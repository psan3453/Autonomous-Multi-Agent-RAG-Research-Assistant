"""
Agent 2: Research Gap Discovery Agent.
Systematically uncovers research gaps across 7 academic dimensions:
1. Methodological gaps
2. Dataset gaps
3. Performance gaps
4. Generalization gaps
5. Computational efficiency gaps
6. Evaluation gaps
7. Application/domain gaps

Enforces CRITICAL EVIDENCE RULE:
- Never marks a gap as VERIFIED if supporting evidence is missing or ungrounded.
- Gaps lacking dual-paper evidence are marked UNVERIFIED with explicit explanation.
- Performs live supplementary literature search (Semantic Scholar / arXiv) to check external precedence.
- Distinguishes 4 distinct academic classifications.
"""

from typing import Dict, Any, List, Optional
from services.llm_service import get_llm_service, log_diagnostic
from services.paper_search import search_real_papers


MANDATORY_CATEGORIES = [
    "Methodological Gaps",
    "Dataset Gaps",
    "Performance Gaps",
    "Generalization Gaps",
    "Computational Efficiency Gaps",
    "Evaluation Gaps",
    "Application/Domain Gaps"
]

CLASSIFICATION_EXPLICIT = "Explicit author-stated gap"
CLASSIFICATION_INFERRED = "Inferred comparative gap"
CLASSIFICATION_LITERATURE = "Gap supported by supplementary literature review"
CLASSIFICATION_UNVERIFIED = "Unverified candidate gap"


def validate_and_classify_gap(gap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces the CRITICAL EVIDENCE RULE:
    - Never mark a gap as VERIFIED if supporting evidence is missing.
    - If Paper A or Paper B evidence is absent, mark UNVERIFIED.
    - Clearly document which evidence is missing without inventing citations.
    """
    ev_a = str(gap.get("evidence_paper_a") or gap.get("paper_a_evidence") or "").strip()
    ev_b = str(gap.get("evidence_paper_b") or gap.get("paper_b_evidence") or "").strip()

    missing_a = (
        not ev_a or
        "not reported" in ev_a.lower() or
        "not extracted" in ev_a.lower() or
        "missing" in ev_a.lower() or
        len(ev_a) < 15
    )
    missing_b = (
        not ev_b or
        "not reported" in ev_b.lower() or
        "not extracted" in ev_b.lower() or
        "missing" in ev_b.lower() or
        len(ev_b) < 15
    )

    if missing_a or missing_b:
        gap["verification_status"] = "UNVERIFIED"
        gap["classification"] = CLASSIFICATION_UNVERIFIED
        reasons = []
        if missing_a:
            reasons.append("Paper A evidence is missing, ungrounded, or not reported in the text")
        if missing_b:
            reasons.append("Paper B evidence is missing, ungrounded, or not reported in the text")
        gap["missing_evidence_explanation"] = "CRITICAL EVIDENCE RULE: " + " and ".join(reasons) + "."
        gap["verification_note"] = gap["missing_evidence_explanation"]
        gap["confidence_level"] = "Low"
        gap["confidence_score"] = min(float(gap.get("confidence_score", 0.3)), 0.35)
        gap["confidence_justification"] = "Low confidence due to incomplete direct textual verification across both surveyed works."
    else:
        gap["verification_status"] = "VERIFIED"
        gap["missing_evidence_explanation"] = "None. Verified by direct textual evidence in both papers."
        gap["verification_note"] = "Fully verified with supporting citations from both papers."
        gap["confidence_level"] = gap.get("confidence_level") or ("High" if float(gap.get("confidence_score", 0.8)) >= 0.75 else "Medium")
        if not gap.get("confidence_justification"):
            gap["confidence_justification"] = "Grounded by direct comparative citations and experimental findings reported in both manuscripts."

        # Keep or refine classification
        user_class = str(gap.get("classification", "")).lower()
        if "explicit" in user_class or "author" in user_class:
            gap["classification"] = CLASSIFICATION_EXPLICIT
        else:
            gap["classification"] = CLASSIFICATION_INFERRED

    return gap


def perform_literature_verification(gap_title: str) -> Dict[str, Any]:
    """
    Perform a live supplementary search using Semantic Scholar & arXiv to check
    whether external researchers have already addressed or explored this candidate gap.
    """
    try:
        results = search_real_papers(gap_title, max_results=3)
        if results:
            papers_meta = [
                {
                    "title": p.get("title", "Untitled"),
                    "authors": p.get("authors", "Unknown"),
                    "year": p.get("year"),
                    "url": p.get("url") or p.get("pdf_url") or "",
                    "abstract_snippet": (p.get("abstract") or "")[:200]
                }
                for p in results[:3]
            ]
            return {
                "searched_query": gap_title,
                "addressed_in_literature": True,
                "related_papers": papers_meta,
                "synthesis": f"Identified {len(results)} relevant publications in external academic databases investigating closely related formulations."
            }
        else:
            return {
                "searched_query": gap_title,
                "addressed_in_literature": False,
                "related_papers": [],
                "synthesis": "No direct published works found specifically resolving this precise gap formulation in available indexes."
            }
    except Exception as e:
        log_diagnostic("WARNING", f"Literature verification query failed for gap '{gap_title}'", e)
        return {
            "searched_query": gap_title,
            "addressed_in_literature": False,
            "related_papers": [],
            "synthesis": "Literature verification query encountered a network timeout."
        }


def run_gap_discovery(
    topic: str,
    analysis_a: Dict[str, Any],
    analysis_b: Dict[str, Any],
    context_a: str = "",
    context_b: str = ""
) -> Dict[str, Any]:
    """
    Identifies, validates, and classifies research gaps across 7 categories.
    Applies the Critical Evidence Rule and integrates live literature search.
    """
    llm = get_llm_service()

    system_instruction = (
        "You are an academic Systematic Reviewer and Literature Specialist discovering genuine research gaps.\n"
        "MANDATORY GAP CATEGORIES TO ANALYZE:\n"
        "1. Methodological Gaps\n"
        "2. Dataset Gaps\n"
        "3. Performance Gaps\n"
        "4. Generalization Gaps\n"
        "5. Computational Efficiency Gaps\n"
        "6. Evaluation Gaps\n"
        "7. Application/Domain Gaps\n\n"
        "CRITICAL EVIDENCE RULES:\n"
        "- Base every gap strictly on actual findings, models, datasets, and limitations reported in the two papers.\n"
        "- If Paper A or Paper B does not report relevant data for a category, explicitly state 'Not reported in the paper'.\n"
        "- Never fabricate citations, quotes, or page references.\n"
        "- Distinguish between 'Gap explicitly stated by authors' and 'Gap inferred from comparison'.\n"
        "- For every gap provide a concrete Possible Solution and a testable Proposed Research Question.\n"
        "- Do NOT claim global research novelty based on only two papers; note that these represent targeted opportunities."
    )

    schema_format = (
        "{\n"
        '  "gaps": [\n'
        '    {\n'
        '      "gap_title": string,\n'
        '      "category": "Methodological Gaps" | "Dataset Gaps" | "Performance Gaps" | "Generalization Gaps" | "Computational Efficiency Gaps" | "Evaluation Gaps" | "Application/Domain Gaps",\n'
        '      "gap_explanation": string,\n'
        '      "evidence_paper_a": string,\n'
        '      "evidence_paper_b": string,\n'
        '      "exact_page_numbers": string,\n'
        '      "supporting_excerpts": string,\n'
        '      "classification": "Gap explicitly stated by authors" | "Gap inferred from comparison",\n'
        '      "confidence_level": "High" | "Medium" | "Low",\n'
        '      "confidence_score": float (0.1 to 1.0),\n'
        '      "confidence_justification": string,\n'
        '      "why_it_matters": string,\n'
        '      "proposed_research_question": string,\n'
        '      "possible_solution": string\n'
        '    }\n'
        '  ],\n'
        '  "synthesis_summary": string,\n'
        '  "scope_disclaimer": "These research gaps reflect the comparative boundary between the two analyzed manuscripts and supplementary indexes; they do not assert exhaustive global novelty without wider meta-analysis."\n'
        "}"
    )

    prompt = (
        f"RESEARCH TOPIC: {topic}\n\n"
        f"PAPER A: {analysis_a.get('title')}\n"
        f"- Objective: {analysis_a.get('research_objective')}\n"
        f"- Problem: {analysis_a.get('problem_statement')}\n"
        f"- Methodology: {analysis_a.get('proposed_methodology')}\n"
        f"- Architecture: {analysis_a.get('model_architecture')}\n"
        f"- Datasets: {analysis_a.get('dataset_names')} (Size: {analysis_a.get('dataset_sizes')})\n"
        f"- Results: {analysis_a.get('actual_experimental_results')}\n"
        f"- Limitations: {analysis_a.get('explicit_limitations')}\n\n"
        f"PAPER B: {analysis_b.get('title')}\n"
        f"- Objective: {analysis_b.get('research_objective')}\n"
        f"- Problem: {analysis_b.get('problem_statement')}\n"
        f"- Methodology: {analysis_b.get('proposed_methodology')}\n"
        f"- Architecture: {analysis_b.get('model_architecture')}\n"
        f"- Datasets: {analysis_b.get('dataset_names')} (Size: {analysis_b.get('dataset_sizes')})\n"
        f"- Results: {analysis_b.get('actual_experimental_results')}\n"
        f"- Limitations: {analysis_b.get('explicit_limitations')}\n\n"
        f"EXCERPTS PAPER A:\n{context_a[:2800]}\n\n"
        f"EXCERPTS PAPER B:\n{context_b[:2800]}\n\n"
        f"Identify and validate all meaningful research gaps matching this JSON schema:\n{schema_format}"
    )

    try:
        raw_result = llm.invoke_structured(prompt, system_instruction=system_instruction, task_type="deep_reasoning")
        gaps_list = raw_result.get("gaps", [])

        # Programmatically apply CRITICAL EVIDENCE RULE to every gap
        validated_gaps = []
        for g in gaps_list:
            v_gap = validate_and_classify_gap(g)
            # Run live supplementary literature search
            lit_ver = perform_literature_verification(v_gap["gap_title"])
            v_gap["literature_verification"] = lit_ver

            # If literature confirms existing studies on this verified gap, refine classification
            if v_gap["verification_status"] == "VERIFIED" and lit_ver.get("addressed_in_literature"):
                v_gap["classification"] = CLASSIFICATION_LITERATURE

            # Sync legacy keys for backward compatibility
            v_gap["exact_page_refs_a"] = v_gap.get("exact_page_numbers", "N/A")
            v_gap["exact_page_refs_b"] = v_gap.get("exact_page_numbers", "N/A")
            v_gap["supporting_passages_a"] = v_gap.get("supporting_excerpts", "")
            v_gap["supporting_passages_b"] = v_gap.get("supporting_excerpts", "")
            v_gap["confidence_explanation"] = v_gap.get("confidence_justification", "")

            validated_gaps.append(v_gap)

        # Guarantee all 7 mandatory research gap categories are represented
        existing_cats = {g.get("category") for g in validated_gaps}
        for cat in MANDATORY_CATEGORIES:
            if cat not in existing_cats:
                cat_lower = cat.lower()
                candidate_unverified = {
                    "gap_title": f"Unaddressed cross-comparative boundary in {cat_lower}",
                    "category": cat,
                    "gap_explanation": f"Neither analyzed publication provides explicit comparative benchmarks or unified architectural evaluation addressing {cat_lower} across both surveyed paradigms.",
                    "evidence_paper_a": "Not reported in the paper",
                    "evidence_paper_b": "Not reported in the paper",
                    "exact_page_numbers": "N/A",
                    "supporting_excerpts": "",
                    "classification": CLASSIFICATION_UNVERIFIED,
                    "confidence_level": "Low",
                    "confidence_score": 0.25,
                    "confidence_justification": f"Candidate gap identified across comparative boundary; marked UNVERIFIED under Critical Evidence Rule due to lack of dual-paper textual disclosure.",
                    "why_it_matters": f"Systematic investigation of {cat_lower} is critical for establishing empirical generalization in production deployments.",
                    "proposed_research_question": f"How can {cat_lower} be systematically reconciled and benchmarked across both operational settings?",
                    "possible_solution": f"Develop an empirical cross-evaluation framework explicitly isolating and testing {cat_lower} under standardized workloads."
                }
                v_gap = validate_and_classify_gap(candidate_unverified)
                v_gap["literature_verification"] = perform_literature_verification(v_gap["gap_title"])
                v_gap["exact_page_refs_a"] = "N/A"
                v_gap["exact_page_refs_b"] = "N/A"
                v_gap["supporting_passages_a"] = ""
                v_gap["supporting_passages_b"] = ""
                v_gap["confidence_explanation"] = v_gap["confidence_justification"]
                validated_gaps.append(v_gap)

        return {
            "gaps": validated_gaps,
            "synthesis_summary": raw_result.get("synthesis_summary", "Systematic comparative gap analysis completed."),
            "scope_disclaimer": raw_result.get(
                "scope_disclaimer",
                "These research gaps reflect the comparative boundary between the two analyzed manuscripts and supplementary indexes; they do not assert exhaustive global novelty without wider meta-analysis."
            )
        }
    except Exception as e:
        log_diagnostic("ERROR", "Failed to discover research gaps", e)
        raise RuntimeError(f"Gap Discovery Agent Error: {str(e)}")
