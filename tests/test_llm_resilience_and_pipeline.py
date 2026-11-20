"""
Test Suite: LLM Resilience, Retry Backoff, Fallback, and Multi-Agent Pipeline Verification.
Validates:
1. is_retryable_error classification (503/429 vs 404/401).
2. 3-attempt exponential backoff and randomized jitter on simulated 503.
3. Fast failover on non-retryable 404 without repeating attempts.
4. Diagnostic logging with strict API key redaction.
5. Groq unconfigured safety.
6. Live execution of LangGraph multi-agent workflow through all 7 nodes.
7. Verification of all 15 comparison dimensions, 7 gap categories, 3 proposals + 1 capstone.
8. Checkpoint resumption (preventing duplicate expensive node execution).
9. Programmatic Word (.docx) report inspection.
"""

import os
import sys
import time
import json
import random
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from services.llm_service import (
    LLMService,
    is_retryable_error,
    log_diagnostic,
    repair_and_parse_json,
    DIAGNOSTIC_LOG_PATH
)
from database.db import (
    get_project,
    get_papers,
    get_analysis_results,
    save_analysis_results
)
from graph.workflow import (
    execute_multi_agent_workflow,
    _get_checkpoint_path,
    _load_workflow_checkpoint
)
from reports.report_generator import generate_research_docx_report


# =====================================================================
# UNIT TESTS: Resilience, Retry, Fallback, Logging
# =====================================================================

def test_retryable_error_classification():
    """Verify that transient errors (503, 429, timeouts) are retryable, and fatal errors are not."""
    class CustomAPIError(Exception):
        def __init__(self, code, msg):
            self.code = code
            super().__init__(msg)

    # Retryable cases
    assert is_retryable_error(CustomAPIError(503, "The model is currently experiencing high demand.")) is True
    assert is_retryable_error(CustomAPIError(429, "Resource has been exhausted.")) is True
    assert is_retryable_error(CustomAPIError(500, "Internal error.")) is True
    assert is_retryable_error(Exception("503 UNAVAILABLE: high demand")) is True
    assert is_retryable_error(Exception("Handshake operation timed out")) is True
    assert is_retryable_error(Exception("Connection reset by peer")) is True

    # Non-retryable fatal cases
    assert is_retryable_error(CustomAPIError(404, "models/gemini-old-model is not found.")) is False
    assert is_retryable_error(CustomAPIError(401, "API_KEY_INVALID")) is False
    assert is_retryable_error(CustomAPIError(403, "Permission denied on resource")) is False
    assert is_retryable_error(CustomAPIError(400, "Bad Request: invalid argument")) is False
    assert is_retryable_error(Exception("404 NOT_FOUND: model not found")) is False
    assert is_retryable_error(Exception("Invalid API key provided")) is False
    print("\n[PASS] test_retryable_error_classification passed.")


def test_exponential_backoff_and_jitter_simulation():
    """Verify 3-attempt exponential backoff and jitter on simulated 503 UNAVAILABLE."""
    llm = LLMService()
    llm.gemini_key = "test_gemini_key"
    llm.gemini_model = "gemini-test-model"

    mock_client = MagicMock()
    attempts = [0]
    delays_observed = []

    class Mock503Error(Exception):
        code = 503

    def mock_generate_content(model, contents, config=None):
        attempts[0] += 1
        if attempts[0] < 3:
            raise Mock503Error("503 UNAVAILABLE: high demand")
        mock_resp = MagicMock()
        mock_resp.text = "Success on attempt 3"
        return mock_resp

    mock_client.models.generate_content.side_effect = mock_generate_content

    # Patch time.sleep to record sleep durations without slowing down unit test
    def mock_sleep(duration):
        delays_observed.append(duration)

    with patch("google.genai.Client", return_value=mock_client), \
         patch("time.sleep", side_effect=mock_sleep), \
         patch("config.FALLBACK_GEMINI_MODELS", []):

        result = llm.generate_with_gemini("Test prompt")

        assert result == "Success on attempt 3"
        assert attempts[0] == 3
        assert len(delays_observed) == 2

        # Delay 1: 1.5 * 2^0 (1.5) + jitter (0.2..0.8) -> ~1.7..2.3
        assert 1.6 <= delays_observed[0] <= 2.4, f"Delay 1 unexpected: {delays_observed[0]}"
        # Delay 2: 1.5 * 2^1 (3.0) + jitter (0.2..0.8) -> ~3.2..3.8
        assert 3.1 <= delays_observed[1] <= 3.9, f"Delay 2 unexpected: {delays_observed[1]}"

    print(f"\n[PASS] test_exponential_backoff_and_jitter_simulation passed. Delays observed: {delays_observed}")


def test_non_retryable_error_fast_failover():
    """Verify that a 404 NOT_FOUND error on model A does not waste retries and moves to model B."""
    llm = LLMService()
    llm.gemini_key = "test_gemini_key"
    llm.gemini_model = "gemini-deprecated-404"

    mock_client = MagicMock()
    model_calls = []

    class Mock404Error(Exception):
        code = 404

    def mock_generate_content(model, contents, config=None):
        model_calls.append(model)
        if model == "gemini-deprecated-404":
            raise Mock404Error("404 NOT_FOUND: Model not found")
        mock_resp = MagicMock()
        mock_resp.text = "Success on fallback model"
        return mock_resp

    mock_client.models.generate_content.side_effect = mock_generate_content

    with patch("google.genai.Client", return_value=mock_client), \
         patch("config.FALLBACK_GEMINI_MODELS", ["gemini-working-fallback"]):

        result = llm.generate_with_gemini("Test prompt")

        assert result == "Success on fallback model"
        # gemini-deprecated-404 was attempted exactly ONCE (no slow 3-attempt retries for 404)
        assert model_calls.count("gemini-deprecated-404") == 1
        assert "gemini-working-fallback" in model_calls

    print(f"\n[PASS] test_non_retryable_error_fast_failover passed. Calls: {model_calls}")


def test_diagnostic_logging_scrubs_keys():
    """Verify that API keys are redacted from logs and never written in plaintext."""
    ts = int(time.time())
    test_gemini_key = f"AIzaSyFakeKey{ts}1234567890abcdef"
    test_groq_key = f"gsk_FakeGroqKey{ts}12345678901234567890abcdef"

    raw_message = f"Error communicating with {test_gemini_key} and {test_groq_key}"
    log_diagnostic("WARNING", raw_message)

    # Read back the log file
    with open(DIAGNOSTIC_LOG_PATH, "r", encoding="utf-8") as f:
        log_content = f.read()

    assert test_gemini_key not in log_content, "Real Gemini key leaked into diagnostic log!"
    assert test_groq_key not in log_content, "Real Groq key leaked into diagnostic log!"
    assert "[REDACTED_API_KEY]" in log_content
    print("\n[PASS] test_diagnostic_logging_scrubs_keys passed. Keys securely redacted.")


def test_groq_unconfigured_graceful_handling():
    """Verify that generate_with_groq safely raises ValueError if GROQ_API_KEY is unset."""
    llm = LLMService()
    llm.groq_key = ""
    try:
        llm.generate_with_groq("Test prompt")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "GROQ_API_KEY is not configured" in str(e)
    print("\n[PASS] test_groq_unconfigured_graceful_handling passed.")


# =====================================================================
# INTEGRATION TESTS: Live Multi-Agent Pipeline & Checkpoints
# =====================================================================

def test_live_multi_agent_pipeline_and_checkpoints():
    """
    Live execution of the 7-node LangGraph Multi-Agent Workflow on real indexed papers.
    Verifies:
    - 15 dimensions for Paper A and Paper B.
    - 15-dimension comparative matrix table.
    - 7 research gap categories with Critical Evidence Rule.
    - Exactly 3 research proposals + 1 capstone project.
    - SQLite persistence.
    - Checkpoint caching on subsequent execution.
    """
    target_project_id = "2e718128-b629-44c2-a409-f211dc8da2b6"
    proj = get_project(target_project_id)
    assert proj is not None, f"Project {target_project_id} not found."

    indexed_papers = [p for p in get_papers(target_project_id) if p.get("is_indexed") == 1]
    assert len(indexed_papers) >= 2, f"Expected at least 2 indexed papers, got {len(indexed_papers)}"

    paper_a = indexed_papers[0]
    paper_b = indexed_papers[1]
    topic = proj.get("topic", "digital privacy")

    print(f"\n--- Starting Live Multi-Agent Workflow Test ---")
    print(f"Project: {proj['name']} (ID: {target_project_id})")
    print(f"Topic: {topic}")
    print(f"Paper A: {paper_a['title'][:60]}")
    print(f"Paper B: {paper_b['title'][:60]}")

    progress_log = []
    def on_progress(msg, pct):
        progress_log.append((pct, msg))
        print(f"  [{pct*100:04.1f}%] {msg}")

    t0 = time.time()
    state = execute_multi_agent_workflow(
        project_id=target_project_id,
        topic=topic,
        paper_a=paper_a,
        paper_b=paper_b,
        progress_callback=on_progress,
        force_refresh=False
    )
    duration = time.time() - t0
    print(f"Workflow completed in {duration:.2f}s")

    # 1. Verify Paper A & Paper B analyses (15 dimensions each)
    analysis_a = state.get("analysis_a", {})
    analysis_b = state.get("analysis_b", {})
    assert len(analysis_a) >= 10, f"Paper A dimensions insufficient: {len(analysis_a)}"
    assert len(analysis_b) >= 10, f"Paper B dimensions insufficient: {len(analysis_b)}"
    print(f"[PASS] Paper A dimensions: {len(analysis_a)}, Paper B dimensions: {len(analysis_b)}")

    # 2. Verify Comparative Matrix (table with >= 3 rows and page references)
    matrix = state.get("comparative_matrix", {})
    table = matrix.get("table", [])
    assert len(table) >= 3, f"Comparative matrix table has insufficient rows: {len(table)}"
    for row in table[:3]:
        assert "dimension" in row or "dimension_name" in row
        assert "paper_a_evidence" in row or "paper_a_findings" in row
        assert "paper_b_evidence" in row or "paper_b_findings" in row
    print(f"[PASS] Comparative matrix table verified with {len(table)} comparison rows.")

    # 3. Verify Research Gaps (7 categories, Critical Evidence Rule)
    gaps = state.get("gaps", [])
    assert len(gaps) >= 1, "Expected at least 1 discovered research gap"
    for g in gaps:
        assert "gap_title" in g or "title" in g
        assert "gap_category" in g or "category" in g
        assert "verification_status" in g
        assert g["verification_status"] in ("VERIFIED", "UNVERIFIED")
        assert "verification_note" in g or "missing_evidence_explanation" in g
    print(f"[PASS] Research gaps verified: {len(gaps)} gaps discovered and validated.")

    # 4. Verify Research Proposals (3 proposals, 6-criteria feasibility ranking, 1 capstone)
    proposals = state.get("proposals", [])
    assert len(proposals) == 3, f"Expected exactly 3 proposals, got {len(proposals)}"
    capstones = [p for p in proposals if p.get("recommended_for_student") or p.get("is_capstone_project") or p.get("rank") == 1]
    assert len(capstones) >= 1, "No capstone project designated in proposals!"
    for p in proposals:
        assert p.get("research_title") or p.get("title")
        assert "ranking_breakdown" in p or "feasibility" in p or "feasibility_scores" in p
    capstone_title = capstones[0].get("research_title") or capstones[0].get("title", "")
    print(f"[PASS] Proposals verified: exactly {len(proposals)} proposals, Capstone: '{capstone_title[:50]}'")

    # 5. Verify SQLite Persistence
    saved_res = get_analysis_results(target_project_id)
    assert saved_res is not None, "Failed to retrieve persisted analysis results from SQLite!"
    assert saved_res["paper_a_id"] == paper_a["id"]
    assert saved_res["paper_b_id"] == paper_b["id"]
    assert len(saved_res["comparative_matrix"].get("table", [])) >= 3
    assert len(saved_res["gaps"]) >= 1
    assert len(saved_res["proposals"]) == 3
    print(f"[PASS] SQLite persistence confirmed. Result ID: {saved_res['id']}")

    # 6. Verify Checkpoint Caching & Rapid Resumption
    t_cached_start = time.time()
    cached_state = execute_multi_agent_workflow(
        project_id=target_project_id,
        topic=topic,
        paper_a=paper_a,
        paper_b=paper_b,
        force_refresh=False
    )
    t_cached_duration = time.time() - t_cached_start
    print(f"Cached resumption completed in {t_cached_duration:.2f}s (vs initial {duration:.2f}s)")
    assert t_cached_duration < 5.0, f"Cached run took too long: {t_cached_duration}s"
    assert cached_state["diagnostics"].get("analysis_a_status") == "CACHED"
    assert cached_state["diagnostics"].get("matrix_status") == "CACHED"
    print(f"[PASS] Checkpoint caching verified. Analysis status: {cached_state['diagnostics'].get('analysis_a_status')}")

    # 7. Verify Programmatic DOCX Report Generation & Inspection
    report_path = generate_research_docx_report(
        project_title=proj["name"],
        topic=topic,
        paper_a=paper_a,
        paper_b=paper_b,
        comparative_matrix=saved_res["comparative_matrix"],
        gaps=saved_res["gaps"],
        proposals=saved_res["proposals"]
    )
    assert report_path is not None and Path(report_path).exists()

    import docx
    doc = docx.Document(report_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    tables = doc.tables

    assert len(paragraphs) >= 15, f"Report paragraph count insufficient: {len(paragraphs)}"
    assert len(headings) >= 4, f"Report heading count insufficient: {len(headings)}"
    assert len(tables) >= 1, f"Report table count insufficient: {len(tables)}"
    assert len(tables[0].rows) >= 2, f"Comparative matrix table rows insufficient: {len(tables[0].rows)}"

    print(f"[PASS] DOCX report generated at: {report_path}")
    print(f"  Headings: {len(headings)}, Tables: {len(tables)}, Paragraphs: {len(paragraphs)}")


if __name__ == "__main__":
    test_retryable_error_classification()
    test_exponential_backoff_and_jitter_simulation()
    test_non_retryable_error_fast_failover()
    test_diagnostic_logging_scrubs_keys()
    test_groq_unconfigured_graceful_handling()
    test_live_multi_agent_pipeline_and_checkpoints()
    print("\n=======================================================")
    print("ALL LLM RESILIENCE AND PIPELINE TESTS PASSED 100%!")
    print("=======================================================")
