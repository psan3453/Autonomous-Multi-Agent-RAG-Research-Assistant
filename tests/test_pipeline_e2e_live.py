import sys
import os
from pathlib import Path
sys.path.insert(0, ".")

from database.db import get_projects, get_papers, get_analysis_results
from services.vector_store import FAISSVectorStore
from graph.workflow import execute_multi_agent_workflow
from reports.report_generator import generate_research_docx_report

def test_pipeline_e2e():
    print("--- [TEST 1] Finding Valid Project with Two Selected Papers & Vector Index ---")
    projects = get_projects()
    target_proj = None
    target_papers = None

    for p in projects:
        vs = FAISSVectorStore(p["id"])
        if vs.exists() and vs.load() and len(vs.chunks) >= 2:
            papers = get_papers(p["id"])
            if len(papers) >= 2:
                target_proj = p
                target_papers = papers[:2]
                break

    assert target_proj is not None, "No suitable project with indexed papers found"
    proj_id = target_proj["id"]
    topic = target_proj["topic"]
    paper_a, paper_b = target_papers[0], target_papers[1]
    print(f"Target Project: {proj_id} ('{topic[:40]}')")
    print(f"Paper A: {paper_a['title'][:40]}")
    print(f"Paper B: {paper_b['title'][:40]}")

    progress_log = []
    def progress_callback(msg, pct):
        progress_log.append((msg, pct))
        print(f"Progress [{pct*100:.0f}%]: {msg}")

    print("\n--- [TEST 2] Executing LangGraph Multi-Agent Workflow ---")
    final_state = execute_multi_agent_workflow(
        project_id=proj_id,
        topic=topic,
        paper_a=paper_a,
        paper_b=paper_b,
        progress_callback=progress_callback
    )

    print("\n--- [TEST 3] Validating Phase 4: Comparative Matrix & 15 Dimensions ---")
    analysis_a = final_state.get("analysis_a", {})
    analysis_b = final_state.get("analysis_b", {})
    matrix = final_state.get("comparative_matrix", {})

    assert len(analysis_a) > 0, "Paper A analysis is empty"
    assert len(analysis_b) > 0, "Paper B analysis is empty"
    print(f"Paper A analysis fields: {len(analysis_a)}")
    print(f"Paper B analysis fields: {len(analysis_b)}")

    # Verify key dimensions exist
    for key in ["research_objective", "proposed_methodology", "evaluation_metrics", "explicit_limitations"]:
        assert key in analysis_a, f"Missing {key} in Paper A"
        assert key in analysis_b, f"Missing {key} in Paper B"

    table = matrix.get("table", [])
    assert len(table) > 0, "Comparative matrix table has 0 rows"
    print(f"Comparative Matrix contains {len(table)} evaluated dimensions.")
    sample_row = table[0]
    print(f"Sample Dimension: '{sample_row.get('dimension')}' | Paper A: '{sample_row.get('paper_a_findings')[:40]}...'")

    print("\n--- [TEST 4] Validating Phase 5: Research Gaps (Critical Evidence Rule) ---")
    gaps = final_state.get("gaps", [])
    assert len(gaps) > 0, "0 research gaps generated"
    print(f"Total gaps identified: {len(gaps)}")

    for idx, g in enumerate(gaps):
        assert "gap_title" in g, f"Gap {idx} missing gap_title"
        assert "category" in g, f"Gap {idx} missing category"
        assert "verification_status" in g, f"Gap {idx} missing verification_status"
        assert g["verification_status"] in ["VERIFIED", "UNVERIFIED"], f"Invalid status: {g['verification_status']}"
        print(f"  Gap #{idx+1} [{g.get('category')}]: {g.get('gap_title')[:45]} -> {g['verification_status']}")

    print("\n--- [TEST 5] Validating Phase 6: Research Idea Generation (18 Dims & Feasibility Rubric) ---")
    proposals = final_state.get("proposals", [])
    assert len(proposals) == 3, f"Expected exactly 3 proposals, got {len(proposals)}"
    print(f"Total proposals synthesized: {len(proposals)}")

    capstone_count = sum(1 for p in proposals if p.get("recommended_for_student"))
    assert capstone_count == 1, f"Expected exactly 1 recommended capstone proposal, got {capstone_count}"

    for idx, p in enumerate(proposals):
        assert "research_title" in p or "proposed_title" in p
        assert "problem_statement" in p
        assert "research_hypothesis" in p
        assert "ranking_breakdown" in p
        breakdown = p.get("ranking_breakdown", {})
        assert len(breakdown) >= 4, f"Incomplete ranking breakdown for proposal {idx}"
        print(f"  Proposal #{p.get('rank', idx+1)}: {p.get('research_title', p.get('proposed_title', ''))[:45]} (Capstone: {p.get('recommended_for_student')})")

    print("\n--- [TEST 6] Validating SQLite Persistence ---")
    db_results = get_analysis_results(proj_id)
    assert db_results is not None, "Failed to retrieve results from SQLite"
    assert db_results["comparative_matrix"] is not None
    assert len(db_results["gaps"]) == len(gaps)
    assert len(db_results["proposals"]) == len(proposals)
    print("Database persistence synchronized successfully.")

    print("\n--- [TEST 7] Validating Phase 8: Docx Report Generation ---")
    out_file = f"Test_Report_{proj_id[:8]}.docx"
    doc_path = generate_research_docx_report(
        project_title=f"Autonomous Research Report: {topic}",
        topic=topic,
        paper_a=paper_a,
        paper_b=paper_b,
        analysis_a=analysis_a,
        analysis_b=analysis_b,
        comparative_matrix=matrix,
        gaps=gaps,
        proposals=proposals,
        output_filename=out_file
    )
    assert os.path.exists(doc_path), f"Report not created at {doc_path}"
    doc_size = os.path.getsize(doc_path)
    assert doc_size > 10000, f"Generated docx file suspiciously small: {doc_size} bytes"
    print(f"Docx report generated successfully at {doc_path} ({doc_size} bytes).")

    print("\n✅ ALL END-TO-END PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    test_pipeline_e2e()
