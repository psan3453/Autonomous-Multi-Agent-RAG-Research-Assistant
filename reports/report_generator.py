"""
Academic Research Report Generator (.docx).
Synthesizes end-to-end scientific findings:
1. Executive Summary & Bibliographic Metadata
2. Detailed Independent 15-Point Extraction (Paper A & Paper B)
3. Comparative Matrix & Methodological Synthesis (Tradeoffs, Scope Check, Unexplored Frontiers)
4. Rigorous Research Gap Analysis (Critical Evidence Rule & Supplementary Literature Verification)
5. Three Prioritized Publication-Grade Research Directions & Recommended Capstone Project
6. Formal Academic References
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from config import REPORTS_DIR


def set_cell_background(cell, fill_hex: str):
    """Set background color of a table cell."""
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def generate_research_docx_report(
    project_topic: str = "",
    paper_a: Optional[Dict[str, Any]] = None,
    paper_b: Optional[Dict[str, Any]] = None,
    comparative_matrix: Optional[Dict[str, Any]] = None,
    gaps: Optional[List[Dict[str, Any]]] = None,
    proposals: Optional[List[Dict[str, Any]]] = None,
    output_filename: str = "comprehensive_research_report.docx",
    project_title: Optional[str] = None,
    topic: Optional[str] = None,
    analysis_a: Optional[Dict[str, Any]] = None,
    analysis_b: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """Generates an executive, academic publication-grade Word document (.docx)."""
    topic_text = project_topic or topic or project_title or "Autonomous Research Investigation"
    comparative_matrix = dict(comparative_matrix or {})
    if analysis_a and not comparative_matrix.get("analysis_a"):
        comparative_matrix["analysis_a"] = analysis_a
    if analysis_b and not comparative_matrix.get("analysis_b"):
        comparative_matrix["analysis_b"] = analysis_b
    paper_a = paper_a or {}
    paper_b = paper_b or {}
    gaps = gaps or []
    proposals = proposals or []

    doc = Document()

    # Page Margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    def add_heading_1(text: str):
        h = doc.add_heading(text, level=1)
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(6)
        if h.runs:
            r = h.runs[0]
            r.font.name = "Calibri"
            r.font.size = Pt(15)
            r.font.bold = True
            r.font.color.rgb = RGBColor(15, 23, 42)
        return h

    def add_heading_2(text: str):
        h = doc.add_heading(text, level=2)
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(4)
        if h.runs:
            r = h.runs[0]
            r.font.name = "Calibri"
            r.font.size = Pt(12)
            r.font.bold = True
            r.font.color.rgb = RGBColor(37, 99, 235)
        return h

    # Document Header Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    title_run = title_p.add_run("AUTONOMOUS LITERATURE REVIEW & RESEARCH GAP DISCOVERY REPORT")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(18)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(15, 23, 42)

    # Subtitle / Core Theme
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    sub_run = sub_p.add_run(f"Systematic Evaluation & Proposal Synthesis for Topic: {topic_text}")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(12)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(100, 116, 139)

    # 1. Executive Summary
    add_heading_1("1. EXECUTIVE SUMMARY & SURVEY SCOPE")
    p_exec = doc.add_paragraph()
    p_exec.add_run(
        f"This academic report presents an autonomous, multi-agent meta-analysis evaluating two foundational scientific manuscripts "
        f"addressing the research theme '{topic_text}'. The objective is to establish an empirical comparative matrix, "
        f"systematically uncover verified research gaps across 7 dimensions under the Critical Evidence Rule, and formulate 3 feasible "
        f"future research directions including a recommended university engineering capstone project."
    )

    # 2. Independent Paper Analysis
    add_heading_1("2. INDEPENDENT PAPER EXTRACTION (15 DIMENSIONS)")
    analysis_a = comparative_matrix.get("analysis_a", {})
    analysis_b = comparative_matrix.get("analysis_b", {})

    dim_labels = [
        ("research_objective", "1. Research Objective"),
        ("problem_statement", "2. Problem Statement"),
        ("research_questions", "3. Research Questions"),
        ("proposed_methodology", "4. Proposed Methodology"),
        ("model_architecture", "5. Model Architecture"),
        ("algorithms", "6. Algorithms & Formulations"),
        ("dataset_names", "7. Dataset Names"),
        ("dataset_sizes", "8. Dataset Sizes / Volume"),
        ("experimental_setup", "9. Experimental Setup & Hardware"),
        ("evaluation_metrics", "10. Evaluation Metrics"),
        ("actual_experimental_results", "11. Actual Experimental Results"),
        ("baseline_methods", "12. Baseline Methods"),
        ("strengths", "13. Key Strengths"),
        ("explicit_limitations", "14. Explicit Limitations"),
        ("future_research_directions", "15. Future Research Directions"),
    ]

    # Paper A Breakdown
    add_heading_2(f"2.1 Paper A: {paper_a.get('title', 'Paper A')}")
    p_a_meta = doc.add_paragraph()
    p_a_meta.add_run(f"Authors: {paper_a.get('authors', 'Unknown')} ({paper_a.get('year', 'N/A')})\n").bold = True
    if paper_a.get("doi"):
        p_a_meta.add_run(f"DOI / Source: https://doi.org/{paper_a.get('doi')}\n")
    if paper_a.get("url"):
        p_a_meta.add_run(f"Paper URL: {paper_a.get('url')}\n")

    for k, label in dim_labels:
        val = analysis_a.get(k, "Not reported in the paper")
        if isinstance(val, list):
            val = "; ".join(str(v) for v in val)
        p = doc.add_paragraph()
        p.add_run(f"{label}: ").bold = True
        p.add_run(str(val))

    # Paper B Breakdown
    add_heading_2(f"2.2 Paper B: {paper_b.get('title', 'Paper B')}")
    p_b_meta = doc.add_paragraph()
    p_b_meta.add_run(f"Authors: {paper_b.get('authors', 'Unknown')} ({paper_b.get('year', 'N/A')})\n").bold = True
    if paper_b.get("doi"):
        p_b_meta.add_run(f"DOI / Source: https://doi.org/{paper_b.get('doi')}\n")
    if paper_b.get("url"):
        p_b_meta.add_run(f"Paper URL: {paper_b.get('url')}\n")

    for k, label in dim_labels:
        val = analysis_b.get(k, "Not reported in the paper")
        if isinstance(val, list):
            val = "; ".join(str(v) for v in val)
        p = doc.add_paragraph()
        p.add_run(f"{label}: ").bold = True
        p.add_run(str(val))

    # 3. Comparative Analysis Matrix
    add_heading_1("3. COMPARATIVE ANALYSIS MATRIX & SYNTHESIS")

    # Scope Disparity Warning if applicable
    if comparative_matrix.get("are_problems_related") is False or comparative_matrix.get("scope_disparity_warning"):
        p_warn = doc.add_paragraph()
        warn_text = comparative_matrix.get(
            "scope_disparity_warning",
            "The surveyed papers investigate fundamentally distinct problem domains."
        )
        compat = comparative_matrix.get("problem_compatibility_score", 0.5)
        p_warn.add_run(f"⚠️ SCOPE DISPARITY WARNING (Domain Compatibility: {compat*100:.0f}%):\n").bold = True
        p_warn.add_run(warn_text)

    table_rows = comparative_matrix.get("table", [])
    if table_rows:
        table = doc.add_table(rows=1, cols=5)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Dimension"
        hdr_cells[1].text = f"Paper A: {paper_a.get('title', '')[:18]}..."
        hdr_cells[2].text = f"Paper B: {paper_b.get('title', '')[:18]}..."
        hdr_cells[3].text = "Similarities & Differences"
        hdr_cells[4].text = "Comparative Interpretation"

        for cell in hdr_cells:
            set_cell_background(cell, "0F172A")
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.size = Pt(9.0)

        for r in table_rows:
            row_cells = table.add_row().cells
            row_cells[0].text = str(r.get("dimension", ""))
            row_cells[1].text = str(r.get("paper_a_findings", r.get("paper_a_evidence", "")))
            row_cells[2].text = str(r.get("paper_b_findings", r.get("paper_b_evidence", "")))
            sim_diff = f"Similarities: {r.get('similarities', 'None')}\n\nDifferences: {r.get('differences', 'None')}"
            row_cells[3].text = sim_diff
            interp = f"{r.get('comparative_interpretation', '')}\n[Refs: {r.get('exact_page_references', r.get('source_page_references', 'N/A'))}]"
            row_cells[4].text = interp

            for cell in row_cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8.0)

    # Synthesis Breakdown
    add_heading_2("3.1 Methodological Trade-offs & Efficiency Synthesis")
    p_synth = doc.add_paragraph()
    if comparative_matrix.get("stronger_methodology_and_conditions"):
        p_synth.add_run("Stronger Methodology & Conditions: ").bold = True
        p_synth.add_run(f"{comparative_matrix.get('stronger_methodology_and_conditions')}\n\n")

    if comparative_matrix.get("methodological_tradeoffs"):
        p_synth.add_run("Architectural Trade-offs: ").bold = True
        p_synth.add_run(f"{comparative_matrix.get('methodological_tradeoffs')}\n\n")

    if comparative_matrix.get("computational_efficiency_comparison"):
        p_synth.add_run("Computational Efficiency: ").bold = True
        p_synth.add_run(f"{comparative_matrix.get('computational_efficiency_comparison')}\n\n")

    if comparative_matrix.get("unexplored_frontiers"):
        p_synth.add_run("Unexplored Research Frontiers: ").bold = True
        p_synth.add_run(f"{comparative_matrix.get('unexplored_frontiers')}\n\n")

    if comparative_matrix.get("comparative_summary"):
        p_synth.add_run("Executive Verdict: ").bold = True
        p_synth.add_run(f"{comparative_matrix.get('comparative_summary')}\n")

    # 4. Research Gaps
    add_heading_1("4. RIGOROUS RESEARCH GAP DISCOVERY")
    p_gaps_intro = doc.add_paragraph()
    p_gaps_intro.add_run(
        "By contrasting empirical evidence from both manuscripts under the Critical Evidence Rule, "
        "the system uncovered the following research gaps across 7 mandatory categories. "
        "Gaps lacking dual-paper verification are marked UNVERIFIED with missing evidence noted:"
    )

    for idx, gap in enumerate(gaps, 1):
        verif_status = gap.get("verification_status", "VERIFIED")
        category = gap.get("category", "General Gaps")
        title = gap.get("gap_title", "Untitled Gap")

        g_box = doc.add_paragraph()
        g_run = g_box.add_run(f"4.{idx} [{verif_status}] [{category}] {title}\n")
        g_run.bold = True
        g_run.font.size = Pt(11)
        g_run.font.color.rgb = RGBColor(15, 23, 42)

        p_det = doc.add_paragraph()
        p_det.add_run(f"• Explanation: {gap.get('gap_explanation', '')}\n")
        p_det.add_run(f"• Evidence (Paper A): {gap.get('evidence_paper_a')} [Page: {gap.get('exact_page_numbers', gap.get('exact_page_refs_a', 'N/A'))}]\n")
        p_det.add_run(f"• Evidence (Paper B): {gap.get('evidence_paper_b')} [Page: {gap.get('exact_page_numbers', gap.get('exact_page_refs_b', 'N/A'))}]\n")
        if gap.get("supporting_excerpts"):
            p_det.add_run(f"• Supporting Excerpts: \"{gap.get('supporting_excerpts')}\"\n")
        p_det.add_run(f"• Classification: {gap.get('classification', 'Inferred')} | Confidence: {gap.get('confidence_level', 'Medium')} ({gap.get('confidence_score', 0.8)})\n")
        p_det.add_run(f"• Confidence Justification: {gap.get('confidence_justification', gap.get('confidence_explanation', 'N/A'))}\n")
        p_det.add_run(f"• Why It Matters: {gap.get('why_it_matters')}\n")
        p_det.add_run(f"• Proposed Research Question: {gap.get('proposed_research_question')}\n")
        p_det.add_run(f"• Possible Solution: {gap.get('possible_solution', 'N/A')}\n")

        # Supplementary literature verification
        lit = gap.get("literature_verification", {})
        if lit:
            addressed = "Precedent Identified in External Literature" if lit.get("addressed_in_literature") else "Novel / Unresolved in Surveyed Indexes"
            p_det.add_run(f"• Supplementary Literature Check: {addressed}\n  {lit.get('synthesis', '')}\n")
            rel_papers = lit.get("related_papers", [])
            for rp in rel_papers[:2]:
                p_det.add_run(f"  - External Precedent: {rp.get('title')} ({rp.get('year', 'N/A')}) by {rp.get('authors', 'Unknown')}\n")

    # Scope disclaimer
    p_disc = doc.add_paragraph()
    p_disc.add_run("Note on Research Novelty: ").bold = True
    p_disc.add_run(
        "These research gaps reflect the comparative boundaries of the two analyzed papers and supplementary indexes; "
        "they represent targeted opportunities rather than exhaustive claims of global novelty."
    )

    # 5. Proposed Research Directions
    add_heading_1("5. PROPOSED FUTURE RESEARCH DIRECTIONS (18-POINT SPECIFICATION)")
    for prop in proposals:
        rank = prop.get("rank", 1)
        is_capstone = prop.get("recommended_for_student", False)
        rec_tag = " ★ [RECOMMENDED CAPSTONE PROJECT]" if is_capstone else ""
        add_heading_2(f"5.{rank} Direction #{rank}: {prop.get('research_title', 'Untitled Direction')}{rec_tag}")

        if is_capstone and prop.get("capstone_recommendation_rationale"):
            p_cap = doc.add_paragraph()
            p_cap.add_run("Capstone Selection Rationale: ").bold = True
            p_cap.add_run(f"{prop.get('capstone_recommendation_rationale')}\n")

        p_p = doc.add_paragraph()
        p_p.add_run("1. Abstract: ").bold = True
        p_p.add_run(f"{prop.get('abstract', 'Not provided')}\n\n")

        p_p.add_run("2. Problem Statement: ").bold = True
        p_p.add_run(f"{prop.get('problem_statement')}\n\n")

        p_p.add_run("3. Research Motivation: ").bold = True
        p_p.add_run(f"{prop.get('research_motivation')}\n\n")

        p_p.add_run("4. Research Hypothesis: ").bold = True
        p_p.add_run(f"{prop.get('research_hypothesis')}\n\n")

        objectives = prop.get("research_objectives", [])
        p_p.add_run("5. Research Objectives:\n").bold = True
        if isinstance(objectives, list):
            for obj in objectives:
                p_p.add_run(f"   • {obj}\n")
        else:
            p_p.add_run(f"   • {objectives}\n")
        p_p.add_run("\n")

        p_p.add_run("6. Proposed Methodology: ").bold = True
        p_p.add_run(f"{prop.get('proposed_methodology')}\n\n")

        p_p.add_run("7. System Architecture: ").bold = True
        p_p.add_run(f"{prop.get('system_architecture', prop.get('technical_architecture'))}\n\n")

        algos = prop.get("algorithms_and_models", [])
        p_p.add_run("8. Algorithms & Models: ").bold = True
        p_p.add_run(f"{', '.join(algos) if isinstance(algos, list) else str(algos)}\n\n")

        datasets = prop.get("dataset_recommendations", prop.get("dataset_suggestions", []))
        p_p.add_run("9. Target Datasets: ").bold = True
        p_p.add_run(f"{', '.join(datasets) if isinstance(datasets, list) else str(datasets)}\n\n")

        p_p.add_run("10. Experimental Setup: ").bold = True
        p_p.add_run(f"{prop.get('experimental_setup', prop.get('experimental_plan'))}\n\n")

        metrics = prop.get("evaluation_metrics", [])
        p_p.add_run("11. Evaluation Metrics: ").bold = True
        p_p.add_run(f"{', '.join(metrics) if isinstance(metrics, list) else str(metrics)}\n\n")

        p_p.add_run("12. Baseline Comparisons: ").bold = True
        p_p.add_run(f"{prop.get('baseline_comparisons', prop.get('baseline_comparison'))}\n\n")

        p_p.add_run("13. Expected Contribution: ").bold = True
        p_p.add_run(f"{prop.get('expected_contribution')}\n\n")

        p_p.add_run("14. Hardware Requirements: ").bold = True
        p_p.add_run(f"{prop.get('hardware_requirements')}\n\n")

        p_p.add_run("15. Limitations & Risks: ").bold = True
        p_p.add_run(f"{prop.get('limitations_and_risks', prop.get('risks_and_limitations'))}\n\n")

        p_p.add_run("16. Publication Potential: ").bold = True
        p_p.add_run(f"{prop.get('publication_potential', 'IEEE/ACM student track')}\n\n")

        # Multi-criteria ranking breakdown
        ranking = prop.get("ranking_breakdown", {})
        if ranking:
            p_p.add_run("17. Feasibility & Complexity Assessment:\n").bold = True
            for crit, score in ranking.items():
                p_p.add_run(f"   • {crit.replace('_', ' ').title()}: {score}\n")
            p_p.add_run("\n")

        steps = prop.get("implementation_roadmap", [])
        if steps:
            p_p.add_run("18. Implementation Roadmap:\n").bold = True
            for step in steps:
                doc.add_paragraph(f"  • {step}", style="List Bullet")

    # 6. References
    add_heading_1("6. REFERENCES & BIBLIOGRAPHY")
    p_ref = doc.add_paragraph()
    p_ref.add_run(f"[1] {paper_a.get('authors', 'Unknown Authors')}. \"{paper_a.get('title', 'Untitled')}\". ({paper_a.get('year', 'N/A')}). ")
    if paper_a.get("doi"):
        p_ref.add_run(f"DOI: {paper_a.get('doi')}. ")
    if paper_a.get("url"):
        p_ref.add_run(f"Available at: {paper_a.get('url')}")
    p_ref.add_run("\n\n")

    p_ref.add_run(f"[2] {paper_b.get('authors', 'Unknown Authors')}. \"{paper_b.get('title', 'Untitled')}\". ({paper_b.get('year', 'N/A')}). ")
    if paper_b.get("doi"):
        p_ref.add_run(f"DOI: {paper_b.get('doi')}. ")
    if paper_b.get("url"):
        p_ref.add_run(f"Available at: {paper_b.get('url')}")
    p_ref.add_run("\n\n")

    target_filepath = REPORTS_DIR / output_filename
    doc.save(str(target_filepath))
    return str(target_filepath)
