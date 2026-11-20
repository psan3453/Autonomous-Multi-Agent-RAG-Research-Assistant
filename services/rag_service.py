"""
RAG Service for Grounded Research Q&A.
- Retrieves relevant chunks from FAISS CPU vector database.
- Implements balanced dual-paper retrieval so both Paper A and Paper B are represented
  for cross-paper inquiries.
- Supports paper-specific filtering (Paper A only, Paper B only).
- Enforces strict evidence grounding and inline provenance citations: [Paper Title, Page X, Section Y].
- Explicitly reports when retrieved evidence is insufficient.
"""

from typing import List, Dict, Any, Optional
from services.embedding_service import get_embedder
from services.vector_store import FAISSVectorStore
from services.llm_service import get_llm_service, log_diagnostic
from config import TOP_K_RETRIEVAL, SCORE_THRESHOLD


class RAGService:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.vector_store = FAISSVectorStore(project_id)
        self.embedder = get_embedder()
        self.llm = get_llm_service()

    def retrieve_balanced_context(
        self,
        query: str,
        paper_a_id: Optional[str] = None,
        paper_b_id: Optional[str] = None,
        paper_filter: Optional[str] = None,
        top_k_per_paper: int = 3,
        threshold: float = SCORE_THRESHOLD,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks with balanced representation:
        - If paper_filter is set to a specific paper_id, retrieve top-k from that paper.
        - If cross-paper (default), retrieve top-k from Paper A AND top-k from Paper B,
          ensuring both papers are represented in the prompt context.
        """
        query_emb = self.embedder.embed_query(query)

        # 1. Single Paper Filtered Retrieval
        if paper_filter and paper_filter != "both":
            raw_chunks = self.vector_store.search(
                query_emb,
                top_k=top_k_per_paper * 2,
                paper_id_filter=paper_filter
            )
            filtered = [c for c in raw_chunks if c.get("score", 0.0) >= threshold]
            return filtered[:top_k_per_paper * 2] if filtered else raw_chunks[:2]

        # 2. Balanced Dual-Paper Retrieval
        chunks_a: List[Dict[str, Any]] = []
        chunks_b: List[Dict[str, Any]] = []

        if paper_a_id:
            raw_a = self.vector_store.search(query_emb, top_k=top_k_per_paper * 2, paper_id_filter=paper_a_id)
            filtered_a = [c for c in raw_a if c.get("score", 0.0) >= threshold]
            chunks_a = filtered_a[:top_k_per_paper] if filtered_a else raw_a[:1]

        if paper_b_id:
            raw_b = self.vector_store.search(query_emb, top_k=top_k_per_paper * 2, paper_id_filter=paper_b_id)
            filtered_b = [c for c in raw_b if c.get("score", 0.0) >= threshold]
            chunks_b = filtered_b[:top_k_per_paper] if filtered_b else raw_b[:1]

        # If paper IDs were not provided, fallback to standard top-k search
        if not chunks_a and not chunks_b:
            raw_all = self.vector_store.search(query_emb, top_k=TOP_K_RETRIEVAL)
            return [c for c in raw_all if c.get("score", 0.0) >= threshold] or raw_all[:2]

        # Combine and interleave
        combined = chunks_a + chunks_b
        combined.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return combined

    def answer_question(
        self,
        query: str,
        paper_a_id: Optional[str] = None,
        paper_b_id: Optional[str] = None,
        paper_a_title: str = "Paper A",
        paper_b_title: str = "Paper B",
        paper_filter: Optional[str] = None,
        top_k: int = 4,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute reliable RAG pipeline:
        1. Retrieve relevant chunks using balanced dual-paper strategy.
        2. Construct strict provenance context.
        3. Enforce grounded answer generation with citations.
        4. Return structured answer with exact page, section, and excerpt provenance.
        """
        chunks = self.retrieve_balanced_context(
            query=query,
            paper_a_id=paper_a_id,
            paper_b_id=paper_b_id,
            paper_filter=paper_filter,
            top_k_per_paper=max(2, top_k // 2)
        )

        if not chunks:
            return {
                "answer": (
                    "No relevant passages were found in the indexed vector store. "
                    "Please verify that the research papers have been uploaded and processed."
                ),
                "citations": [],
                "chunks": []
            }

        context_blocks = []
        citations_summary = []

        for idx, chunk in enumerate(chunks, 1):
            p_title = chunk.get("paper_title", "Unknown Paper")
            page_num = chunk.get("page_number", "Unknown")
            sec = chunk.get("section", "General")
            content = chunk.get("content", "").strip()
            score = chunk.get("score", 0.0)

            context_blocks.append(
                f"[Source {idx}] Paper: \"{p_title}\" | Page: {page_num} | Section: {sec} | Similarity: {score:.3f}\n"
                f"Passage:\n{content}\n"
            )

            citations_summary.append({
                "source_id": idx,
                "paper_title": p_title,
                "page_number": page_num,
                "section": sec,
                "score": round(score, 4),
                "snippet": content[:240] + "..." if len(content) > 240 else content
            })

        formatted_context = "\n---\n".join(context_blocks)

        system_instruction = (
            "You are an expert Academic Research Scientist answering questions based on two research papers.\n"
            "STRICT GROUNDING RULES:\n"
            "1. Base your answer EXCLUSIVELY on the retrieved source passages provided below.\n"
            "2. Whenever stating a factual assertion, finding, metric, or limitation, immediately cite its source in the format: "
            "[Paper Title, Page X, Section Y] or [Source N].\n"
            "3. If the retrieved passages do NOT contain sufficient evidence to answer the user query with certainty, "
            "you MUST state explicitly: 'Based on the retrieved excerpts from the papers, there is insufficient evidence in the text to confirm...'\n"
            "4. Never hallucinate experimental results, dataset sizes, or benchmarks not present in the excerpts.\n"
            "5. If comparing the two papers, clearly separate what Paper A demonstrates from what Paper B demonstrates."
        )

        user_prompt = (
            f"USER INQUIRY: {query}\n\n"
            f"SELECTED PAPERS:\n"
            f"- Paper A: {paper_a_title}\n"
            f"- Paper B: {paper_b_title}\n\n"
            f"RETRIEVED SOURCE EXCERPTS:\n\n"
            f"{formatted_context}\n\n"
            "Provide a comprehensive, evidence-grounded response with specific page and section citations."
        )

        try:
            answer = self.llm.invoke(user_prompt, system_instruction=system_instruction, task_type="deep_reasoning")
        except Exception as e:
            log_diagnostic("ERROR", "Failed to generate RAG response", e)
            answer = f"Error generating answer with LLM service: {str(e)}"

        return {
            "answer": answer,
            "citations": citations_summary,
            "chunks": chunks
        }
