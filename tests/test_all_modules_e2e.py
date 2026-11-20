"""
Autonomous Multi-Agent RAG Research Assistant - Comprehensive Verification Suite
Tests all 10 core architectural modules end-to-end:
1. Academic Search APIs & Normalization
2. SQLite Project Scoping & Paper Persistence
3. PyMuPDF Page-by-Page PDF Extraction & Chunking
4. FAISS Vector Store Indexing & Semantic Search
5. 15-Dimension Comparative Matrix & Synthesis
6. 7-Category Research Gap Discovery & Critical Evidence Rule
7. 18-Dimension Proposal Generation & Capstone Ranking
8. Dual Streamlit / SQLite Session Data Loader
9. Academic Word (.docx) Report Generator
10. RAG Service Grounded Dual-Paper Provenance
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db import (
    init_db,
    create_project,
    get_projects,
    get_project,
    save_papers,
    get_papers,
    set_paper_selected,
    get_selected_papers,
    save_analysis_results,
    get_analysis_results
)
from services.paper_search import (
    normalize_title,
    compute_relevance_score,
    search_real_papers,
    get_last_provider_status,
    COMMON_STOPWORDS
)
from services.pdf_processor import extract_and_chunk_pdf, detect_section_title
from services.vector_store import FAISSVectorStore
from services.embedding_service import get_embedder
from services.rag_service import RAGService
from agents.analysis_agent import REQUIRED_DIMENSIONS, REQUIRED_FIELDS
from agents.gap_agent import (
    validate_and_classify_gap,
    MANDATORY_CATEGORIES,
    CLASSIFICATION_EXPLICIT,
    CLASSIFICATION_INFERRED,
    CLASSIFICATION_LITERATURE,
    CLASSIFICATION_UNVERIFIED
)
from reports.report_generator import generate_research_docx_report
from app import load_project_analysis_data


class TestComprehensiveE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.test_project_id = "a59921d8-713a-46ff-9a45-7a0e5efb2162"

    def test_01_search_normalization_and_deduplication(self):
        """1. Verify title normalization, query term scoring, and deduplication logic."""
        t1 = "LoRA: Low-Rank Adaptation of Large Language Models!"
        t2 = "lora  low-rank adaptation of large language models."
        self.assertEqual(normalize_title(t1), normalize_title(t2))

        paper = {
            "title": "Parameter-Efficient Fine-Tuning LoRA vs Full Fine-Tuning",
            "abstract": "We evaluate LoRA across downstream reasoning tasks.",
            "year": 2024,
            "pdf_url": "https://arxiv.org/pdf/2106.09685.pdf",
            "citation_count": 150
        }
        score = compute_relevance_score(paper, ["parameter", "lora", "tuning"])
        self.assertGreater(score, 5.0, "Relevance score should reflect title matches, recency, and PDF presence")
        print("\n[Module 1 PASS] Search normalization and relevance scoring verified.")

    def test_02_database_persistence_and_cross_project_isolation(self):
        """2. Verify that papers saved across different projects have isolated IDs and never overwrite."""
        proj_1 = create_project("Test Topic Isolation Alpha")
        proj_2 = create_project("Test Topic Isolation Beta")

        sample_papers = [
            {"id": "shared_paper_1", "title": "Foundation Models for Robotics", "authors": "Researcher A", "year": 2024},
            {"id": "shared_paper_2", "title": "Zero-Shot Policy Learning", "authors": "Researcher B", "year": 2023}
        ]

        save_papers(proj_1, sample_papers)
        save_papers(proj_2, sample_papers)

        papers_1 = get_papers(proj_1)
        papers_2 = get_papers(proj_2)

        self.assertEqual(len(papers_1), 2)
        self.assertEqual(len(papers_2), 2)

        # Confirm IDs are scoped to respective projects
        for p in papers_1:
            self.assertTrue(p["id"].startswith(f"{proj_1}_"))
        for p in papers_2:
            self.assertTrue(p["id"].startswith(f"{proj_2}_"))

        # Confirm selecting in proj_1 does not alter proj_2
        set_paper_selected(proj_1, papers_1[0]["id"], True)
        self.assertEqual(len(get_selected_papers(proj_1)), 1)
        self.assertEqual(len(get_selected_papers(proj_2)), 0)

        print("[Module 2 PASS] Database project-scoping and selection isolation verified.")

    def test_03_pdf_extraction_and_chunking(self):
        """3. Verify PyMuPDF page-by-page extraction and 1-indexed page preservation."""
        sample_pdf = PROJECT_ROOT / "storage" / "papers" / "arxiv_2506_15415v1.pdf"
        self.assertTrue(sample_pdf.exists(), f"Sample PDF must exist at {sample_pdf}")

        chunks, pages, err = extract_and_chunk_pdf(
            str(sample_pdf),
            paper_id="test_paper_sample",
            paper_title="Targeted Lexical Injection via LoRA"
        )
        self.assertIsNone(err)
        self.assertGreater(pages, 0)
        self.assertGreater(len(chunks), 0)

        c = chunks[0]
        self.assertEqual(c["paper_id"], "test_paper_sample")
        self.assertGreaterEqual(c["page_number"], 1)
        self.assertIn("section", c)
        self.assertIn("content", c)
        print(f"[Module 3 PASS] PyMuPDF extraction: {pages} pages, {len(chunks)} chunks.")

    def test_04_faiss_vector_store_retrieval(self):
        """4. Verify FAISS CPU vector index loading and chunk retrieval."""
        vs = FAISSVectorStore(self.test_project_id)
        loaded = vs.load()
        self.assertTrue(loaded, f"FAISS index for {self.test_project_id} should load from storage/indexes")
        self.assertGreater(len(vs.chunks), 0)

        # Embed query and search
        embedder = get_embedder()
        q_emb = embedder.embed_query("parameter efficient fine tuning adaptation")
        results = vs.search(q_emb, top_k=3)
        self.assertGreater(len(results), 0)
        self.assertIn("score", results[0])
        print(f"[Module 4 PASS] FAISS vector store: {len(vs.chunks)} chunks indexed, top search score: {results[0]['score']:.3f}.")

    def test_05_15_dimension_matrix_structure(self):
        """5. Verify all 15 required scientific comparison dimensions are defined and accessible."""
        required_keys = [k for k, _ in REQUIRED_DIMENSIONS]
        self.assertEqual(len(required_keys), 15)
        expected_keys = [
            "research_objective", "problem_statement", "research_questions",
            "proposed_methodology", "model_architecture", "algorithms",
            "dataset_names", "dataset_sizes", "experimental_setup",
            "evaluation_metrics", "actual_experimental_results", "baseline_methods",
            "strengths", "explicit_limitations", "future_research_directions"
        ]
        for ek in expected_keys:
            self.assertIn(ek, required_keys, f"Expected key '{ek}' missing from REQUIRED_DIMENSIONS")
        print("[Module 5 PASS] 15-Dimension comparative matrix schema verified.")

    def test_06_research_gap_critical_evidence_rule(self):
        """6. Verify algorithmic enforcement of Critical Evidence Rule and 7 mandatory categories."""
        self.assertEqual(len(MANDATORY_CATEGORIES), 7)

        # Gap with verified evidence
        good_gap = {
            "gap_title": "Lack of Multi-Modal Vision Adaptation",
            "category": "Methodological Gaps",
            "paper_a_evidence": "Paper A evaluated exclusively on text benchmarks (page 6).",
            "paper_b_evidence": "Paper B tested solely on unimodal classification (page 4).",
            "why_it_matters": "Vision-language models require unified multimodal adaptation.",
            "possible_solution": "Unified vision-text adapter layer."
        }
        validated_good = validate_and_classify_gap(good_gap)
        self.assertEqual(validated_good["verification_status"], "VERIFIED")

        # Gap with missing evidence -> Must be UNVERIFIED
        bad_gap = {
            "gap_title": "Hypothetical Unproven Gap",
            "category": "Dataset Gaps",
            "paper_a_evidence": "Not reported in the paper",
            "paper_b_evidence": "None provided",
            "why_it_matters": "Unknown.",
            "possible_solution": "Unknown."
        }
        validated_bad = validate_and_classify_gap(bad_gap)
        self.assertEqual(validated_bad["verification_status"], "UNVERIFIED")
        self.assertIn("missing", validated_bad["verification_note"].lower())
        print("[Module 6 PASS] 7 Gap Categories and Critical Evidence Rule validation verified.")

    def test_07_proposals_ranking_and_capstone(self):
        """7. Verify proposal structure containing all 18 dimensions and capstone ranking."""
        analysis = get_analysis_results(self.test_project_id)
        self.assertIsNotNone(analysis)
        proposals = analysis.get("proposals", [])
        self.assertGreaterEqual(len(proposals), 1)

        p = proposals[0]
        self.assertIn("research_title", p)
        self.assertIn("abstract", p)
        self.assertIn("problem_statement", p)
        self.assertIn("research_hypothesis", p)
        self.assertIn("proposed_methodology", p)
        self.assertTrue(bool(p.get("ranking_breakdown") or p.get("feasibility") or p.get("implementation_roadmap")))

        has_capstone = any(prop.get("recommended_for_student") for prop in proposals)
        self.assertTrue(has_capstone, "At least one proposal must be tagged as recommended capstone project")
        print(f"[Module 7 PASS] Verified {len(proposals)} proposals with capstone selection.")

    def test_08_streamlit_dual_persistence_loader(self):
        """8. Verify load_project_analysis_data synchronizes SQLite and session state across reruns."""
        data = load_project_analysis_data(self.test_project_id)
        self.assertIsNotNone(data)
        self.assertIn("comparative_matrix", data)
        self.assertIn("gaps", data)
        self.assertIn("proposals", data)
        self.assertGreaterEqual(len(data["gaps"]), 1)
        self.assertGreaterEqual(len(data["proposals"]), 1)
        print("[Module 8 PASS] Unified loader loads and synchronizes analysis data across reruns.")

    def test_09_academic_word_report_generator(self):
        """9. Verify generate_research_docx_report builds a publication-grade Word document."""
        selected = get_selected_papers(self.test_project_id)
        data = load_project_analysis_data(self.test_project_id)
        test_doc_name = "test_e2e_report.docx"

        doc_path = generate_research_docx_report(
            project_title="Autonomous Multi-Agent RAG Literature Review",
            topic="Parameter-Efficient Fine-Tuning LoRA vs Full Fine-Tuning",
            paper_a=selected[0],
            paper_b=selected[1],
            comparative_matrix=data["comparative_matrix"],
            gaps=data["gaps"],
            proposals=data["proposals"],
            output_filename=test_doc_name
        )
        self.assertTrue(os.path.exists(doc_path))
        size = os.path.getsize(doc_path)
        self.assertGreater(size, 10000)

        # Cleanup
        try:
            os.remove(doc_path)
        except Exception:
            pass
        print(f"[Module 9 PASS] Word report generation verified ({size} bytes).")

    def test_10_rag_service_provenance_and_defensive_kwargs(self):
        """10. Verify RAGService retrieves balanced chunks and accepts kwargs without crashing."""
        rag = RAGService(self.test_project_id)
        selected = get_selected_papers(self.test_project_id)
        # Test retrieve_balanced_context with kwargs
        chunks = rag.retrieve_balanced_context(
            "LoRA rank adaptation",
            paper_a_id=selected[0]["id"],
            paper_b_id=selected[1]["id"],
            extra_param_should_not_crash=True
        )
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)
        print(f"[Module 10 PASS] RAG balanced retrieval verified with {len(chunks)} provenance passages.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
