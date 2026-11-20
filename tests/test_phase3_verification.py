import sys
from pathlib import Path
sys.path.insert(0, ".")

from database.db import get_projects, get_selected_papers, save_chat_message, get_chat_history
from services.rag_service import RAGService
from services.vector_store import FAISSVectorStore

def test_phase3():
    print("--- [TEST 1] Locating Vector Indexed Project ---")
    projects = get_projects()
    test_proj = None
    for p in projects:
        vs = FAISSVectorStore(p["id"])
        if vs.exists() and vs.load() and len(vs.chunks) > 0:
            test_proj = p
            break

    assert test_proj is not None, "No project with active FAISS index found from Phase 2"
    proj_id = test_proj["id"]
    print(f"Using project {proj_id} with {len(FAISSVectorStore(proj_id).chunks)} indexed chunks.")

    vs = FAISSVectorStore(proj_id)
    vs.load()
    paper_ids = list({c["paper_id"] for c in vs.chunks})
    assert len(paper_ids) >= 2, f"Expected at least 2 distinct paper IDs in index, got {len(paper_ids)}"
    paper_a_id, paper_b_id = paper_ids[0], paper_ids[1]

    rag = RAGService(proj_id)

    print("--- [TEST 2] Testing Balanced Dual-Paper Retrieval ---")
    query = "What methodology, dataset, and evaluation metrics are used?"
    balanced_chunks = rag.retrieve_balanced_context(
        query=query,
        paper_a_id=paper_a_id,
        paper_b_id=paper_b_id,
        top_k_per_paper=3
    )

    chunks_a = [c for c in balanced_chunks if c["paper_id"] == paper_a_id]
    chunks_b = [c for c in balanced_chunks if c["paper_id"] == paper_b_id]
    print(f"Retrieved: {len(chunks_a)} chunks from Paper A, {len(chunks_b)} chunks from Paper B.")
    assert len(chunks_a) > 0, "Paper A has 0 retrieved chunks"
    assert len(chunks_b) > 0, "Paper B has 0 retrieved chunks"

    print("--- [TEST 3] Testing Paper-Specific Retrieval Scope ---")
    chunks_only_a = rag.retrieve_balanced_context(query=query, paper_filter=paper_a_id, top_k_per_paper=3)
    assert all(c["paper_id"] == paper_a_id for c in chunks_only_a), "Found non-Paper A chunk in Paper A filter"

    chunks_only_b = rag.retrieve_balanced_context(query=query, paper_filter=paper_b_id, top_k_per_paper=3)
    assert all(c["paper_id"] == paper_b_id for c in chunks_only_b), "Found non-Paper B chunk in Paper B filter"
    print("Paper filter scoping verified successfully.")

    print("--- [TEST 4] Testing Grounded Q&A Generation & Provenance Citations ---")
    result = rag.answer_question(
        query=query,
        paper_a_id=paper_a_id,
        paper_b_id=paper_b_id,
        paper_a_title="Paper A Title",
        paper_b_title="Paper B Title"
    )

    answer = result.get("answer", "")
    citations = result.get("citations", [])
    print(f"Generated answer length: {len(answer)} chars.")
    print(f"Total citations returned: {len(citations)}")
    assert len(answer) > 50, "Answer too short or empty"
    assert len(citations) > 0, "No citations returned in RAG response"

    # Verify citation fields
    first_cit = citations[0]
    for req_key in ["paper_title", "page_number", "section", "score", "snippet"]:
        assert req_key in first_cit, f"Missing citation key: {req_key}"
        assert first_cit[req_key] is not None

    print(f"Sample citation: Page {first_cit['page_number']}, Section '{first_cit['section']}', Score: {first_cit['score']}")

    print("--- [TEST 5] Testing Chat History Persistence in SQLite ---")
    save_chat_message(proj_id, "user", query, [])
    save_chat_message(proj_id, "assistant", answer, citations)

    history = get_chat_history(proj_id)
    assert len(history) >= 2, f"Expected at least 2 messages in chat history, got {len(history)}"
    last_user_msg = history[-2]
    last_asst_msg = history[-1]
    assert last_user_msg["role"] == "user"
    assert last_asst_msg["role"] == "assistant"
    assert len(last_asst_msg.get("citations", [])) > 0
    print(f"Persisted and retrieved {len(history)} chat messages with citations.")

    print("\n✅ ALL PHASE 3 ACCEPTANCE TESTS PASSED!")

if __name__ == "__main__":
    test_phase3()
