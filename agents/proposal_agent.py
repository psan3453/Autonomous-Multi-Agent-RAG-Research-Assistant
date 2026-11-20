"""
Agent 3: Research Proposal Agent.
Generates 3 concrete, publication-grade research directions directly grounded
in the validated research gaps.

Every proposal includes all 18 required academic components:
1. Research title
2. Abstract
3. Problem statement
4. Research motivation
5. Research hypothesis
6. Research objectives
7. Proposed methodology
8. System architecture
9. Algorithms and models
10. Dataset recommendations
11. Experimental setup
12. Evaluation metrics
13. Baseline comparisons
14. Expected contribution
15. Implementation roadmap
16. Hardware requirements
17. Limitations and risks
18. Publication potential

Ranked across 6 student-centric criteria, highlighting one recommended capstone project.
"""

from typing import Dict, Any, List, Optional
from services.llm_service import get_llm_service, log_diagnostic


def run_proposal_generation(
    topic: str,
    analysis_a: Dict[str, Any],
    analysis_b: Dict[str, Any],
    gaps: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate 3 distinct, actionable research proposals based on validated gaps.
    Includes all 18 academic dimensions and explicit capstone project ranking.
    """
    llm = get_llm_service()

    system_instruction = (
        "You are a Distinguished AI Research Director and Academic Capstone Advisor.\n"
        "Your task is to formulate THREE distinct, scientifically rigorous, publication-grade research directions.\n\n"
        "CRITICAL SCIENTIFIC RULES:\n"
        "1. Every idea must directly address one or more of the validated research gaps from the comparison.\n"
        "2. Do NOT present hypothetical results as completed experiments. "
        "Explicitly formulate expectations as formal hypotheses (e.g. 'We hypothesize that...').\n"
        "3. Every proposal MUST contain all 18 structured fields:\n"
        "   1. research_title, 2. abstract, 3. problem_statement, 4. research_motivation, 5. research_hypothesis, "
        "   6. research_objectives, 7. proposed_methodology, 8. system_architecture, 9. algorithms_and_models, "
        "   10. dataset_recommendations, 11. experimental_setup, 12. evaluation_metrics, 13. baseline_comparisons, "
        "   14. expected_contribution, 15. implementation_roadmap, 16. hardware_requirements, "
        "   17. limitations_and_risks, 18. publication_potential.\n"
        "4. RANKING & CAPSTONE SELECTION:\n"
        "   Rank proposals based on: student feasibility, research contribution, technical complexity, "
        "   dataset availability, hardware requirements, and evaluation possibilities.\n"
        "   Select EXACTLY ONE project with recommended_for_student: true and provide an explicit "
        "   capstone_recommendation_rationale explaining why it is optimal for a final-year engineering student.\n"
        "5. Return ONLY a valid JSON object matching the requested schema."
    )

    schema_format = (
        "{\n"
        '  "proposals": [\n'
        '    {\n'
        '      "rank": 1,\n'
        '      "recommended_for_student": true | false,\n'
        '      "capstone_recommendation_rationale": string,\n'
        '      "research_title": string,\n'
        '      "abstract": string,\n'
        '      "problem_statement": string,\n'
        '      "research_motivation": string,\n'
        '      "research_hypothesis": string,\n'
        '      "research_objectives": [string],\n'
        '      "proposed_methodology": string,\n'
        '      "system_architecture": string,\n'
        '      "algorithms_and_models": [string],\n'
        '      "dataset_recommendations": [string],\n'
        '      "experimental_setup": string,\n'
        '      "evaluation_metrics": [string],\n'
        '      "baseline_comparisons": string,\n'
        '      "expected_contribution": string,\n'
        '      "implementation_roadmap": [\n'
        '        "Phase 1 (Weeks 1-3): ...",\n'
        '        "Phase 2 (Weeks 4-7): ...",\n'
        '        "Phase 3 (Weeks 8-11): ...",\n'
        '        "Phase 4 (Weeks 12-14): ..."\n'
        '      ],\n'
        '      "hardware_requirements": string,\n'
        '      "limitations_and_risks": string,\n'
        '      "publication_potential": string,\n'
        '      "ranking_breakdown": {\n'
        '        "student_feasibility": "High" | "Medium" | "Low",\n'
        '        "research_contribution": "High" | "Medium" | "Low",\n'
        '        "technical_complexity": "High" | "Medium" | "Low",\n'
        '        "dataset_availability": "High" | "Medium" | "Low",\n'
        '        "hardware_feasibility": "High" | "Medium" | "Low",\n'
        '        "evaluation_possibility": "High" | "Medium" | "Low"\n'
        '      }\n'
        '    }\n'
        '  ],\n'
        '  "ranking_rationale": string\n'
        "}"
    )

    # Format validated gaps
    gaps_context = []
    for idx, g in enumerate(gaps[:7], 1):
        gaps_context.append(
            f"Gap #{idx} [{g.get('category')}]: {g.get('gap_title')}\n"
            f"- Status: {g.get('verification_status')} ({g.get('classification')})\n"
            f"- Explanation: {g.get('gap_explanation', '')[:200]}\n"
            f"- Possible Solution: {g.get('possible_solution', 'N/A')}\n"
            f"- Proposed Question: {g.get('proposed_research_question', 'N/A')}\n"
        )
    formatted_gaps = "\n".join(gaps_context)

    prompt = (
        f"CORE RESEARCH TOPIC: {topic}\n\n"
        f"PAPER A: {analysis_a.get('title')}\n"
        f"- Methodology: {analysis_a.get('proposed_methodology')}\n"
        f"- Datasets: {analysis_a.get('dataset_names')}\n"
        f"- Limitations: {analysis_a.get('explicit_limitations')}\n\n"
        f"PAPER B: {analysis_b.get('title')}\n"
        f"- Methodology: {analysis_b.get('proposed_methodology')}\n"
        f"- Datasets: {analysis_b.get('dataset_names')}\n"
        f"- Limitations: {analysis_b.get('explicit_limitations')}\n\n"
        f"VALIDATED RESEARCH GAPS:\n{formatted_gaps}\n\n"
        f"Formulate THREE distinct research proposals matching this JSON structure:\n{schema_format}"
    )

    try:
        result = llm.invoke_structured(prompt, system_instruction=system_instruction, task_type="deep_reasoning")
        if not isinstance(result, dict):
            result = {}

        proposals = result.get("proposals", [])
        if not isinstance(proposals, list):
            proposals = []

        # Guarantee exactly 3 proposals
        while len(proposals) < 3:
            rank_num = len(proposals) + 1
            proposals.append({
                "rank": rank_num,
                "research_title": f"Benchmarking and Unified Evaluation of {topic} (Direction {rank_num})",
                "abstract": f"This research direction proposes an empirical evaluation framework addressing cross-cutting limitations identified between surveyed methodologies in {topic}.",
                "problem_statement": f"Lack of unified reproducible benchmark comparing operational trade-offs in {topic}.",
                "research_motivation": f"Bridging the methodological boundary between surveyed techniques to guide engineering deployment.",
                "research_hypothesis": f"We hypothesize that hybrid multi-objective optimization achieves higher robustness than standalone baselines in {topic}.",
                "research_objectives": [
                    f"Develop standardized benchmark suite for {topic}",
                    f"Quantify latency vs accuracy trade-offs across realistic operational conditions",
                    f"Evaluate generalization across unseen evaluation splits"
                ],
                "proposed_methodology": f"Constructing modular pipeline integrating strengths of both surveyed architectures with automated validation.",
                "system_architecture": f"Three-tier modular architecture: Ingestion Layer, Core Processing Engine, and Evaluation/Telemetry Module.",
                "algorithms_and_models": ["Transformer-based backbone", "Cross-entropy loss with adaptive regularization", "Greedy search with beam-search fallback"],
                "dataset_recommendations": ["Public domain benchmark dataset", "Synthetic stress-testing corpus"],
                "experimental_setup": "Single GPU workstation (RTX 3060 / 4060 or Google Colab T4) running PyTorch 2.x on Ubuntu.",
                "evaluation_metrics": ["F1-score / Accuracy", "Inference latency (ms)", "Peak VRAM utilization (MB)"],
                "baseline_comparisons": "Direct empirical comparison against Paper A and Paper B implementations.",
                "expected_contribution": f"First open-source standardized reproducibility benchmark evaluating frontier tradeoffs in {topic}.",
                "implementation_roadmap": [
                    "Phase 1 (Weeks 1-3): Literature baseline replication and dataset preparation",
                    "Phase 2 (Weeks 4-7): Modular architecture prototyping and component integration",
                    "Phase 3 (Weeks 8-11): Rigorous empirical experimentation and baseline benchmarking",
                    "Phase 4 (Weeks 12-14): Error analysis, ablation study, and research paper drafting"
                ],
                "hardware_requirements": "Consumer-grade GPU (8GB VRAM) or free cloud instance (Google Colab T4).",
                "limitations_and_risks": "Potential sensitivity to training hyper-parameters; mitigated through grid search with early stopping.",
                "publication_potential": "Targeting national/international student symposium or IEEE/ACM workshop track."
            })

        proposals = proposals[:3]

        # Ensure at least one proposal is designated as recommended capstone
        has_rec = any(p.get("recommended_for_student") for p in proposals)
        if not has_rec and proposals:
            proposals[0]["recommended_for_student"] = True
            if not proposals[0].get("capstone_recommendation_rationale"):
                proposals[0]["capstone_recommendation_rationale"] = (
                    "Optimal balance between novelty and feasibility on standard student computing infrastructure."
                )

        # Normalize backward-compatible keys and guarantee all 18 fields and 6 criteria exist
        for idx, p in enumerate(proposals, 1):
            p["rank"] = idx
            if not p.get("ranking_breakdown") or not isinstance(p.get("ranking_breakdown"), dict):
                p["ranking_breakdown"] = {}

            rb = p["ranking_breakdown"]
            rb.setdefault("student_feasibility", "High" if idx == 1 else "Medium")
            rb.setdefault("research_contribution", "High")
            rb.setdefault("technical_complexity", "Medium")
            rb.setdefault("dataset_availability", "High")
            rb.setdefault("hardware_feasibility", "High" if idx == 1 else "Medium")
            rb.setdefault("evaluation_possibility", "High")

            # Guarantee all 18 required fields are populated
            p.setdefault("research_title", p.get("title", f"Research Direction #{idx}: {topic}"))
            p.setdefault("abstract", f"Empirical investigation addressing core research gaps in {topic}.")
            p.setdefault("problem_statement", f"Unaddressed methodological tradeoffs in {topic}.")
            p.setdefault("research_motivation", f"Advancing reproducibility and empirical rigor in {topic}.")
            p.setdefault("research_hypothesis", f"We hypothesize that unified benchmarking yields measurable improvements in {topic}.")
            p.setdefault("research_objectives", ["Analyze baseline", "Implement proposed approach", "Validate empirically"])
            p.setdefault("proposed_methodology", "Hybrid comparative implementation with ablation verification.")
            p.setdefault("system_architecture", "Modular pipeline: Data Loader, Processing Engine, Evaluation Harness.")
            p.setdefault("algorithms_and_models", ["Baseline model", "Modified proposed architecture"])
            p.setdefault("dataset_recommendations", ["Public benchmark dataset"])
            p.setdefault("experimental_setup", "Python 3.11, PyTorch, consumer GPU or Google Colab.")
            p.setdefault("evaluation_metrics", ["Accuracy / F1", "Latency", "Resource footprint"])
            p.setdefault("baseline_comparisons", "Evaluated against surveyed literature baselines.")
            p.setdefault("expected_contribution", "Reproducible experimental insights and validated benchmark.")
            p.setdefault("implementation_roadmap", [
                "Phase 1 (Weeks 1-3): Setup & baselines",
                "Phase 2 (Weeks 4-7): Implementation",
                "Phase 3 (Weeks 8-11): Evaluation",
                "Phase 4 (Weeks 12-14): Documentation"
            ])
            p.setdefault("hardware_requirements", "Standard laptop or Google Colab free tier.")
            p.setdefault("limitations_and_risks", "Resource constraints; mitigated by subset sampling.")
            p.setdefault("publication_potential", "Conference workshop or student research track.")

            p["technical_architecture"] = p.get("system_architecture") or p.get("technical_architecture", "")
            p["dataset_suggestions"] = p.get("dataset_recommendations") or p.get("dataset_suggestions", [])
            p["baseline_comparison"] = p.get("baseline_comparisons") or p.get("baseline_comparison", "")
            p["risks_and_limitations"] = p.get("limitations_and_risks") or p.get("risks_and_limitations", "")
            p["feasibility"] = rb.get("student_feasibility", "High")

        result["proposals"] = proposals
        return result
    except Exception as e:
        log_diagnostic("ERROR", "Proposal agent generation failed", e)
        raise RuntimeError(f"Proposal Agent Error: {str(e)}")
