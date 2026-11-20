import sys
import os
import uuid
from pathlib import Path
sys.path.insert(0, ".")

from services.pdf_processor import extract_and_chunk_pdf
from services.embedding_service import get_embedder
from services.vector_store import FAISSVectorStore
from database.db import init_db, create_project, save_papers, get_papers, set_paper_selected, get_selected_papers, update_paper_pdf_info

def test_phase2():
    print("--- [TEST 1] Testing PyMuPDF Extraction on Real PDF ---")
    papers_dir = Path("storage/papers")
    pdf_files = list(papers_dir.glob("*.pdf"))
    assert len(pdf_files) >= 2, f"Need at least 2 PDFs in storage/papers, found {len(pdf_files)}"

    pdf_a_path = str(pdf_files[0])
    pdf_b_path = str(pdf_files[1])

    proj_id = create_project("Phase 2 PDF Ingestion Verification")
    paper_a_id = f"{proj_id}_paper_a"
    paper_b_id = f"{proj_id}_paper_b"

    chunks_a, pages_a, err_a = extract_and_chunk_pdf(pdf_a_path, paper_a_id, "Sample Paper A Title")
    assert err_a is None, f"Paper A extraction error: {err_a}"
    assert pages_a > 0, "Paper A has 0 pages"
    assert len(chunks_a) > 0, "Paper A produced 0 chunks"
    print(f"Paper A: {pages_a} pages, {len(chunks_a)} chunks extracted.")

    # Verify 1-indexed page numbering
    for c in chunks_a:
        assert c["page_number"] >= 1, f"Invalid page number {c['page_number']}"
        assert c["paper_id"] == paper_a_id
        assert len(c["content"]) >= 50

    chunks_b, pages_b, err_b = extract_and_chunk_pdf(pdf_b_path, paper_b_id, "Sample Paper B Title")
    assert err_b is None, f"Paper B extraction error: {err_b}"
    assert pages_b > 0, "Paper B has 0 pages"
    assert len(chunks_b) > 0, "Paper B produced 0 chunks"
    print(f"Paper B: {pages_b} pages, {len(chunks_b)} chunks extracted.")

    print("--- [TEST 2] Computing BGE Embeddings ---")
    all_chunks = chunks_a + chunks_b
    embedder = get_embedder()
    texts = [c["content"] for c in all_chunks]
    embeddings = embedder.embed_texts(texts)
    assert embeddings.shape[0] == len(all_chunks), "Embedding count mismatch"
    assert embeddings.shape[1] == 384, f"Expected 384 dimensions, got {embeddings.shape[1]}"
    print(f"Generated embeddings shape: {embeddings.shape}")

    print("--- [TEST 3] Building and Persisting FAISS Vector Index ---")
    vs = FAISSVectorStore(proj_id)
    success = vs.build_and_save(all_chunks, embeddings)
    assert success is True, "build_and_save returned False"
    assert vs.exists() is True, "Vector store index files do not exist"
    print("FAISS vector store saved and verified on disk.")

    print("--- [TEST 4] Loading FAISS and Performing Filtered Search ---")
    vs_loaded = FAISSVectorStore(proj_id)
    loaded_ok = vs_loaded.load()
    assert loaded_ok is True, "Failed to reload vector store"
    assert len(vs_loaded.chunks) == len(all_chunks)

    query_emb = embedder.embed_query("evaluation methodology and experimental results")
    results_all = vs_loaded.search(query_emb, top_k=5)
    assert len(results_all) == 5, f"Expected 5 results, got {len(results_all)}"
    print(f"Top search result score: {results_all[0]['score']:.4f} from page {results_all[0]['page_number']}")

    # Search with paper_a filter
    results_a = vs_loaded.search(query_emb, top_k=3, paper_id_filter=paper_a_id)
    assert len(results_a) > 0, "Paper A filtered search returned 0 results"
    for r in results_a:
        assert r["paper_id"] == paper_a_id

    # Search with paper_b filter
    results_b = vs_loaded.search(query_emb, top_k=3, paper_id_filter=paper_b_id)
    assert len(results_b) > 0, "Paper B filtered search returned 0 results"
    for r in results_b:
        assert r["paper_id"] == paper_b_id

    print("Paper-isolated retrieval verified for both Paper A and Paper B.")
    print("\n✅ ALL PHASE 2 ACCEPTANCE TESTS PASSED!")

if __name__ == "__main__":
    test_phase2()
