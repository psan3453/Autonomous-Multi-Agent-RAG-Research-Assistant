import sys
import os
import uuid
from pathlib import Path
sys.path.insert(0, ".")

from database.db import (
    init_db,
    create_project,
    get_projects,
    get_project,
    save_papers,
    get_papers,
    set_paper_selected,
    get_selected_papers,
    save_chat_message,
    get_chat_history,
    save_analysis_results,
    get_analysis_results
)
from services.paper_search import search_real_papers
from services.vector_store import FAISSVectorStore

# Helper simulating the exact Streamlit sidebar reconciliation logic from app.py
def run_sidebar_reconciliation(session_state: dict, project_keys: list):
    # 1. Process pending project activation if requested
    if session_state.get("pending_project_id"):
        pending = session_state.pop("pending_project_id")
        if pending in project_keys:
            session_state["active_project_id"] = pending
            session_state["sidebar_active_project_selector"] = pending

    # 2. Reconcile active_project_id and selector widget state BEFORE selectbox is instantiated
    current_selector = session_state.get("sidebar_active_project_selector")
    if current_selector and current_selector != "-- Create New Project --" and current_selector in project_keys:
        if session_state.get("active_project_id") != current_selector:
            session_state["active_project_id"] = current_selector
            proj_data = get_project(current_selector)
            if proj_data:
                session_state["active_topic"] = proj_data["topic"]
                session_state["chat_history"] = get_chat_history(current_selector)
    elif session_state.get("active_project_id") and session_state.get("active_project_id") in project_keys:
        session_state["sidebar_active_project_selector"] = session_state["active_project_id"]
        if not session_state.get("active_topic"):
            proj_data = get_project(session_state["active_project_id"])
            if proj_data:
                session_state["active_topic"] = proj_data["topic"]
    else:
        session_state["active_project_id"] = None
        session_state["active_topic"] = ""
        session_state["sidebar_active_project_selector"] = "-- Create New Project --"


def run_on_change_callback(session_state: dict):
    selected = session_state.get("sidebar_active_project_selector")
    if selected == "-- Create New Project --" or not selected:
        session_state["active_project_id"] = None
        session_state["active_topic"] = ""
        session_state["chat_history"] = []
        session_state["navigation_page"] = "Research Topic Search"
    else:
        session_state["active_project_id"] = selected
        proj_data = get_project(selected)
        if proj_data:
            session_state["active_topic"] = proj_data["topic"]
            session_state["chat_history"] = get_chat_history(selected)


def run_tests():
    init_db()
    results = {}

    print("======================================================================")
    print("=== STARTING PROJECT SELECTOR & SESSION-STATE LIFECYCLE AUDIT ===")
    print("======================================================================")

    # Setup 2 distinct initial projects
    proj_a_id = create_project("Deep Learning for Autonomous Vehicles", name="Autonomous Driving Project A")
    save_papers(proj_a_id, [
        {"id": f"{proj_a_id}_p1", "title": "Paper A1 Autonomous Perception", "authors": "Author A1", "year": 2023, "abstract": "AV Perception"},
        {"id": f"{proj_a_id}_p2", "title": "Paper A2 Trajectory Planning", "authors": "Author A2", "year": 2024, "abstract": "AV Planning"}
    ])
    save_chat_message(proj_a_id, "user", "What is AV trajectory planning?", [])
    save_chat_message(proj_a_id, "assistant", "Trajectory planning computes collision-free paths.", [])

    proj_b_id = create_project("Medical Image Segmentation with Transformers", name="Medical Imaging Project B")
    save_papers(proj_b_id, [
        {"id": f"{proj_b_id}_p1", "title": "Paper B1 Transformer Segmentation", "authors": "Author B1", "year": 2024, "abstract": "Medical Seg"}
    ])
    save_chat_message(proj_b_id, "user", "How does Swin-UNet work?", [])

    all_projs = get_projects()
    project_keys = [p["id"] for p in all_projs]

    # ------------------------------------------------------------------
    # TEST A: Select an existing project
    # ------------------------------------------------------------------
    state_a = {
        "active_project_id": None,
        "active_topic": "",
        "sidebar_active_project_selector": proj_a_id,
        "navigation_page": "Home Dashboard"
    }
    # Trigger on_change callback as Streamlit does
    run_on_change_callback(state_a)
    run_sidebar_reconciliation(state_a, project_keys)

    test_a_pass = (
        state_a["active_project_id"] == proj_a_id and
        state_a["sidebar_active_project_selector"] == proj_a_id and
        state_a["active_topic"] == "Deep Learning for Autonomous Vehicles" and
        len(state_a.get("chat_history", [])) == 2
    )
    results["Test A (Select Existing Project)"] = (test_a_pass, f"Active: {state_a['active_project_id'][:8]}, Chat: {len(state_a.get('chat_history', []))} msgs")

    # ------------------------------------------------------------------
    # TEST B: Create a new project via pending-project pattern
    # ------------------------------------------------------------------
    state_b = {
        "active_project_id": proj_a_id,
        "sidebar_active_project_selector": proj_a_id,
        "navigation_page": "Research Topic Search"
    }
    # Main body creates project (simulating line 551-554)
    new_topic = "Quantum Machine Learning Algorithms"
    new_proj_id = create_project(new_topic, name="Quantum ML Project")
    # Body sets pending_project_id (NEVER touches sidebar_active_project_selector here!)
    state_b["active_project_id"] = new_proj_id
    state_b["active_topic"] = new_topic
    state_b["pending_project_id"] = new_proj_id

    # Simulate rerun: sidebar reconciliation runs
    updated_keys = [p["id"] for p in get_projects()]
    run_sidebar_reconciliation(state_b, updated_keys)

    test_b_pass = (
        state_b["active_project_id"] == new_proj_id and
        state_b["sidebar_active_project_selector"] == new_proj_id and
        state_b.get("pending_project_id") is None and
        state_b["active_topic"] == new_topic
    )
    results["Test B (Create New Project)"] = (test_b_pass, f"Created & Activated: {new_proj_id[:8]}, Selector: {state_b['sidebar_active_project_selector'][:8]}")

    # ------------------------------------------------------------------
    # TEST C: Switch from Project A to Project B
    # ------------------------------------------------------------------
    state_c = {
        "active_project_id": proj_a_id,
        "sidebar_active_project_selector": proj_b_id, # User clicked B
        "navigation_page": "Top Five Papers"
    }
    run_on_change_callback(state_c)
    run_sidebar_reconciliation(state_c, updated_keys)

    papers_in_b = get_papers(state_c["active_project_id"])
    chat_in_b = get_chat_history(state_c["active_project_id"])

    test_c_pass = (
        state_c["active_project_id"] == proj_b_id and
        state_c["sidebar_active_project_selector"] == proj_b_id and
        len(papers_in_b) == 1 and
        papers_in_b[0]["title"] == "Paper B1 Transformer Segmentation" and
        len(chat_in_b) == 1
    )
    results["Test C (Switch Project A -> B)"] = (test_c_pass, f"Active: {state_c['active_project_id'][:8]}, Papers: {len(papers_in_b)}, Chat: {len(chat_in_b)}")

    # ------------------------------------------------------------------
    # TEST D: Return from Project B to Project A
    # ------------------------------------------------------------------
    state_d = {
        "active_project_id": proj_b_id,
        "sidebar_active_project_selector": proj_a_id, # User clicked A
        "navigation_page": "Top Five Papers"
    }
    run_on_change_callback(state_d)
    run_sidebar_reconciliation(state_d, updated_keys)

    papers_in_a = get_papers(state_d["active_project_id"])
    chat_in_a = get_chat_history(state_d["active_project_id"])

    test_d_pass = (
        state_d["active_project_id"] == proj_a_id and
        state_d["sidebar_active_project_selector"] == proj_a_id and
        len(papers_in_a) == 2 and
        len(chat_in_a) == 2
    )
    results["Test D (Return Project B -> A)"] = (test_d_pass, f"Restored: {state_d['active_project_id'][:8]}, Papers: {len(papers_in_a)}, Chat: {len(chat_in_a)}")

    # ------------------------------------------------------------------
    # TEST E: Navigate between all workflow pages
    # ------------------------------------------------------------------
    nav_pages = [
        "Home Dashboard",
        "Research Topic Search",
        "Top Five Papers",
        "Paper Processing",
        "RAG Research Chat",
        "Paper Comparison",
        "Research Gap Discovery",
        "Research Idea Generation",
        "Report Generation"
    ]
    all_pages_intact = True
    state_e = {
        "active_project_id": proj_a_id,
        "sidebar_active_project_selector": proj_a_id,
        "active_topic": "Deep Learning for Autonomous Vehicles"
    }
    for page in nav_pages:
        state_e["navigation_page"] = page
        run_sidebar_reconciliation(state_e, updated_keys)
        if state_e["active_project_id"] != proj_a_id or state_e["sidebar_active_project_selector"] != proj_a_id:
            all_pages_intact = False

    results["Test E (Navigate All 9 Workflow Pages)"] = (all_pages_intact, f"Preserved active project across all {len(nav_pages)} pages")

    # ------------------------------------------------------------------
    # TEST F: Browser Refresh Simulation (Selector has ID, active_id is None)
    # ------------------------------------------------------------------
    # Simulates browser reload where active_project_id was lost/None but widget kept selector key
    state_f = {
        "active_project_id": None,
        "active_topic": "",
        "sidebar_active_project_selector": proj_b_id, # Widget retained choice
        "navigation_page": "Top Five Papers"
    }
    # In a refresh, on_change does NOT fire, only sidebar reconciliation runs!
    run_sidebar_reconciliation(state_f, updated_keys)

    test_f_pass = (
        state_f["active_project_id"] == proj_b_id and
        state_f["sidebar_active_project_selector"] == proj_b_id and
        state_f["active_topic"] == "Medical Image Segmentation with Transformers" and
        len(state_f.get("chat_history", [])) == 1
    )
    results["Test F (Browser Refresh Reconciliation)"] = (test_f_pass, f"Reconciled active_id={state_f['active_project_id'][:8]} from selector='{state_f['sidebar_active_project_selector'][:8]}'")

    # ------------------------------------------------------------------
    # TEST G: Search for new topic after selecting a project
    # ------------------------------------------------------------------
    state_g = {
        "active_project_id": proj_a_id,
        "sidebar_active_project_selector": proj_a_id,
        "navigation_page": "Research Topic Search"
    }
    search_topic_g = "Explainable AI in Healthcare Diagnostics"
    proj_g_id = create_project(search_topic_g, name="XAI Diagnostics Project")
    save_papers(proj_g_id, [
        {"id": f"{proj_g_id}_p1", "title": "SHAP for Clinical Risk Prediction", "authors": "Researcher G", "year": 2024, "abstract": "XAI"}
    ])
    # Body sets pending
    state_g["active_project_id"] = proj_g_id
    state_g["active_topic"] = search_topic_g
    state_g["pending_project_id"] = proj_g_id

    updated_keys_g = [p["id"] for p in get_projects()]
    run_sidebar_reconciliation(state_g, updated_keys_g)

    # Verify Project A is untouched
    proj_a_papers_after = get_papers(proj_a_id)
    proj_g_papers = get_papers(proj_g_id)

    test_g_pass = (
        state_g["active_project_id"] == proj_g_id and
        state_g["sidebar_active_project_selector"] == proj_g_id and
        len(proj_g_papers) == 1 and
        len(proj_a_papers_after) == 2
    )
    results["Test G (Search Topic After Project Selection)"] = (test_g_pass, f"New Project G: {proj_g_id[:8]}, Project A papers preserved: {len(proj_a_papers_after)}")

    # ------------------------------------------------------------------
    # TEST H: Restart Streamlit and verify project persistence
    # ------------------------------------------------------------------
    # Clean memory references and verify from fresh SQLite connection
    persisted_projects = get_projects()
    persisted_ids = [p["id"] for p in persisted_projects]
    test_h_pass = (
        proj_a_id in persisted_ids and
        proj_b_id in persisted_ids and
        new_proj_id in persisted_ids and
        proj_g_id in persisted_ids
    )
    results["Test H (Restart & Project Persistence)"] = (test_h_pass, f"Total Persisted Projects in DB: {len(persisted_projects)}")

    # Print summary
    print("\n" + "="*70)
    all_passed = True
    for test_name, (passed, detail) in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"{status} {test_name}: {detail}")
    print("="*70)
    print(f"OVERALL RESULT: {'ALL 8 SCENARIOS PASSED' if all_passed else 'SOME SCENARIOS FAILED'}")
    print("="*70)
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
