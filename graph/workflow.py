"""
LangGraph Multi-Agent Workflow Orchestrator.
Coordinates the end-to-end scientific research pipeline:
1. Independent Paper Analysis (Extracts 15 dimensions per paper)
2. Comparative Matrix Generation (Side-by-side evaluation + Scope Compatibility)
3. Research Gap Discovery (Identifies gaps across 7 categories)
4. Gap Evidence Validation (Enforces Critical Evidence Rule)
5. Supplementary Literature Verification (Queries Semantic Scholar & arXiv)
6. Research Proposal Generation (3 prioritized, publication-grade proposals)
7. Save Results to SQLite
"""

import json
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from langgraph.graph import StateGraph, END

import config
from graph.state import ResearchState
from agents.analysis_agent import run_analysis_agent, build_comparative_matrix
from agents.gap_agent import (
    run_gap_discovery,
    validate_and_classify_gap,
    perform_literature_verification,
    CLASSIFICATION_LITERATURE
)
from agents.proposal_agent import run_proposal_generation
from services.vector_store import FAISSVectorStore
from services.llm_service import log_diagnostic
from database.db import save_analysis_results, update_project_status, get_analysis_results

CHECKPOINTS_DIR = getattr(config, "STORAGE_DIR", Path(__file__).resolve().parent.parent / "storage") / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_checkpoint_path(project_id: str, paper_a_id: str, paper_b_id: str) -> Path:
    safe_a = paper_a_id.replace("/", "_").replace("\\", "_")
    safe_b = paper_b_id.replace("/", "_").replace("\\", "_")
    return CHECKPOINTS_DIR / f"workflow_{project_id}_{safe_a}_{safe_b}.json"


def _save_workflow_checkpoint(project_id: str, paper_a_id: str, paper_b_id: str, data: Dict[str, Any]):
    try:
        path = _get_checkpoint_path(project_id, paper_a_id, paper_b_id)
        existing = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        log_diagnostic("WARNING", f"Failed to save workflow checkpoint: {e}")


def _load_workflow_checkpoint(project_id: str, paper_a_id: str, paper_b_id: str) -> Dict[str, Any]:
    try:
        path = _get_checkpoint_path(project_id, paper_a_id, paper_b_id)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_diagnostic("WARNING", f"Failed to load workflow checkpoint: {e}")
    return {}


def retrieve_paper_context_summary(
    vector_store: FAISSVectorStore,
    paper_id: str,
    max_chars: int = 8000
) -> str:
    """
    Extracts representative chunks from key academic sections for LLM agent reasoning.
    Ensures broad coverage across Abstract, Introduction, Methodology, Results, and Limitations.
    """
    if not vector_store.chunks:
        vector_store.load()

    chunks = vector_store.get_all_chunks_for_paper(paper_id)

    # Fuzzy match if exact ID differs by punctuation
    if not chunks:
        clean_id = paper_id.replace(".", "_").replace("-", "_")
        chunks = [
            c for c in vector_store.chunks 
            if c.get("paper_id") == clean_id or paper_id in c.get("chunk_id", "")
        ]

    if not chunks:
        return "No extracted PDF text available in vector index for this paper."

    priority_sections = [
        "abstract", "introduction", "methodology", "method", "architecture",
        "system", "experiments", "experimental", "results", "discussion",
        "limitations", "conclusion"
    ]

    prioritized_chunks = []
    other_chunks = []

    for c in chunks:
        sec = (c.get("section") or "").lower()
        if any(p in sec for p in priority_sections):
            prioritized_chunks.append(c)
        else:
            other_chunks.append(c)

    ordered = prioritized_chunks + other_chunks
    text_blocks = []
    current_len = 0

    for c in ordered:
        snippet = f"[Page {c.get('page_number', '?')}, Section: {c.get('section', 'General')}]:\n{c.get('content', '')}"
        text_blocks.append(snippet)
        current_len += len(snippet)
        if current_len >= max_chars:
            break

    return "\n\n".join(text_blocks)


def node_independent_analysis(state: ResearchState) -> Dict[str, Any]:
    """Node 1: Independently analyze Paper A & Paper B across 15 scientific dimensions."""
    paper_a = state["paper_a"]
    paper_b = state["paper_b"]
    project_id = state["project_id"]

    vector_store = FAISSVectorStore(project_id)
    context_a = state.get("context_a") or retrieve_paper_context_summary(vector_store, paper_a["id"])
    context_b = state.get("context_b") or retrieve_paper_context_summary(vector_store, paper_b["id"])

    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    analysis_a = state.get("analysis_a")
    analysis_b = state.get("analysis_b")

    # Analyze Paper A if not already present
    if not (analysis_a and isinstance(analysis_a, dict) and len(analysis_a) >= 10):
        try:
            analysis_a = run_analysis_agent(paper_a.get("title", "Paper A"), context_a)
            diagnostics["analysis_a_status"] = "SUCCESS"
        except Exception as e:
            log_diagnostic("ERROR", f"Independent analysis failed on Paper A ({paper_a.get('id')})", e)
            errors.append(f"Analysis Agent Error (Paper A): {str(e)}")
            diagnostics["analysis_a_status"] = f"FAILED: {str(e)}"
            raise RuntimeError(f"Analysis Agent Error (Paper A): {str(e)}")
    else:
        diagnostics["analysis_a_status"] = "CACHED"

    # Analyze Paper B if not already present
    if not (analysis_b and isinstance(analysis_b, dict) and len(analysis_b) >= 10):
        try:
            analysis_b = run_analysis_agent(paper_b.get("title", "Paper B"), context_b)
            diagnostics["analysis_b_status"] = "SUCCESS"
        except Exception as e:
            log_diagnostic("ERROR", f"Independent analysis failed on Paper B ({paper_b.get('id')})", e)
            errors.append(f"Analysis Agent Error (Paper B): {str(e)}")
            diagnostics["analysis_b_status"] = f"FAILED: {str(e)}"
            raise RuntimeError(f"Analysis Agent Error (Paper B): {str(e)}")
    else:
        diagnostics["analysis_b_status"] = "CACHED"

    # Checkpoint intermediate analysis results immediately
    _save_workflow_checkpoint(project_id, paper_a["id"], paper_b["id"], {
        "analysis_a": analysis_a,
        "analysis_b": analysis_b,
        "context_a": context_a,
        "context_b": context_b,
    })

    return {
        "context_a": context_a,
        "context_b": context_b,
        "analysis_a": analysis_a,
        "analysis_b": analysis_b,
        "current_step": "papers_analyzed",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_comparative_matrix(state: ResearchState) -> Dict[str, Any]:
    """Node 2: Generate the side-by-side comparative matrix and scope compatibility analysis."""
    paper_a = state["paper_a"]
    paper_b = state["paper_b"]
    project_id = state["project_id"]
    analysis_a = state["analysis_a"]
    analysis_b = state["analysis_b"]
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    comparative_matrix = state.get("comparative_matrix")

    if not (comparative_matrix and isinstance(comparative_matrix, dict) and len(comparative_matrix.get("table", [])) >= 3):
        try:
            comparative_matrix = build_comparative_matrix(analysis_a, analysis_b)
            diagnostics["matrix_status"] = "SUCCESS"
        except Exception as e:
            log_diagnostic("ERROR", "Comparative matrix build failed", e)
            errors.append(f"Comparative Matrix Error: {str(e)}")
            diagnostics["matrix_status"] = f"FAILED: {str(e)}"
            raise RuntimeError(f"Comparative Matrix Error: {str(e)}")
    else:
        comparative_matrix["analysis_a"] = analysis_a
        comparative_matrix["analysis_b"] = analysis_b
        diagnostics["matrix_status"] = "CACHED"

    _save_workflow_checkpoint(project_id, paper_a["id"], paper_b["id"], {
        "comparative_matrix": comparative_matrix
    })

    return {
        "comparative_matrix": comparative_matrix,
        "current_step": "matrix_generated",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_gap_discovery(state: ResearchState) -> Dict[str, Any]:
    """Node 3: Identify candidate research gaps across 7 categories."""
    paper_a = state["paper_a"]
    paper_b = state["paper_b"]
    project_id = state["project_id"]
    topic = state["topic"]
    analysis_a = state["analysis_a"]
    analysis_b = state["analysis_b"]
    context_a = state.get("context_a", "")
    context_b = state.get("context_b", "")
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    raw_gaps = state.get("raw_gaps")
    summary = state.get("gaps_summary", "")

    if not (raw_gaps and isinstance(raw_gaps, list) and len(raw_gaps) >= 1):
        try:
            gaps_result = run_gap_discovery(topic, analysis_a, analysis_b, context_a, context_b)
            raw_gaps = gaps_result.get("gaps", [])
            summary = gaps_result.get("synthesis_summary", "")
            diagnostics["gap_discovery_status"] = f"SUCCESS ({len(raw_gaps)} candidate gaps discovered)"
        except Exception as e:
            log_diagnostic("ERROR", "Gap Discovery failed", e)
            errors.append(f"Gap Discovery Agent Error: {str(e)}")
            diagnostics["gap_discovery_status"] = f"FAILED: {str(e)}"
            raise RuntimeError(f"Gap Discovery Agent Error: {str(e)}")
    else:
        diagnostics["gap_discovery_status"] = f"CACHED ({len(raw_gaps)} candidate gaps)"

    _save_workflow_checkpoint(project_id, paper_a["id"], paper_b["id"], {
        "raw_gaps": raw_gaps,
        "gaps_summary": summary
    })

    return {
        "raw_gaps": raw_gaps,
        "gaps_summary": summary,
        "current_step": "gaps_discovered",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_gap_validation(state: ResearchState) -> Dict[str, Any]:
    """Node 4: Programmatically enforce the Critical Evidence Rule on every candidate gap."""
    raw_gaps = state.get("raw_gaps", [])
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    validated_gaps = []
    for g in raw_gaps:
        v_gap = validate_and_classify_gap(g)
        validated_gaps.append(v_gap)

    verified_count = sum(1 for g in validated_gaps if g.get("verification_status") == "VERIFIED")
    unverified_count = len(validated_gaps) - verified_count
    diagnostics["validation_status"] = f"SUCCESS ({verified_count} VERIFIED, {unverified_count} UNVERIFIED)"

    return {
        "gaps": validated_gaps,
        "current_step": "gaps_validated",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_literature_verification(state: ResearchState) -> Dict[str, Any]:
    """Node 5: Execute live supplementary literature discovery via Semantic Scholar & arXiv."""
    gaps = state.get("gaps", [])
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    updated_gaps = []
    for g in gaps:
        # Check if already verified during discovery or run fresh
        if "literature_verification" not in g or not g["literature_verification"]:
            lit_ver = perform_literature_verification(g.get("gap_title", ""))
            g["literature_verification"] = lit_ver
        else:
            lit_ver = g["literature_verification"]

        if g.get("verification_status") == "VERIFIED" and lit_ver.get("addressed_in_literature"):
            g["classification"] = CLASSIFICATION_LITERATURE

        updated_gaps.append(g)

    diagnostics["literature_status"] = "SUCCESS"
    return {
        "gaps": updated_gaps,
        "current_step": "literature_verified",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_proposal_generation(state: ResearchState) -> Dict[str, Any]:
    """Node 6: Synthesize 3 prioritized research proposals with all 18 dimensions and capstone project."""
    paper_a = state["paper_a"]
    paper_b = state["paper_b"]
    project_id = state["project_id"]
    topic = state["topic"]
    analysis_a = state["analysis_a"]
    analysis_b = state["analysis_b"]
    gaps = state["gaps"]
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    proposals = state.get("proposals")
    rationale = state.get("ranking_rationale", "")

    if not (proposals and isinstance(proposals, list) and len(proposals) >= 3):
        try:
            proposal_result = run_proposal_generation(topic, analysis_a, analysis_b, gaps)
            proposals = proposal_result.get("proposals", [])
            rationale = proposal_result.get("ranking_rationale", "")
            diagnostics["proposals_status"] = f"SUCCESS ({len(proposals)} proposals generated)"
        except Exception as e:
            log_diagnostic("ERROR", "Proposal generation failed", e)
            errors.append(f"Proposal Agent Error: {str(e)}")
            diagnostics["proposals_status"] = f"FAILED: {str(e)}"
            raise RuntimeError(f"Proposal Agent Error: {str(e)}")
    else:
        diagnostics["proposals_status"] = f"CACHED ({len(proposals)} proposals)"

    _save_workflow_checkpoint(project_id, paper_a["id"], paper_b["id"], {
        "proposals": proposals,
        "ranking_rationale": rationale
    })

    return {
        "proposals": proposals,
        "ranking_rationale": rationale,
        "current_step": "proposals_generated",
        "errors": errors,
        "diagnostics": diagnostics
    }


def node_save_results(state: ResearchState) -> Dict[str, Any]:
    """Node 7: Persist all generated analyses, validated gaps, and proposals into SQLite."""
    project_id = state["project_id"]
    paper_a = state["paper_a"]
    paper_b = state["paper_b"]
    comparative_matrix = dict(state.get("comparative_matrix", {}))
    analysis_a = state.get("analysis_a", {})
    analysis_b = state.get("analysis_b", {})
    gaps = state.get("gaps", [])
    proposals = state.get("proposals", [])
    errors = list(state.get("errors", []))
    diagnostics = dict(state.get("diagnostics", {}))

    # Ensure individual analyses are firmly embedded in comparative_matrix
    comparative_matrix["analysis_a"] = analysis_a
    comparative_matrix["analysis_b"] = analysis_b

    # Strict output validation
    if not analysis_a:
        raise RuntimeError("Validation Failure: Paper A 15-point analysis is empty.")
    if not analysis_b:
        raise RuntimeError("Validation Failure: Paper B 15-point analysis is empty.")
    if not comparative_matrix.get("table"):
        raise RuntimeError("Validation Failure: Comparative matrix table has 0 dimensions.")
    if not gaps or len(gaps) < 1:
        raise RuntimeError("Validation Failure: Research gap discovery produced 0 gaps.")
    if not proposals or len(proposals) < 1:
        raise RuntimeError("Validation Failure: Proposal agent produced 0 proposals.")

    try:
        save_analysis_results(
            project_id=project_id,
            paper_a_id=paper_a["id"],
            paper_b_id=paper_b["id"],
            matrix=comparative_matrix,
            gaps=gaps,
            proposals=proposals
        )
        try:
            update_project_status(project_id, "analyzed")
        except Exception as st_err:
            log_diagnostic("WARNING", f"Could not update project status: {st_err}")
        diagnostics["persistence_status"] = "SUCCESS (Saved to SQLite)"
    except Exception as e:
        log_diagnostic("ERROR", "Failed to persist results to SQLite", e)
        errors.append(f"Database Persistence Error: {str(e)}")
        diagnostics["persistence_status"] = f"FAILED: {str(e)}"
        raise RuntimeError(f"Database Persistence Error: {str(e)}")

    return {
        "comparative_matrix": comparative_matrix,
        "current_step": "completed",
        "errors": errors,
        "diagnostics": diagnostics
    }


def build_research_graph() -> Any:
    """Build and compile the LangGraph StateGraph strictly following the required pipeline order."""
    graph = StateGraph(ResearchState)

    graph.add_node("independent_analysis", node_independent_analysis)
    graph.add_node("comparative_matrix", node_comparative_matrix)
    graph.add_node("gap_discovery", node_gap_discovery)
    graph.add_node("gap_validation", node_gap_validation)
    graph.add_node("literature_verification", node_literature_verification)
    graph.add_node("proposal_generation", node_proposal_generation)
    graph.add_node("save_results", node_save_results)

    graph.set_entry_point("independent_analysis")
    graph.add_edge("independent_analysis", "comparative_matrix")
    graph.add_edge("comparative_matrix", "gap_discovery")
    graph.add_edge("gap_discovery", "gap_validation")
    graph.add_edge("gap_validation", "literature_verification")
    graph.add_edge("literature_verification", "proposal_generation")
    graph.add_edge("proposal_generation", "save_results")
    graph.add_edge("save_results", END)

    return graph.compile()


def execute_multi_agent_workflow(
    project_id: str,
    topic: str,
    paper_a: Dict[str, Any],
    paper_b: Dict[str, Any],
    progress_callback: Optional[Callable[[str, float], None]] = None,
    force_refresh: bool = False
) -> ResearchState:
    """
    Run the complete LangGraph multi-agent pipeline with step-by-step progress callbacks.
    Executes all 7 nodes sequentially without silent failure.
    Resumes from checkpoints and caches completed nodes to prevent redundant LLM invocations.
    """
    app = build_research_graph()

    initial_state: ResearchState = {
        "project_id": project_id,
        "topic": topic,
        "paper_a": paper_a,
        "paper_b": paper_b,
        "context_a": "",
        "context_b": "",
        "analysis_a": {},
        "analysis_b": {},
        "comparative_matrix": {},
        "raw_gaps": [],
        "gaps": [],
        "gaps_summary": "",
        "proposals": [],
        "ranking_rationale": "",
        "current_step": "started",
        "errors": [],
        "diagnostics": {}
    }

    # Load existing checkpoint or database analysis if not forcing refresh
    if not force_refresh:
        # Check SQLite first
        db_results = get_analysis_results(project_id)
        if db_results and db_results.get("paper_a_id") == paper_a["id"] and db_results.get("paper_b_id") == paper_b["id"]:
            matrix = db_results.get("comparative_matrix", {})
            if matrix:
                if matrix.get("analysis_a"):
                    initial_state["analysis_a"] = matrix["analysis_a"]
                if matrix.get("analysis_b"):
                    initial_state["analysis_b"] = matrix["analysis_b"]
                if matrix.get("table") and len(matrix.get("table", [])) >= 3:
                    initial_state["comparative_matrix"] = matrix
            if db_results.get("gaps"):
                initial_state["gaps"] = db_results["gaps"]
                initial_state["raw_gaps"] = db_results["gaps"]
            if db_results.get("proposals") and len(db_results.get("proposals", [])) >= 3:
                initial_state["proposals"] = db_results["proposals"]

        # Check intermediate disk checkpoint
        chk = _load_workflow_checkpoint(project_id, paper_a["id"], paper_b["id"])
        if chk:
            if chk.get("analysis_a") and not initial_state["analysis_a"]:
                initial_state["analysis_a"] = chk["analysis_a"]
            if chk.get("analysis_b") and not initial_state["analysis_b"]:
                initial_state["analysis_b"] = chk["analysis_b"]
            if chk.get("context_a") and not initial_state["context_a"]:
                initial_state["context_a"] = chk["context_a"]
            if chk.get("context_b") and not initial_state["context_b"]:
                initial_state["context_b"] = chk["context_b"]
            if chk.get("comparative_matrix") and not initial_state["comparative_matrix"]:
                initial_state["comparative_matrix"] = chk["comparative_matrix"]
            if chk.get("raw_gaps") and not initial_state["raw_gaps"]:
                initial_state["raw_gaps"] = chk["raw_gaps"]
            if chk.get("gaps_summary") and not initial_state["gaps_summary"]:
                initial_state["gaps_summary"] = chk["gaps_summary"]
            if chk.get("proposals") and not initial_state["proposals"]:
                initial_state["proposals"] = chk["proposals"]
            if chk.get("ranking_rationale") and not initial_state["ranking_rationale"]:
                initial_state["ranking_rationale"] = chk["ranking_rationale"]
    else:
        # Clear checkpoint file if force refresh
        try:
            chk_path = _get_checkpoint_path(project_id, paper_a["id"], paper_b["id"])
            if chk_path.exists():
                chk_path.unlink()
        except Exception:
            pass

    steps = [
        ("Step 1/7: Performing independent 15-point analysis of Paper A & Paper B...", 0.15),
        ("Step 2/7: Constructing scientific comparative matrix & scope compatibility...", 0.30),
        ("Step 3/7: Discovering research gaps across 7 academic categories...", 0.45),
        ("Step 4/7: Programmatically enforcing Critical Evidence Rule...", 0.60),
        ("Step 5/7: Executing supplementary literature verification via Semantic Scholar & arXiv...", 0.75),
        ("Step 6/7: Synthesizing 3 publication-grade research proposals & capstone recommendation...", 0.90),
        ("Step 7/7: Persisting structured findings to SQLite...", 0.98),
    ]

    # Stream graph execution with progress callbacks
    current_state = initial_state
    step_idx = 0

    for output in app.stream(initial_state):
        node_name = list(output.keys())[0]
        node_output = output[node_name]
        current_state.update(node_output)

        if progress_callback and step_idx < len(steps):
            msg, pct = steps[step_idx]
            progress_callback(msg, pct)
            step_idx += 1

    # Final comprehensive validation before returning state
    matrix = current_state.get("comparative_matrix", {})
    if not matrix or not matrix.get("table"):
        raise RuntimeError("Workflow Execution Error: Comparative matrix table was not produced.")
    if not current_state.get("gaps"):
        raise RuntimeError("Workflow Execution Error: Research gaps list is empty.")
    if not current_state.get("proposals"):
        raise RuntimeError("Workflow Execution Error: Research proposals list is empty.")

    if progress_callback:
        progress_callback("Multi-Agent Review Complete! All research outputs validated and persisted.", 1.0)

    return current_state
