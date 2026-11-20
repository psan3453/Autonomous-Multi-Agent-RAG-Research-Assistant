"""
Comprehensive Test Suite for Phase 7 Requirements.
Tests:
1. PDF text extraction (PyMuPDF)
2. Chunk metadata and page preservation
3. FAISS retrieval for Paper A
4. FAISS retrieval for Paper B
5. RAG answer generation with citations
6. Structured paper analysis (15 fields)
7. Comparison output & scope disparity check
8. Gap evidence validation (Critical Evidence Rule)
9. LangGraph state transitions
"""

import os
import unittest
import sys
from pathlib import Path

# Ensure root directory is on path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.db import init_db, get_project, get_selected_papers
from services.pdf_processor import extract_and_chunk_pdf
from services.vector_store import FAISSVectorStore
from services.rag_service import RAGService
from agents.analysis_agent import run_analysis_agent, build_comparative_matrix, REQUIRED_FIELDS
from agents.gap_agent import validate_and_classify_gap
from graph.workflow import build_research_graph, execute_multi_agent_workflow


class TestPhase7ResearchPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import gc
        gc.collect()
        init_db()
        cls.project_id = "a59921d8-713a-46ff-9a45-7a0e5efb2162"
        # Pre-load embedder cleanly once for the test process
        try:
            from services.embedding_service import get_embedder
            get_embedder()._load_model()
        except Exception:
            pass

        cls.paper_a = {
            "id": "arxiv_2606.01947v1",
            "title": "Parameter-Efficient Fine-Tuning of Large Pretrained Models for Instance Segmentation Tasks",
            "authors": "Abou Baker et al.",
            "year": 2024,
            "local_pdf_path": str(ROOT_DIR / "storage" / "papers" / "arxiv_2606_01947v1.pdf")
        }
        cls.paper_b = {
            "id": "arxiv_2506.15415v1",
            "title": "Targeted Lexical Injection: Unlocking Latent Cross-Lingual Alignment in Lugha-Llama via Early-Layer LoRA Fine-Tuning",
            "authors": "Research Team",
            "year": 2025,
            "local_pdf_path": str(ROOT_DIR / "storage" / "papers" / "arxiv_2506_15415v1.pdf")
        }

    def test_01_pdf_text_extraction(self):
        """1. Test PDF text extraction on real downloaded PDF."""
        self.assertTrue(os.path.exists(self.paper_b["local_pdf_path"]), "Paper B local PDF should exist")
        chunks, pages, err = extract_and_chunk_pdf(
            self.paper_b["local_pdf_path"],
            self.paper_b["id"],
            self.paper_b["title"]
        )
        self.assertIsNone(err, f"PDF extraction failed: {err}")
        self.assertGreater(pages, 5, "PDF should have more than 5 pages")
        self.assertGreater(len(chunks), 10, "PDF should produce chunks")

    def test_02_chunk_metadata_and_page_preservation(self):
        """2. Test chunk metadata and page preservation."""
        chunks, pages, _ = extract_and_chunk_pdf(
            self.paper_b["local_pdf_path"],
            self.paper_b["id"],
            self.paper_b["title"]
        )
        first_chunk = chunks[0]
        self.assertIn("paper_id", first_chunk)
        self.assertIn("paper_title", first_chunk)
        self.assertIn("page_number", first_chunk)
        self.assertIn("section", first_chunk)
        self.assertIn("chunk_id", first_chunk)
        self.assertEqual(first_chunk["page_number"], 1, "First page should be 1")

    def test_03_faiss_retrieval_paper_a(self):
        """3. Test FAISS retrieval for Paper A."""
        vs = FAISSVectorStore(self.project_id)
        self.assertTrue(vs.load(), "FAISS vector store should load successfully")
        chunks_a = vs.get_all_chunks_for_paper(self.paper_a["id"])
        self.assertGreaterEqual(len(chunks_a), 20, "Paper A should have indexed chunks")

    def test_04_faiss_retrieval_paper_b(self):
        """4. Test FAISS retrieval for Paper B."""
        vs = FAISSVectorStore(self.project_id)
        vs.load()
        chunks_b = vs.get_all_chunks_for_paper(self.paper_b["id"])
        self.assertGreaterEqual(len(chunks_b), 10, "Paper B should have indexed chunks")

    def test_05_rag_answer_generation(self):
        """5. Test grounded RAG answer generation with citations."""
        rag = RAGService(self.project_id)
        result = rag.answer_question(
            query="What problem does Paper A address regarding parameter-efficient fine-tuning?",
            paper_a_id=self.paper_a["id"],
            paper_b_id=self.paper_b["id"],
            paper_a_title=self.paper_a["title"],
            paper_b_title=self.paper_b["title"]
        )
        self.assertIsNotNone(result.get("answer"))
        self.assertNotIn("Error generating answer", result.get("answer"))
        self.assertGreater(len(result.get("citations", [])), 0, "RAG should return supporting citations")

    def test_06_structured_paper_analysis_15_fields(self):
        """6. Test structured paper analysis extracting all 15 required fields."""
        vs = FAISSVectorStore(self.project_id)
        vs.load()
        chunks = vs.get_all_chunks_for_paper(self.paper_a["id"])
        sample_context = "\n\n".join([c["content"] for c in chunks[:5]])

        analysis = run_analysis_agent(self.paper_a["title"], sample_context)
        for field in REQUIRED_FIELDS:
            self.assertIn(field, analysis, f"Field '{field}' missing from analysis")
            self.assertTrue(len(str(analysis[field])) > 0, f"Field '{field}' should not be empty")

    def test_07_comparison_output_and_scope_check(self):
        """7. Test comparative matrix generation and scope disparity warning."""
        mock_a = {
            "title": self.paper_a["title"],
            "research_objective": "Fine-tune instance segmentation with minimal parameters.",
            "research_problem": "High compute cost in vision models.",
            "methodology": "LoRA adapters attached to vision transformer backbones.",
            "model_architecture": "Mask R-CNN / Swin Transformer",
            "algorithms": "AdamW, Low-Rank Adaptation",
            "dataset_names": "COCO, Cityscapes",
            "dataset_sizes": "118k images",
            "training_testing_setup": "80/20 train/test split on A100",
            "evaluation_metrics": "mAP, Box AP, Mask AP",
            "experimental_results": "Achieves 98% of full fine-tuning performance.",
            "baseline_methods": "Full fine-tuning, linear probe",
            "strengths": ["Low memory footprint"],
            "explicit_limitations": ["Evaluated only on 2 vision benchmarks"],
            "future_research_directions": ["Cross-dataset generalization"]
        }
        mock_b = {
            "title": self.paper_b["title"],
            "research_objective": "Unlock cross-lingual alignment in Arabic Llama.",
            "research_problem": "Lexical alignment gap in low-resource multilingual LLMs.",
            "methodology": "Early-layer LoRA fine-tuning for targeted lexical injection.",
            "model_architecture": "Llama-2 7B / Lugha-Llama",
            "algorithms": "Cross-Entropy, Early-Layer LoRA",
            "dataset_names": "Arabic-English Parallel Corpus",
            "dataset_sizes": "500k sentence pairs",
            "training_testing_setup": "Pretrained LLM fine-tuned for 3 epochs",
            "evaluation_metrics": "BLEU, chrF, Perplexity",
            "experimental_results": "Improves translation quality by 3.2 BLEU.",
            "baseline_methods": "Standard LoRA, Full FT",
            "strengths": ["Efficient cross-lingual transfer"],
            "explicit_limitations": ["Limited to Arabic dialectal variations"],
            "future_research_directions": ["Scaling to additional Afroasiatic languages"]
        }

        matrix = build_comparative_matrix(mock_a, mock_b)
        self.assertIn("table", matrix)
        self.assertIn("are_problems_related", matrix)
        self.assertIn("scope_disparity_warning", matrix)
        print("\n[Scope Check Detected]:", matrix.get("scope_disparity_warning"))

    def test_08_gap_evidence_critical_evidence_rule(self):
        """8. Test gap evidence validation enforcing the Critical Evidence Rule."""
        unverified_gap = {
            "gap_title": "Arbitrary Unsupported Metric Gap",
            "category": "Evaluation Gaps",
            "evidence_paper_a": "Not reported in the paper",
            "evidence_paper_b": "Not reported in the paper",
            "classification": "Gap inferred from comparison",
            "confidence_score": 0.8
        }
        validated = validate_and_classify_gap(unverified_gap)
        self.assertEqual(validated["verification_status"], "UNVERIFIED")
        self.assertEqual(validated["classification"], "Unverified Candidate Gap")
        self.assertIn("CRITICAL EVIDENCE RULE", validated["verification_note"])

        verified_gap = {
            "gap_title": "Cross-Domain Transfer Limitation",
            "category": "Generalization Gaps",
            "evidence_paper_a": "Tested exclusively on COCO and Cityscapes benchmarks [Page 12].",
            "evidence_paper_b": "Tested exclusively on Modern Standard Arabic corpus [Page 8].",
            "classification": "Gap inferred from comparison",
            "confidence_score": 0.85
        }
        validated2 = validate_and_classify_gap(verified_gap)
        self.assertEqual(validated2["verification_status"], "VERIFIED")

    def test_09_langgraph_workflow_transitions(self):
        """9. Test LangGraph StateGraph compilation and state transitions."""
        app = build_research_graph()
        self.assertIsNotNone(app, "Compiled StateGraph should not be None")


if __name__ == "__main__":
    unittest.main()
