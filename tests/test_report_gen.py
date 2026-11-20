import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import init_db, get_project, get_selected_papers, get_analysis_results
from reports.report_generator import generate_research_docx_report

init_db()
project_id = "a59921d8-713a-46ff-9a45-7a0e5efb2162"
project = get_project(project_id)
selected = get_selected_papers(project_id)
assert len(selected) >= 2, "Project must have 2 selected papers"

analysis_data = get_analysis_results(project_id)
assert analysis_data is not None, "Project must have analysis data"

matrix = analysis_data.get("comparative_matrix", {})
gaps = analysis_data.get("gaps", [])
proposals = analysis_data.get("proposals", [])

print(f"Generating report for project: {project['name']}")
out_file = "test_verification_report.docx"
doc_path = generate_research_docx_report(
    project_title=f"Autonomous RAG Research Report: {project['topic']}",
    topic=project["topic"],
    paper_a=selected[0],
    paper_b=selected[1],
    analysis_a=matrix.get("analysis_a", {}),
    analysis_b=matrix.get("analysis_b", {}),
    comparative_matrix=matrix,
    gaps=gaps,
    proposals=proposals,
    output_filename=out_file
)

assert os.path.exists(doc_path), f"Report file must exist at {doc_path}"
file_size = os.path.getsize(doc_path)
print(f"Report successfully created: {doc_path} ({file_size} bytes)")
assert file_size > 5000, f"Report file size ({file_size} bytes) is suspiciously small"

# Clean up test file
try:
    os.remove(doc_path)
    print("Test file cleanup successful.")
except Exception:
    pass

print("ALL REPORT GENERATION CHECKS PASSED.")
