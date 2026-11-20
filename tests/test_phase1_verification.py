import sys
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
    get_selected_papers
)
from services.paper_search import search_real_papers, get_last_provider_status

def test_phase1():
    print("--- [TEST 1] Initializing DB ---")
    init_db()

    print("--- [TEST 2] Testing Search: 'image captioning using nlp' ---")
    papers = search_real_papers("image captioning using nlp", max_results=5)
    print(f"Total papers found: {len(papers)}")
    assert len(papers) > 0, "Expected at least 1 real paper"

    medical_keywords = ["covid", "clinical", "patient", "sers", "biomedical"]
    for p in papers:
        title_lower = p["title"].lower()
        print(f"  Found: {p['title']} ({p.get('year')}) [{p.get('source')}]")
        assert not any(k in title_lower for k in medical_keywords), f"Polluted paper title: {p['title']}"

    print("--- [TEST 3] Creating Project and Saving Papers ---")
    topic = "Image Captioning with Deep Learning and Transformers"
    proj_id = create_project(topic)
    assert proj_id is not None, "Failed to create project"
    print(f"Created project: {proj_id}")

    save_papers(proj_id, papers)
    retrieved = get_papers(proj_id)
    assert len(retrieved) == len(papers), f"Expected {len(papers)} papers, got {len(retrieved)}"
    print(f"Retrieved {len(retrieved)} papers from SQLite for project {proj_id}")

    print("--- [TEST 4] Testing Paper Selection Persistence ---")
    # Select exactly two papers
    set_paper_selected(proj_id, retrieved[0]["id"], True)
    set_paper_selected(proj_id, retrieved[1]["id"], True)

    selected = get_selected_papers(proj_id)
    assert len(selected) == 2, f"Expected 2 selected papers, got {len(selected)}"
    print(f"Selected papers verified: '{selected[0]['title'][:30]}' and '{selected[1]['title'][:30]}'")

    print("--- [TEST 5] Testing Project Isolation ---")
    proj_b_id = create_project("Suspicious Human Activity Recognition")
    papers_b = get_papers(proj_b_id)
    assert len(papers_b) == 0, f"Expected 0 papers in fresh project, got {len(papers_b)}"
    print("Project isolation verified: fresh project has 0 papers.")

    print("\n✅ ALL PHASE 1 ACCEPTANCE TESTS PASSED!")

if __name__ == "__main__":
    test_phase1()
