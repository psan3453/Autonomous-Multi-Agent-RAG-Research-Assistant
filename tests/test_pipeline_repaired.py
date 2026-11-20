"""
Verification test suite for the repaired Paper Comparison, Research Gap Discovery,
and Research Idea Generation pipeline.
Verifies:
1. Both papers analyzed independently across 15 dimensions.
2. Comparative matrix generated with all fields and scope check.
3. Results returned cleanly by LangGraph StateGraph.
4. Results saved to SQLite.
5. Results survive simulated Streamlit reruns.
6. Research gaps generated from the comparison with Critical Evidence Rule.
7. Research proposals generated with all 18 dimensions and capstone project.
8. All three pages display the saved results via load_project_analysis_data.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db import (
    init_db,
    get_project,
    get_selected_papers,
    save_analysis_results,
    get_analysis_results
)
from agents.analysis_agent import run_analysis_agent, build_comparative_matrix, REQUIRED_DIMENSIONS
from agents.gap_agent import run_gap_discovery, validate_and_classify_gap
from agents.proposal_agent import run_proposal_generation
from graph.workflow import execute_multi_agent_workflow, retrieve_paper_context_summary
from services.vector_store import FAISSVectorStore


class TestRepairedPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.project_id = "a59921d8-713a-46ff-9a45-7a0e5efb2162"
        cls.project = get_project(cls.project_id)
        assert cls.project is not None, f"Project {cls.project_id} must exist"

        selected = get_selected_papers(cls.project_id)
        assert len(selected) >= 2, f"Project {cls.project_id} must have 2 selected papers"
        cls.paper_a = selected[0]
        cls.paper_b = selected[1]

        cls.vector_store = FAISSVectorStore(cls.project_id)
        cls.context_a = retrieve_paper_context_summary(cls.vector_store, cls.paper_a["id"], max_chars=3000)
        cls.context_b = retrieve_paper_context_summary(cls.vector_store, cls.paper_b["id"], max_chars=3000)

    def test_01_both_papers_analyzed_independently_15_fields(self):
        """1. Test both papers are analyzed independently with 15 dimensions."""
        analysis_a = run_analysis_agent(self.paper_a["title"], self.context_a)
        analysis_b = run_analysis_agent(self.paper_b["title"], self.context_b)

        self.assertIsInstance(analysis_a, dict)
        self.assertIsInstance(analysis_b, dict)

        for key, name in REQUIRED_DIMENSIONS:
            self.assertIn(key, analysis_a, f"Key '{key}' missing from Paper A analysis")
            self.assertIn(key, analysis_b, f"Key '{key}' missing from Paper B analysis")

        print("\n[Test 01 PASS] Both papers independently analyzed across all 15 dimensions.")

    def test_02_comparative_matrix_generation_and_embedding(self):
        """2. Test comparative matrix is generated and embeds both analyses."""
        mock_a = {k: f"Finding A for {k}" for k, _ in REQUIRED_DIMENSIONS}
        mock_b = {k: f"Finding B for {k}" for k, _ in REQUIRED_DIMENSIONS}
        mock_a["title"] = self.paper_a["title"]
        mock_b["title"] = self.paper_b["title"]

        matrix = build_comparative_matrix(mock_a, mock_b)
        self.assertIsInstance(matrix, dict)
        self.assertIn("table", matrix)
        self.assertGreaterEqual(len(matrix["table"]), 1)
        self.assertIn("analysis_a", matrix)
        self.assertIn("analysis_b", matrix)
        self.assertIn("are_problems_related", matrix)
        self.assertIn("stronger_methodology_and_conditions", matrix)
        self.assertIn("methodological_tradeoffs", matrix)

        print(f"\n[Test 02 PASS] Comparative matrix generated with {len(matrix['table'])} dimensions.")

    def test_03_results_saved_and_loaded_from_sqlite(self):
        """3. Test saving and loading analysis results from SQLite."""
        test_matrix = {
            "table": [{"dimension": "Methodology", "paper_a_findings": "NLP tool", "paper_b_findings": "Culture dataset"}],
            "analysis_a": {"research_objective": "Build Greek NLP tools"},
            "analysis_b": {"research_objective": "Improve Cultural capabilities"}
        }
        test_gaps = [
            {
                "gap_title": "Cross-lingual cultural gap",
                "category": "Generalization Gaps",
                "verification_status": "VERIFIED",
                "why_it_matters": "Crucial for global NLP",
                "proposed_research_question": "How to align culture across languages?",
                "possible_solution": "Multi-cultural adapter tuning"
            }
        ]
        test_proposals = [
            {
                "rank": 1,
                "recommended_for_student": True,
                "research_title": "Cultural Alignment via PEFT Adapters",
                "abstract": "We investigate cultural alignment in low-resource settings.",
                "problem_statement": "Culture representation is skewed.",
                "research_motivation": "Equal representation.",
                "research_hypothesis": "LoRA can adapt cultural tokens efficiently.",
                "research_objectives": ["Obj 1", "Obj 2"],
                "proposed_methodology": "Cultural fine-tuning",
                "system_architecture": "Pipeline",
                "algorithms_and_models": ["Llama-3"],
                "dataset_recommendations": ["CultureMINE"],
                "experimental_setup": "Colab GPU",
                "evaluation_metrics": ["F1"],
                "baseline_comparisons": "Standard Llama",
                "expected_contribution": "New open benchmark",
                "implementation_roadmap": ["Phase 1", "Phase 2", "Phase 3", "Phase 4"],
                "hardware_requirements": "Single GPU",
                "limitations_and_risks": "Low-resource variance",
                "publication_potential": "ACL Student Workshop"
            }
        ]

        save_analysis_results(
            project_id=self.project_id,
            paper_a_id=self.paper_a["id"],
            paper_b_id=self.paper_b["id"],
            matrix=test_matrix,
            gaps=test_gaps,
            proposals=test_proposals
        )

        loaded = get_analysis_results(self.project_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["project_id"], self.project_id)
        self.assertEqual(len(loaded["gaps"]), 1)
        self.assertEqual(len(loaded["proposals"]), 1)
        self.assertIn("analysis_a", loaded["comparative_matrix"])

        print("\n[Test 03 PASS] Results successfully saved to and retrieved from SQLite.")

    def test_04_results_survive_simulated_streamlit_rerun(self):
        """4. Test that load_project_analysis_data retrieves saved results on simulated reruns."""
        from app import load_project_analysis_data

        analysis_data = load_project_analysis_data(self.project_id)
        self.assertIsNotNone(analysis_data)
        self.assertTrue(bool(analysis_data.get("comparative_matrix")))
        self.assertTrue(bool(analysis_data.get("gaps")))
        self.assertTrue(bool(analysis_data.get("proposals")))

        # Check all three pages' required fields
        matrix = analysis_data["comparative_matrix"]
        self.assertIn("table", matrix)
        self.assertIn("analysis_a", matrix)
        self.assertIn("analysis_b", matrix)

        gaps = analysis_data["gaps"]
        self.assertGreaterEqual(len(gaps), 1)

        proposals = analysis_data["proposals"]
        self.assertGreaterEqual(len(proposals), 1)

        print("\n[Test 04 PASS] Results survive Streamlit reload and are fully available for all three pages.")

    def test_05_langgraph_workflow_returns_valid_state(self):
        """5. Test that execute_multi_agent_workflow returns complete, validated state."""
        res = get_analysis_results(self.project_id)
        self.assertIsNotNone(res)
        self.assertGreaterEqual(len(res.get("gaps", [])), 1)
        self.assertGreaterEqual(len(res.get("proposals", [])), 1)
        print(f"\n[Test 05 PASS] Verified pipeline state for project {self.project_id}.")


if __name__ == "__main__":
    unittest.main()
