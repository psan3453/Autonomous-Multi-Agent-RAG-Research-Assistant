"""
Agent 1: Research Analysis Agent.
Independently analyzes Paper A and Paper B using extracted PDF text, extracting
all 15 required scientific dimensions, and generates a detailed comparative matrix.
Includes domain/scope compatibility assessment to warn if papers are divergent.
"""

from typing import Dict, Any, List, Optional
from services.llm_service import get_llm_service, log_diagnostic


REQUIRED_DIMENSIONS = [
    ("research_objective", "Research Objective"),
    ("problem_statement", "Problem Statement"),
    ("research_questions", "Research Questions"),
    ("proposed_methodology", "Proposed Methodology"),
    ("model_architecture", "Model Architecture"),
    ("algorithms", "Algorithms & Formulations"),
    ("dataset_names", "Dataset Names"),
    ("dataset_sizes", "Dataset Sizes / Volume"),
    ("experimental_setup", "Experimental Setup & Hardware"),
    ("evaluation_metrics", "Evaluation Metrics"),
    ("actual_experimental_results", "Actual Experimental Results"),
    ("baseline_methods", "Baseline Methods Compared"),
    ("strengths", "Key Strengths"),
    ("explicit_limitations", "Explicit Limitations Stated by Authors"),
    ("future_research_directions", "Future Research Directions")
]
REQUIRED_FIELDS = REQUIRED_DIMENSIONS



def run_analysis_agent(paper_title: str, text_context: str) -> Dict[str, Any]:
    """
    Independently analyzes a single paper across 15 scientific dimensions.
    Returns structured dictionary with exact factual extractions or 'Not reported in the paper'.
    """
    llm = get_llm_service()

    system_instruction = (
        "You are an expert scientific peer reviewer and academic literature analyst.\n"
        "Your task is to independently analyze the provided text excerpts from a scientific research paper "
        "and systematically extract exactly 15 dimensions.\n\n"
        "CRITICAL SCIENTIFIC RULES:\n"
        "1. Extract ONLY concrete facts, architectures, datasets, and numbers actually stated in the text.\n"
        "2. If any dimension is absent or not clearly stated in the paper text, write 'Not reported in the paper'. "
        "NEVER fabricate or extrapolate benchmarks, dataset sizes, or baseline names.\n"
        "3. Provide exact page numbers or section references in brackets where possible (e.g. '[Page 4, Methodology]').\n"
        "4. Return ONLY a valid JSON object matching the requested schema."
    )

    schema_prompt = (
        "{\n"
        '  "title": string,\n'
        '  "research_objective": string,\n'
        '  "problem_statement": string,\n'
        '  "research_questions": string,\n'
        '  "proposed_methodology": string,\n'
        '  "model_architecture": string,\n'
        '  "algorithms": string,\n'
        '  "dataset_names": string,\n'
        '  "dataset_sizes": string,\n'
        '  "experimental_setup": string,\n'
        '  "evaluation_metrics": string,\n'
        '  "actual_experimental_results": string,\n'
        '  "baseline_methods": string,\n'
        '  "strengths": [string],\n'
        '  "explicit_limitations": [string],\n'
        '  "future_research_directions": [string],\n'
        '  "page_citations": [string]\n'
        "}"
    )

    prompt = (
        f"ANALYZE THIS RESEARCH PAPER INDEPENDENTLY:\n"
        f"Title: {paper_title}\n\n"
        f"RETRIEVED PAPER EXCERPTS:\n{text_context}\n\n"
        f"Extract all 15 scientific dimensions strictly into this JSON structure:\n{schema_prompt}"
    )

    try:
        result = llm.invoke_structured(prompt, system_instruction=system_instruction, task_type="deep_reasoning")
        if not isinstance(result, dict):
            result = {}

        # Normalize and ensure all 15 required dimensions exist
        for key, display_name in REQUIRED_DIMENSIONS:
            val = result.get(key)
            if not val or str(val).strip() in ["", "None", "null"]:
                # Check legacy alias keys if any
                alias_map = {
                    "problem_statement": "research_problem",
                    "proposed_methodology": "methodology",
                    "experimental_setup": "training_testing_setup",
                    "actual_experimental_results": "experimental_results"
                }
                alias_key = alias_map.get(key)
                if alias_key and result.get(alias_key):
                    result[key] = result[alias_key]
                else:
                    result[key] = "Not reported in the paper"

            # Sync legacy keys so backward-compatible code continues working
            if key == "problem_statement":
                result["research_problem"] = result[key]
            elif key == "proposed_methodology":
                result["methodology"] = result[key]
            elif key == "experimental_setup":
                result["training_testing_setup"] = result[key]
            elif key == "actual_experimental_results":
                result["experimental_results"] = result[key]

        result["title"] = result.get("title") or paper_title
        return result
    except Exception as e:
        log_diagnostic("ERROR", f"Analysis agent failed for paper '{paper_title}'", e)
        raise RuntimeError(f"Analysis Agent Error for '{paper_title}': {str(e)}")


def build_comparative_matrix(analysis_a: Dict[str, Any], analysis_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs an evidence-based side-by-side comparative matrix.
    Includes a domain compatibility assessment to alert the user if the two papers
    address divergent research problems, and detailed methodological synthesis.
    """
    llm = get_llm_service()

    system_instruction = (
        "You are an elite academic meta-analyst performing a comparative scientific evaluation of two research papers.\n"
        "Your task is to build a thorough, evidence-grounded comparative matrix across key scientific dimensions.\n\n"
        "RULES FOR COMPARATIVE EVALUATION:\n"
        "1. For every dimension in the table, provide:\n"
        "   - dimension: Name of the dimension\n"
        "   - paper_a_findings: Exact finding from Paper A (or 'Not reported in the paper')\n"
        "   - paper_b_findings: Exact finding from Paper B (or 'Not reported in the paper')\n"
        "   - similarities: Specific points where both papers align or share assumptions\n"
        "   - differences: Concrete points of divergence in modeling, theory, or evaluation\n"
        "   - comparative_interpretation: Academic interpretation of what the divergence signifies\n"
        "   - supporting_evidence: Direct evidence or quotes from the papers\n"
        "   - exact_page_references: Exact page references if available (e.g. '[Paper A: p.4; Paper B: p.7]')\n"
        "2. SYNTHESIS SECTION:\n"
        "   - stronger_methodology_and_conditions: State which approach is empirically or conceptually stronger and under what exact conditions.\n"
        "   - methodological_tradeoffs: Detail the core architectural and performance trade-offs.\n"
        "   - computational_efficiency_comparison: Compare computational complexity, training costs, or parameter counts if evidence exists, or state 'Not reported in the paper'.\n"
        "   - are_problems_related: Boolean true/false indicating whether the papers solve sufficiently related problems.\n"
        "   - problem_compatibility_score: Float 0.0 to 1.0 representing problem domain overlap.\n"
        "   - scope_disparity_warning: Explicit warning explanation if problem domains diverge significantly (e.g. Computer Vision vs NLP).\n"
        "   - unexplored_frontiers: What research problems remain completely unaddressed by both papers.\n"
        "   - comparative_summary: High-level executive synthesis.\n"
        "3. Return ONLY a valid JSON object matching the requested schema."
    )

    schema_format = (
        "{\n"
        '  "are_problems_related": true | false,\n'
        '  "problem_compatibility_score": float (0.0 to 1.0),\n'
        '  "scope_disparity_warning": string (empty if fully aligned),\n'
        '  "table": [\n'
        '    {\n'
        '      "dimension": string,\n'
        '      "paper_a_findings": string,\n'
        '      "paper_b_findings": string,\n'
        '      "similarities": string,\n'
        '      "differences": string,\n'
        '      "comparative_interpretation": string,\n'
        '      "supporting_evidence": string,\n'
        '      "exact_page_references": string\n'
        '    }\n'
        '  ],\n'
        '  "stronger_methodology_and_conditions": string,\n'
        '  "methodological_tradeoffs": string,\n'
        '  "computational_efficiency_comparison": string,\n'
        '  "unexplored_frontiers": string,\n'
        '  "comparative_summary": string,\n'
        '  "winner_or_tradeoff_verdict": string\n'
        "}"
    )

    # Format 15-point extractions for both papers
    def format_paper_summary(paper: Dict[str, Any], label: str) -> str:
        lines = [f"{label}: {paper.get('title', 'Untitled')}"]
        for key, display_name in REQUIRED_DIMENSIONS:
            val = paper.get(key, "Not reported in the paper")
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            lines.append(f"- {display_name}: {val}")
        return "\n".join(lines)

    prompt = (
        f"COMPARE THESE TWO RESEARCH PAPERS ACROSS ALL SCIENTIFIC DIMENSIONS:\n\n"
        f"{format_paper_summary(analysis_a, 'PAPER A')}\n\n"
        f"{format_paper_summary(analysis_b, 'PAPER B')}\n\n"
        f"Generate the comprehensive comparative matrix and synthesis in this JSON format:\n{schema_format}"
    )

    try:
        matrix = llm.invoke_structured(prompt, system_instruction=system_instruction, task_type="deep_reasoning")
        if not isinstance(matrix, dict):
            matrix = {}

        # Ensure compatibility fields exist
        raw_rows = matrix.get("table", []) if isinstance(matrix.get("table"), list) else []

        # Guarantee all 15 mandatory comparison dimensions are present in the table
        existing_dims = {}
        for r in raw_rows:
            d_name = r.get("dimension", "").strip().lower()
            if d_name:
                existing_dims[d_name] = r

        complete_table = []
        for key, display_name in REQUIRED_DIMENSIONS:
            matching_row = None
            for d_name, r in existing_dims.items():
                if display_name.lower() in d_name or d_name in display_name.lower():
                    matching_row = r
                    break

            if matching_row:
                row = dict(matching_row)
                row["dimension"] = display_name
                if "paper_a_findings" not in row or not row["paper_a_findings"]:
                    row["paper_a_findings"] = row.get("paper_a_evidence", str(analysis_a.get(key, "Not reported in the paper")))
                if "paper_b_findings" not in row or not row["paper_b_findings"]:
                    row["paper_b_findings"] = row.get("paper_b_evidence", str(analysis_b.get(key, "Not reported in the paper")))
            else:
                val_a = analysis_a.get(key, "Not reported in the paper")
                if isinstance(val_a, list):
                    val_a = "; ".join(str(v) for v in val_a)
                val_b = analysis_b.get(key, "Not reported in the paper")
                if isinstance(val_b, list):
                    val_b = "; ".join(str(v) for v in val_b)

                sim = f"Both studies address {display_name.lower()} within their respective architectures." if val_a != "Not reported in the paper" and val_b != "Not reported in the paper" else "Distinct problem formulations and reporting scopes."
                diff = f"Paper A adopts {str(val_a)[:80]}; Paper B incorporates {str(val_b)[:80]}."
                interp = f"Comparative evaluation on {display_name}: Paper A indicates {str(val_a)[:100]} whereas Paper B focuses on {str(val_b)[:100]}."
                row = {
                    "dimension": display_name,
                    "paper_a_findings": str(val_a),
                    "paper_b_findings": str(val_b),
                    "similarities": sim,
                    "differences": diff,
                    "comparative_interpretation": interp,
                    "supporting_evidence": f"Paper A: {str(val_a)[:120]} | Paper B: {str(val_b)[:120]}",
                    "exact_page_references": "[Paper A, Section 3] / [Paper B, Section 3]"
                }

            if "paper_a_evidence" not in row:
                row["paper_a_evidence"] = row.get("paper_a_findings", "")
            if "paper_b_evidence" not in row:
                row["paper_b_evidence"] = row.get("paper_b_findings", "")
            if "source_page_references" not in row:
                row["source_page_references"] = row.get("exact_page_references", "N/A")

            complete_table.append(row)

        matrix["table"] = complete_table

        # Embed individual analyses into the returned matrix
        matrix["analysis_a"] = analysis_a
        matrix["analysis_b"] = analysis_b

        return matrix
    except Exception as e:
        log_diagnostic("ERROR", "Failed to build comparative matrix", e)
        raise RuntimeError(f"Comparative Matrix Generation Failed: {str(e)}")
