import sys
import os
from pathlib import Path
sys.path.insert(0, ".")

from database.db import init_db, create_project, save_papers, get_papers, set_paper_selected, get_selected_papers
from services.paper_search import search_real_papers, get_last_provider_status
from services.pdf_processor import extract_and_chunk_pdf
from services.embedding_service import get_embedder
from services.vector_store import FAISSVectorStore

def run_search_quality_audit():
    print("======================================================================")
    print("=== STARTING COMPREHENSIVE SEARCH QUALITY & RELEVANCE AUDIT ===")
    print("======================================================================")
    init_db()

    test_queries = [
        {
            "query": "Image Captioning using Deep Learning",
            "topic": "Image Captioning",
            "required_concept": ["caption", "captioning", "image-to-text", "visual description"],
            "conflicting_concepts": ["enhancement", "segmentation", "super-resolution"]
        },
        {
            "query": "Image Enhancement",
            "topic": "Image Enhancement",
            "required_concept": ["enhancement", "enhancing", "low-light", "super-resolution", "denoising", "restoration"],
            "conflicting_concepts": ["caption", "captioning"]
        },
        {
            "query": "Image Classification",
            "topic": "Image Classification",
            "required_concept": ["classification", "classifier", "classifying", "categorization", "recognition"],
            "conflicting_concepts": ["caption", "captioning"]
        },
        {
            "query": "Image Segmentation",
            "topic": "Image Segmentation",
            "required_concept": ["segmentation", "segmenting", "segmenter", "pixel-level", "contour", "mask"],
            "conflicting_concepts": ["caption", "captioning"]
        }
    ]

    all_audits_passed = True
    audit_records = []

    for t_info in test_queries:
        q = t_info["query"]
        topic_name = t_info["topic"]
        req_concepts = t_info["required_concept"]
        conflict_concepts = t_info["conflicting_concepts"]

        print(f"\n" + "="*70)
        print(f"QUERY: '{q}'")
        print(f"Target Research Domain: {topic_name}")
        print("="*70)

        # 1. Execute live search
        papers = search_real_papers(q, max_results=5)
        prov_status = get_last_provider_status()
        print(f"Discovered {len(papers)} papers across APIs:")

        if len(papers) < 3:
            print(f"[FAIL] Returned only {len(papers)} papers (expected at least 3).")
            all_audits_passed = False

        # Create project to mirror Streamlit backend
        proj_id = create_project(q, name=f"Audit_{topic_name.replace(' ', '_')}")
        save_papers(proj_id, papers)

        for idx, p in enumerate(papers, 1):
            title = p.get("title", "")
            abstract = p.get("abstract", "")
            full_text = (f"{title} {abstract}").lower()

            rel_class = p.get("relevance_classification", "Irrelevant")
            rel_note = p.get("relevance_note", "")

            # Research objective audit
            has_required = any(c in full_text for c in req_concepts)
            has_conflict = any(c in title.lower() for c in conflict_concepts) and not has_required

            # Verify classification validity
            if rel_class == "Relevant":
                if not has_required:
                    print(f"  [AUDIT ERROR] Paper marked Relevant but lacks core concept {req_concepts}!")
                    all_audits_passed = False
            elif rel_class == "Irrelevant":
                print(f"  [INFO] Filtered / Flagged Irrelevant: {title}")

            if has_conflict:
                print(f"  [CROSS-TOPIC CONTAMINATION DETECTED] Title: '{title}' contains conflicting concepts {conflict_concepts}!")
                all_audits_passed = False

            print(f"\n  Paper {idx}: {title}")
            print(f"    Authors: {p.get('authors')} ({p.get('year', 'N/A')}) | Source: {p.get('source')}")
            print(f"    Classification: [{rel_class}]")
            print(f"    Justification: {rel_note}")
            print(f"    Research Objective Alignment: {'VERIFIED ALIGNED' if has_required else 'NOT ALIGNED'}")

        audit_records.append({
            "query": q,
            "topic": topic_name,
            "project_id": proj_id,
            "papers": papers
        })

    # ----------------------------------------------------------------------
    # STEP 8: Confirm selected papers proceed through PDF processing & vector indexing
    # ----------------------------------------------------------------------
    print("\n" + "="*70)
    print("STEP 8: VERIFYING DOWNSTREAM PIPELINE CONTINUITY (PDF -> FAISS)")
    print("="*70)

    # Use first audit project (Image Captioning)
    caption_audit = audit_records[0]
    cap_proj_id = caption_audit["project_id"]
    cap_papers = caption_audit["papers"]

    # Select two papers
    paper_a = cap_papers[0]
    paper_b = cap_papers[1]
    set_paper_selected(cap_proj_id, paper_a["id"], True)
    set_paper_selected(cap_proj_id, paper_b["id"], True)

    selected = get_selected_papers(cap_proj_id)
    assert len(selected) == 2, f"Expected 2 selected papers, got {len(selected)}"
    print(f"Successfully selected 2 papers in Project {cap_proj_id[:8]}:")
    print(f"  Paper A: {selected[0]['title']}")
    print(f"  Paper B: {selected[1]['title']}")

    # Ingest 2 local test PDFs representing these papers
    papers_dir = Path("storage/papers")
    pdf_files = list(papers_dir.glob("*.pdf"))
    assert len(pdf_files) >= 2, "Need 2 test PDFs"

    pdf_a_path = str(pdf_files[0])
    pdf_b_path = str(pdf_files[1])

    chunks_a, pages_a, err_a = extract_and_chunk_pdf(pdf_a_path, selected[0]["id"], selected[0]["title"])
    chunks_b, pages_b, err_b = extract_and_chunk_pdf(pdf_b_path, selected[1]["id"], selected[1]["title"])

    print(f"Extracted {pages_a} pages ({len(chunks_a)} chunks) for Paper A")
    print(f"Extracted {pages_b} pages ({len(chunks_b)} chunks) for Paper B")

    all_chunks = chunks_a + chunks_b
    embedder = get_embedder()
    embeddings = embedder.embed_texts([c["content"] for c in all_chunks])

    vs = FAISSVectorStore(cap_proj_id)
    built_ok = vs.build_and_save(all_chunks, embeddings)
    reloaded_ok = vs.load()

    downstream_ok = (built_ok and reloaded_ok and len(vs.chunks) == len(all_chunks))
    print(f"FAISS vector store saved and reloaded: {downstream_ok} (Total indexed chunks: {len(vs.chunks)})")

    if not downstream_ok:
        all_audits_passed = False

    print("\n" + "="*70)
    print(f"OVERALL SEARCH QUALITY AUDIT RESULT: {'ALL AUDITS PASSED' if all_audits_passed else 'AUDIT FAILED'}")
    print("="*70)
    return all_audits_passed

if __name__ == "__main__":
    success = run_search_quality_audit()
    sys.exit(0 if success else 1)
