"""
Integration and Acceptance Test Suite for the Three Prioritized Modules:
1. Paper Comparison (15 dimensions, comparative matrix, scope check, tradeoffs)
2. Research Gap Discovery (7 categories, Critical Evidence Rule, supplementary literature)
3. Research Idea Generation (3 proposals, 18 fields, 6-criteria ranking, capstone project)
Includes SQLite persistence, Word docx report generation, and full LangGraph workflow.
"""

import sys
import os
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
from agents.gap_agent import (
    run_gap_discovery,
    validate_and_classify_gap,
    perform_literature_verification,
    MANDATORY_CATEGORIES,
    CLASSIFICATION_EXPLICIT,
    CLASSIFICATION_INFERRED,
    CLASSIFICATION_LITERATURE,
    CLASSIFICATION_UNVERIFIED
)
from agents.proposal_agent import run_proposal_generation
from graph.workflow import execute_multi_agent_workflow, retrieve_paper_context_summary
from services.vector_store import FAISSVectorStore
from reports.report_generator import generate_research_docx_report


class TestThreePriorities(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.project_id = "a59921d8-713a-46ff-9a45-7a0e5efb2162"
        cls.project = get_project(cls.project_id)
        assert cls.project is not None, f"Project {cls.project_id} must exist in research_assistant.db"

        selected = get_selected_papers(cls.project_id)
        assert len(selected) >= 2, "Project must have at least 2 selected papers"
        cls.paper_a = selected[0]
        cls.paper_b = selected[1]

        # Retrieve actual indexed PDF text from FAISS
        cls.vector_store = FAISSVectorStore(cls.project_id)
        cls.context_a = retrieve_paper_context_summary(cls.vector_store, cls.paper_a["id"], max_chars=3500)
        cls.context_b = retrieve_paper_context_summary(cls.vector_store, cls.paper_b["id"], max_chars=3500)

        # Store for downstream tests
        cls.analysis_a = {}
        cls.analysis_b = {}
        cls.comparative_matrix = {}
        cls.gaps = []
        cls.proposals = []

    def test_01_independent_paper_a_extraction(self):
        """Priority 1: Test independent 15-dimension analysis of Paper A."""
        analysis = run_analysis_agent(self.paper_a["title"], self.context_a)
        self.assertIsInstance(analysis, dict)
        self.assertIn("title", analysis)

        # Check all 15 required dimensions
        for key, display_name in REQUIRED_DIMENSIONS:
            self.assertIn(key, analysis, f"Dimension '{key}' must exist in analysis_a")
            val = analysis[key]
            self.assertTrue(len(str(val)) > 0, f"Value for '{key}' must not be empty")

        TestThreePriorities.analysis_a = analysis
        print(f"\n[Test 01 PASS] Paper A 15-Point Extraction: Objective='{analysis.get('research_objective')[:60]}...'")

    def test_02_independent_paper_b_extraction(self):
        """Priority 1: Test independent 15-dimension analysis of Paper B."""
        analysis = run_analysis_agent(self.paper_b["title"], self.context_b)
        self.assertIsInstance(analysis, dict)

        for key, display_name in REQUIRED_DIMENSIONS:
            self.assertIn(key, analysis, f"Dimension '{key}' must exist in analysis_b")
            val = analysis[key]
            self.assertTrue(len(str(val)) > 0, f"Value for '{key}' must not be empty")

        TestThreePriorities.analysis_b = analysis
        print(f"\n[Test 02 PASS] Paper B 15-Point Extraction: Objective='{analysis.get('research_objective')[:60]}...'")

    def test_03_comparative_matrix_and_scope_check(self):
        """Priority 1: Test comparative matrix generation and scope disparity detection."""
        matrix = build_comparative_matrix(self.analysis_a, self.analysis_b)
        self.assertIsInstance(matrix, dict)

        # Verify comparative table
        table = matrix.get("table", [])
        self.assertGreaterEqual(len(table), 1, "Comparative matrix must include dimension rows")
        first_row = table[0]
        self.assertIn("dimension", first_row)
        self.assertIn("similarities", first_row)
        self.assertIn("differences", first_row)
        self.assertIn("comparative_interpretation", first_row)

        # Verify synthesis fields
        self.assertIn("are_problems_related", matrix)
        self.assertIn("problem_compatibility_score", matrix)
        self.assertIn("stronger_methodology_and_conditions", matrix)
        self.assertIn("methodological_tradeoffs", matrix)
        self.assertIn("computational_efficiency_comparison", matrix)
        self.assertIn("unexplored_frontiers", matrix)

        # Embedded individual analyses
        self.assertIn("analysis_a", matrix)
        self.assertIn("analysis_b", matrix)

        TestThreePriorities.comparative_matrix = matrix
        print(f"\n[Test 03 PASS] Comparative Matrix Generated with {len(table)} dimensions. Scope Alignment: {matrix.get('are_problems_related')}")

    def test_04_gap_discovery_and_critical_evidence_rule(self):
        """Priority 2: Test research gap discovery across 7 categories and Critical Evidence Rule."""
        gaps_result = run_gap_discovery(
            self.project["topic"],
            self.analysis_a,
            self.analysis_b,
            self.context_a,
            self.context_b
        )
        self.assertIsInstance(gaps_result, dict)
        gaps = gaps_result.get("gaps", [])
        self.assertGreaterEqual(len(gaps), 1, "Must uncover at least 1 candidate gap")

        # Verify gap schema
        for g in gaps:
            self.assertIn("gap_title", g)
            self.assertIn("category", g)
            self.assertIn("verification_status", g)
            self.assertIn(g["verification_status"], ["VERIFIED", "UNVERIFIED"])
            self.assertIn("why_it_matters", g)
            self.assertIn("proposed_research_question", g)
            self.assertIn("possible_solution", g)

        # Test Critical Evidence Rule unit logic
        unverified_dummy = {
            "gap_title": "Fake Gap",
            "evidence_paper_a": "Not reported in the paper",
            "evidence_paper_b": "Valid evidence for paper B",
            "confidence_score": 0.8
        }
        validated = validate_and_classify_gap(unverified_dummy)
        self.assertEqual(validated["verification_status"], "UNVERIFIED")
        self.assertEqual(validated["classification"], CLASSIFICATION_UNVERIFIED)
        self.assertIn("missing", validated["missing_evidence_explanation"].lower())

        TestThreePriorities.gaps = gaps
        print(f"\n[Test 04 PASS] {len(gaps)} Research Gaps Discovered. Critical Evidence Rule successfully enforced.")

    def test_05_supplementary_literature_verification(self):
        """Priority 2: Test supplementary literature discovery via Semantic Scholar & arXiv."""
        query = "Parameter-Efficient Fine-Tuning LoRA instance segmentation"
        lit_res = perform_literature_verification(query)
        self.assertIsInstance(lit_res, dict)
        self.assertIn("searched_query", lit_res)
        self.assertIn("addressed_in_literature", lit_res)
        self.assertIn("related_papers", lit_res)
        self.assertIn("synthesis", lit_res)
        print(f"\n[Test 05 PASS] Literature search verification completed for: '{query}' -> Addressed: {lit_res.get('addressed_in_literature')}")

    def test_06_three_proposals_generation_18_fields(self):
        """Priority 3: Test formulation of 3 research proposals with all 18 dimensions and capstone project."""
        prop_res = run_proposal_generation(
            self.project["topic"],
            self.analysis_a,
            self.analysis_b,
            self.gaps
        )
        self.assertIsInstance(prop_res, dict)
        proposals = prop_res.get("proposals", [])
        self.assertEqual(len(proposals), 3, "Must generate exactly 3 research proposals")

        # Check required fields and capstone selection
        has_recommended = False
        required_18 = [
            "research_title", "abstract", "problem_statement", "research_motivation",
            "research_hypothesis", "research_objectives", "proposed_methodology",
            "system_architecture", "algorithms_and_models", "dataset_recommendations",
            "experimental_setup", "evaluation_metrics", "baseline_comparisons",
            "expected_contribution", "implementation_roadmap", "hardware_requirements",
            "limitations_and_risks", "publication_potential"
        ]

        for p in proposals:
            for field in required_18:
                self.assertIn(field, p, f"Field '{field}' missing from proposal '{p.get('research_title')}'")
            if p.get("recommended_for_student"):
                has_recommended = True
                self.assertTrue(len(p.get("capstone_recommendation_rationale", "")) > 0)

        self.assertTrue(has_recommended, "At least one proposal must be designated as recommended capstone project")

        TestThreePriorities.proposals = proposals
        print(f"\n[Test 06 PASS] 3 Proposals Generated with all 18 dimensions. Capstone project designated.")

    def test_07_sqlite_persistence(self):
        """Test persisting and reading all results from SQLite database."""
        save_analysis_results(
            project_id=self.project_id,
            paper_a_id=self.paper_a["id"],
            paper_b_id=self.paper_b["id"],
            matrix=self.comparative_matrix,
            gaps=self.gaps,
            proposals=self.proposals
        )

        loaded = get_analysis_results(self.project_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["project_id"], self.project_id)
        self.assertIn("analysis_a", loaded["comparative_matrix"])
        self.assertIn("analysis_b", loaded["comparative_matrix"])
        self.assertEqual(len(loaded["gaps"]), len(self.gaps))
        self.assertEqual(len(loaded["proposals"]), 3)
        print(f"\n[Test 07 PASS] Successfully persisted and verified {len(loaded['gaps'])} gaps and {len(loaded['proposals'])} proposals in SQLite.")

    def test_08_docx_report_generation(self):
        """Test generating an academic Word (.docx) report containing all three modules."""
        output_file = "test_three_priorities_report.docx"
        file_path = generate_research_docx_report(
            project_topic=self.project["topic"],
            paper_a=self.paper_a,
            paper_b=self.paper_b,
            comparative_matrix=self.comparative_matrix,
            gaps=self.gaps,
            proposals=self.proposals,
            output_filename=output_file
        )
        self.assertTrue(Path(file_path).exists(), "Generated DOCX file must exist")
        file_size = Path(file_path).stat().st_size
        self.assertGreater(file_size, 10000, "DOCX file must have substantial content")
        print(f"\n[Test 08 PASS] DOCX Report generated successfully: {file_path} ({file_size} bytes)")

    def test_09_full_langgraph_workflow_execution(self):
        """Test the end-to-end 7-node LangGraph StateGraph execution."""
        step_log = []
        def progress_cb(msg, pct):
            step_log.append((pct, msg))

        final_state = execute_multi_agent_workflow(
            project_id=self.project_id,
            topic=self.project["topic"],
            paper_a=self.paper_a,
            paper_b=self.paper_b,
            progress_callback=progress_cb
        )

        self.assertEqual(final_state.get("current_step"), "completed")
        self.assertIn("analysis_a", final_state)
        self.assertIn("analysis_b", final_state)
        self.assertIn("comparative_matrix", final_state)
        self.assertGreaterEqual(len(final_state.get("gaps", [])), 1)
        self.assertEqual(len(final_state.get("proposals", [])), 3)
        self.assertEqual(len(final_state.get("errors", [])), 0)
        self.assertGreaterEqual(len(step_log), 5)
        print(f"\n[Test 09 PASS] LangGraph 7-node workflow executed flawlessly. {len(step_log)} step callbacks delivered.")


if __name__ == "__main__":
    unittest.main()
