"""
End-to-End Pipeline Verification Test.
Tests:
- Real paper search with Semantic Scholar & arXiv
- Database persistence of projects and papers
- Report generator outputting valid .docx file
"""

import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import (
    init_db,
    create_project,
    save_papers,
    get_papers,
    set_paper_selected,
    get_selected_papers
)
from services.paper_search import search_real_papers
from reports.report_generator import generate_research_docx_report


class TestE2EPipeline(unittest.TestCase):

    def test_e2e_search_and_persist(self):
        init_db()
        topic = "Retrieval Augmented Generation"
        proj_id = create_project(topic)

        # Real paper search
        papers = search_real_papers(topic, max_results=5)
        self.assertGreaterEqual(len(papers), 1, "Should find at least 1 real paper")
        
        first_paper = papers[0]
        self.assertTrue(len(first_paper["title"]) > 5)
        self.assertIn("source", first_paper)
        print(f"\n[E2E TEST] Discovered paper: {first_paper['title']} ({first_paper.get('year')})")

        # Save to DB
        save_papers(proj_id, papers)
        db_papers = get_papers(proj_id)
        self.assertEqual(len(db_papers), len(papers))

        # Select 2 papers if available
        if len(db_papers) >= 2:
            set_paper_selected(proj_id, db_papers[0]["id"], True)
            set_paper_selected(proj_id, db_papers[1]["id"], True)
            selected = get_selected_papers(proj_id)
            self.assertEqual(len(selected), 2)

    def test_e2e_docx_report_generation(self):
        paper_a = {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "authors": "Patrick Lewis et al.",
            "year": 2020,
            "doi": "10.48550/arXiv.2005.11401",
            "url": "https://arxiv.org/abs/2005.11401"
        }
        paper_b = {
            "title": "Dense Passage Retrieval for Open-Domain Question Answering",
            "authors": "Vladimir Karpukhin et al.",
            "year": 2020,
            "doi": "10.18653/v1/2020.emnlp-main.550",
            "url": "https://arxiv.org/abs/2004.04906"
        }
        analysis_a = {
            "objectives": "Combine parametric memory with non-parametric retrieval.",
            "methodology": "DPR retriever coupled with BART sequence-to-sequence generator.",
            "datasets": "Natural Questions, TriviaQA, CuratedTREC",
            "experimental_results": "Outperforms state-of-the-art extractive and generative baselines.",
            "limitations": ["Retriever update latency", "Hallucinations on ungrounded documents"]
        }
        analysis_b = {
            "objectives": "Demonstrate dense representations outperform BM25 in open-domain QA.",
            "methodology": "Dual-encoder BERT architecture trained with in-batch negatives.",
            "datasets": "Natural Questions, WebQuestions, SQuAD",
            "experimental_results": "Achieves 78.4% top-20 retrieval accuracy, beating BM25 by 19%.",
            "limitations": ["Limited out-of-domain vocabulary generalization", "High memory index footprint"]
        }
        comparative_matrix = {
            "table": [
                {
                    "dimension": "Architecture",
                    "paper_a": "Retriever-Generator Hybrid (DPR + BART)",
                    "paper_b": "Dense Dual-Encoder Retriever Only",
                    "comparative_insight": "Paper A focuses on end-to-end generation, Paper B on retrieval ranking."
                }
            ],
            "comparative_summary": "Both papers established modern dense neural retrieval foundation.",
            "winner_or_tradeoff_verdict": "Tradeoff between generation fidelity and retrieval index size."
        }
        gaps = [
            {
                "gap_title": "Out-of-Distribution Dense Retrieval Failure",
                "category": "Generalization",
                "description": "Dense encoders overfit to Wikipedia domain and degrade on specialized medical/legal corpora.",
                "evidence_paper_a": "Trained exclusively on Wikipedia dumps.",
                "evidence_paper_b": "Zero-shot transfer shows 15% drop on non-Wikipedia benchmarks.",
                "page_refs_a": "Section 4.1, Page 5",
                "page_refs_b": "Section 5.2, Page 7",
                "why_it_matters": "Critical for cross-domain enterprise adoption.",
                "gap_type": "Author-Stated Limitation",
                "confidence_level": "High",
                "verification_status": "Verified from Text"
            }
        ]
        proposals = [
            {
                "rank": 1,
                "proposed_title": "Cross-Domain Adaptive Dense RAG via Self-Supervised Continual Re-indexing",
                "problem_statement": "Generalization drop in dense retrievers when migrating out of distribution.",
                "motivation": "Addresses real-world domain shifts.",
                "proposed_solution": "Lightweight LoRA adapters with unsupervised contrastive pre-training.",
                "research_hypothesis": "Adapter tuning preserves 92% retrieval recall across heterogeneous corpora.",
                "technical_architecture": "BGE small encoder with low-rank domain projection matrices.",
                "algorithms": ["Contrastive InfoNCE Loss", "LoRA", "HNSW FAISS"],
                "dataset_suggestions": ["BEIR Benchmark", "BioASQ"],
                "implementation_steps": [
                    "Benchmark baseline DPR on BEIR",
                    "Implement domain-adaptive projection layer",
                    "Evaluate cross-domain MRR@10 and inference latency"
                ],
                "evaluation_metrics": ["MRR@10", "NDCG@10", "Latency (ms)"],
                "expected_outcomes": "12% improvement in out-of-domain retrieval accuracy.",
                "student_feasibility": "High - Feasible in 3 months on single GPU or CPU.",
                "potential_research_contribution": "First plug-and-play domain adapter for dense RAG.",
                "limitations_and_risks": "Requires multi-domain evaluation sets."
            }
        ]

        doc_path = generate_research_docx_report(
            project_title="Test Project Report",
            topic="Dense Retrieval and RAG",
            paper_a=paper_a,
            paper_b=paper_b,
            analysis_a=analysis_a,
            analysis_b=analysis_b,
            comparative_matrix=comparative_matrix,
            gaps=gaps,
            proposals=proposals,
            output_filename="test_output_report.docx"
        )
        self.assertTrue(os.path.exists(doc_path), f"Report not found at {doc_path}")
        self.assertGreater(os.path.getsize(doc_path), 5000, "Docx file should be non-empty")
        print(f"\n[E2E TEST] Generated DOCX Report: {doc_path} ({os.path.getsize(doc_path)} bytes)")


if __name__ == "__main__":
    unittest.main()
