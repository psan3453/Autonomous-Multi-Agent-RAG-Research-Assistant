import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_projects, get_selected_papers, set_paper_selected, get_papers

projects = get_projects()
for p in projects:
    sel = get_selected_papers(p["id"])
    papers = get_papers(p["id"])
    print(f"[{p['id']}] '{p['name']}' -> Total papers: {len(papers)}, Selected: {len(sel)}")
