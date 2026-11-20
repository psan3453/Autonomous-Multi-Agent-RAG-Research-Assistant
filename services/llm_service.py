"""
Configurable Dual LLM Service (Gemini + Groq) with Automatic Failover.
- Google Gemini: Deep research reasoning, comparative synthesis, and grounded QA.
- Groq: Low-latency extraction, structured classification, and rapid failover.
- Structured diagnostic logging to storage/logs/diagnostics.log (NO API keys exposed).
- Resilient JSON/Pydantic structured output parsing with syntax repair.
"""

import os
import re
import json
import time
import random
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel

import config
from config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    DEFAULT_GEMINI_MODEL,
    FALLBACK_GEMINI_MODELS,
    DEFAULT_GROQ_MODEL,
    FALLBACK_GROQ_MODELS,
)

DIAGNOSTIC_LOG_PATH = getattr(
    config,
    "DIAGNOSTIC_LOG_PATH",
    getattr(config, "LOGS_DIR", Path(__file__).resolve().parent.parent / "storage" / "logs") / "diagnostics.log"
)
DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Configure logger for diagnostics without exposing credentials
logger = logging.getLogger("ResearchAssistant.LLM")
logger.setLevel(logging.INFO)

if not logger.handlers:
    try:
        fh = logging.FileHandler(str(DIAGNOSTIC_LOG_PATH), encoding="utf-8")
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass


def log_diagnostic(level: str, message: str, exc: Optional[Exception] = None):
    """Log diagnostic information safely without exposing sensitive secrets."""
    # Scrub potential API keys from message
    clean_msg = re.sub(r"(AIza[0-9A-Za-z\-_]{25,50}|gsk_[0-9A-Za-z]{25,60})", "[REDACTED_API_KEY]", message)
    if exc:
        exc_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        clean_exc = re.sub(r"(AIza[0-9A-Za-z\-_]{25,50}|gsk_[0-9A-Za-z]{25,60})", "[REDACTED_API_KEY]", exc_str)
        clean_msg = f"{clean_msg}\nException: {clean_exc}"

    if level == "ERROR":
        logger.error(clean_msg)
    elif level == "WARNING":
        logger.warning(clean_msg)
    else:
        logger.info(clean_msg)


def is_retryable_error(exc: Exception) -> bool:
    """
    Determine whether an error from an LLM provider is transient and retryable.
    Retries HTTP 503 (high demand/unavailable), 429 (rate limit), and network/timeouts.
    Immediately skips fatal non-retryable errors (400, 401, 403, 404).
    """
    # 1. Check explicit HTTP/gRPC status codes if available
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    if code in (400, 401, 403, 404):
        return False

    msg = str(exc).lower()

    # 2. Fatal non-retryable errors
    fatal_patterns = [
        "404 not_found",
        "404 not found",
        "model not found",
        "model_not_found",
        "does not exist",
        "is not supported",
        "invalid api key",
        "api_key_invalid",
        "invalid_api_key",
        "authentication failed",
        "permission denied",
        "401 unauthorized",
        "401",
        "403 forbidden",
        "403",
        "400 bad_request",
        "invalid argument",
    ]
    if any(pat in msg for pat in fatal_patterns):
        return False

    # 3. Retryable transient errors
    retryable_patterns = [
        "503",
        "unavailable",
        "high demand",
        "overloaded",
        "429",
        "resource_exhausted",
        "rate limit",
        "rate_limit",
        "too many requests",
        "timeout",
        "timed out",
        "deadline exceeded",
        "connection reset",
        "connection refused",
        "502",
        "504",
        "bad gateway",
        "service unavailable",
        "temporary failure",
        "handshake operation timed out"
    ]
    return any(pat in msg for pat in retryable_patterns)


def repair_and_parse_json(text: str) -> Any:
    """
    Robust JSON parser for LLM responses.
    Handles:
    - Markdown code fences
    - Trailing commas before closing brackets
    - Unbalanced braces
    - Raw plain text embedding JSON
    """
    if not text or not text.strip():
        raise ValueError("Cannot parse JSON from empty LLM text.")

    cleaned = text.strip()

    # 1. Strip markdown fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()

    # 2. Extract outermost JSON structure
    first_brace = cleaned.find("{")
    first_bracket = cleaned.find("[")
    
    start_pos = -1
    is_object = True

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_pos = first_brace
        is_object = True
    elif first_bracket != -1:
        start_pos = first_bracket
        is_object = False

    if start_pos != -1:
        cleaned = cleaned[start_pos:]
        last_char = "}" if is_object else "]"
        end_pos = cleaned.rfind(last_char)
        if end_pos != -1:
            cleaned = cleaned[:end_pos + 1]

    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # Attempt standard parse with strict=False
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as err:
        log_diagnostic("WARNING", f"Initial JSON parse failed: {err}. Attempting brace balancing.")

    # Try balancing braces if truncated
    if is_object and not cleaned.endswith("}"):
        cleaned += "}"
    elif not is_object and not cleaned.endswith("]"):
        cleaned += "]"

    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as final_err:
        log_diagnostic("ERROR", f"Failed to parse JSON even after repair. Raw text sample: {text[:300]}", final_err)
        raise ValueError(f"Failed to parse structured JSON from LLM: {final_err}")


# Backward-compatible alias for unit tests
extract_json_from_llm_text = repair_and_parse_json


class LLMService:
    def __init__(self):
        self.gemini_key = GEMINI_API_KEY
        self.groq_key = GROQ_API_KEY
        self.gemini_model = DEFAULT_GEMINI_MODEL
        self.groq_model = DEFAULT_GROQ_MODEL
        self.last_provider_used = "None"
        self.last_model_used = "None"
        self.recent_errors: List[str] = []

    def update_keys(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None):
        """Update runtime API keys safely."""
        if gemini_key and gemini_key.strip():
            self.gemini_key = gemini_key.strip()
            os.environ["GEMINI_API_KEY"] = self.gemini_key
        if groq_key and groq_key.strip():
            self.groq_key = groq_key.strip()
            os.environ["GROQ_API_KEY"] = self.groq_key

    def generate_with_gemini(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Execute Gemini prompt using google-genai SDK across candidate models.
        Features:
        - 3-attempt exponential backoff with randomized jitter on transient 503/429/timeout errors.
        - Immediate skipping of non-retryable 400/401/403/404 errors without wasting time.
        - Sequential fallback across verified candidate models.
        - Structured diagnostic logging of provider, model, attempt, status, and elapsed time.
        """
        if not self.gemini_key or not self.gemini_key.strip():
            raise ValueError("GEMINI_API_KEY is not configured or empty.")

        target_model = model or self.gemini_model
        configured_fallbacks = getattr(config, "FALLBACK_GEMINI_MODELS", [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
        ])
        candidate_models = []
        for m in [target_model] + list(configured_fallbacks):
            if m and m not in candidate_models:
                candidate_models.append(m)

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self.gemini_key,
            http_options=types.HttpOptions(api_version="v1beta", timeout=60000)
        )
        last_error = None
        attempted_history = []
        max_attempts_per_model = 3

        for m_name in candidate_models:
            for attempt in range(1, max_attempts_per_model + 1):
                t0 = time.time()
                try:
                    config_obj = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    ) if system_instruction else types.GenerateContentConfig(temperature=0.2)

                    response = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config=config_obj
                    )
                    elapsed = time.time() - t0

                    if response and response.text:
                        self.last_provider_used = "Gemini"
                        self.last_model_used = m_name
                        log_diagnostic(
                            "INFO",
                            f"Gemini generation successful [Provider: Gemini, Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: 200, Elapsed: {elapsed:.2f}s]."
                        )
                        return response.text
                    else:
                        raise RuntimeError("Gemini returned an empty text response.")

                except Exception as e:
                    elapsed = time.time() - t0
                    last_error = e
                    retryable = is_retryable_error(e)
                    status_code = getattr(e, "code", getattr(e, "status_code", "UNKNOWN"))
                    err_summary = str(e)[:160].replace("\n", " ")

                    attempt_record = f"Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: {status_code}, Retryable: {retryable}, Elapsed: {elapsed:.2f}s, Error: {err_summary}"
                    attempted_history.append(attempt_record)
                    self.recent_errors.append(attempt_record)

                    log_diagnostic(
                        "WARNING" if retryable else "ERROR",
                        f"Gemini attempt failed [Provider: Gemini, Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: {status_code}, Elapsed: {elapsed:.2f}s]: {err_summary}"
                    )

                    if not retryable:
                        log_diagnostic("WARNING", f"Error for '{m_name}' is non-retryable ({status_code}). Skipping remaining attempts for this model.")
                        break  # Fall back to next candidate model immediately

                    if attempt < max_attempts_per_model:
                        backoff = 1.5 * (2 ** (attempt - 1)) + random.uniform(0.2, 0.8)
                        log_diagnostic("INFO", f"Backing off for {backoff:.2f}s before retry attempt {attempt + 1}/{max_attempts_per_model} on model '{m_name}'...")
                        time.sleep(backoff)
                    else:
                        log_diagnostic("WARNING", f"Model '{m_name}' exhausted all {max_attempts_per_model} attempts. Falling back to next candidate model...")

        history_summary = " | ".join(attempted_history[-6:])
        raise RuntimeError(f"All Gemini models exhausted. Last error: {str(last_error)}. Attempts: {history_summary}")

    def generate_with_groq(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Execute Groq prompt across candidate models with exponential backoff retry.
        Only attempts Groq when a valid non-empty API key is configured.
        Supports 128k context length models (e.g. llama-3.3-70b-versatile).
        """
        if not self.groq_key or not self.groq_key.strip():
            self.groq_key = os.getenv("GROQ_API_KEY", "").strip()

        if not self.groq_key:
            raise ValueError("GROQ_API_KEY is not configured or empty.")

        target_model = model or self.groq_model
        configured_fallbacks = getattr(config, "FALLBACK_GROQ_MODELS", [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ])
        candidate_models = []
        for m in [target_model] + list(configured_fallbacks) + ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        from groq import Groq
        client = Groq(api_key=self.groq_key, timeout=60.0)
        last_error = None
        attempted_history = []
        max_attempts_per_model = 3

        for m_name in candidate_models:
            for attempt in range(1, max_attempts_per_model + 1):
                t0 = time.time()
                try:
                    messages = []
                    if system_instruction:
                        messages.append({"role": "system", "content": system_instruction})
                    messages.append({"role": "user", "content": prompt})

                    completion = client.chat.completions.create(
                        model=m_name,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=8192,
                    )
                    elapsed = time.time() - t0

                    if completion.choices and completion.choices[0].message.content:
                        self.last_provider_used = "Groq"
                        self.last_model_used = m_name
                        log_diagnostic(
                            "INFO",
                            f"Groq generation successful [Provider: Groq, Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: 200, Elapsed: {elapsed:.2f}s]."
                        )
                        return completion.choices[0].message.content
                    else:
                        raise RuntimeError("Groq returned empty text choices.")

                except Exception as e:
                    elapsed = time.time() - t0
                    last_error = e
                    retryable = is_retryable_error(e)
                    status_code = getattr(e, "status_code", getattr(e, "code", "UNKNOWN"))
                    err_summary = str(e)[:160].replace("\n", " ")

                    attempt_record = f"Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: {status_code}, Retryable: {retryable}, Elapsed: {elapsed:.2f}s, Error: {err_summary}"
                    attempted_history.append(attempt_record)
                    self.recent_errors.append(attempt_record)

                    log_diagnostic(
                        "WARNING" if retryable else "ERROR",
                        f"Groq attempt failed [Provider: Groq, Model: {m_name}, Attempt: {attempt}/{max_attempts_per_model}, Status: {status_code}, Elapsed: {elapsed:.2f}s]: {err_summary}"
                    )

                    if not retryable:
                        log_diagnostic("WARNING", f"Error for Groq model '{m_name}' is non-retryable ({status_code}). Skipping remaining attempts for this model.")
                        break

                    if attempt < max_attempts_per_model:
                        backoff = 1.5 * (2 ** (attempt - 1)) + random.uniform(0.2, 0.8)
                        log_diagnostic("INFO", f"Backing off for {backoff:.2f}s before retry attempt {attempt + 1}/{max_attempts_per_model} on Groq model '{m_name}'...")
                        time.sleep(backoff)
                    else:
                        log_diagnostic("WARNING", f"Groq model '{m_name}' exhausted all {max_attempts_per_model} attempts. Falling back to next candidate model...")

        history_summary = " | ".join(attempted_history[-6:])
        raise RuntimeError(f"All Groq models exhausted. Last error: {str(last_error)}. Attempts: {history_summary}")

    def invoke(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        task_type: str = "deep_reasoning"
    ) -> str:
        """
        Unified invoke with automatic failover between Gemini and Groq.
        Preserves detailed tracebacks and logs.
        """
        errors = []

        gemini_ready = bool(self.gemini_key and self.gemini_key.strip()) or bool(os.getenv("GEMINI_API_KEY", "").strip())
        if not self.gemini_key and gemini_ready:
            self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        groq_ready = bool(self.groq_key and self.groq_key.strip()) or bool(os.getenv("GROQ_API_KEY", "").strip())
        if not self.groq_key and groq_ready:
            self.groq_key = os.getenv("GROQ_API_KEY", "").strip()

        # Strategy 1: If fast_task, prefer Groq first if available
        if task_type == "fast_task" and groq_ready:
            try:
                return self.generate_with_groq(prompt, system_instruction)
            except Exception as e:
                errors.append(f"Groq preferred fast task failed: {str(e)}")
                log_diagnostic("WARNING", f"Groq fast task failed ({type(e).__name__}). Failing over to Gemini...", e)

        # Strategy 2: Deep reasoning or primary call (Try Gemini first)
        gemini_failed = False
        if gemini_ready:
            try:
                return self.generate_with_gemini(prompt, system_instruction)
            except Exception as e:
                gemini_failed = True
                errors.append(f"Gemini call failed: {str(e)}")
                log_diagnostic("WARNING", f"Gemini exhausted ({type(e).__name__}). Automatic fallback checking Groq...", e)

        # Strategy 3: Automatic fallback to Groq if Gemini failed or was unavailable
        if groq_ready:
            try:
                log_diagnostic("INFO", f"Executing Groq automatic fallback (model: {self.groq_model})...")
                return self.generate_with_groq(prompt, system_instruction)
            except Exception as e:
                errors.append(f"Groq fallback failed: {str(e)}")
                log_diagnostic("ERROR", f"Groq fallback also failed ({type(e).__name__}).", e)
        else:
            if gemini_failed:
                log_diagnostic("INFO", "Groq fallback unavailable: GROQ_API_KEY is not configured in .env.")

        # If both failed or unavailable
        combined_err = " | ".join(errors) if errors else "No valid API keys configured for Gemini or Groq."
        log_diagnostic("ERROR", f"Complete LLM pipeline failure: {combined_err}")
        raise RuntimeError(f"LLM Generation Failed on all available providers. Details: {combined_err}")

    def invoke_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        task_type: str = "deep_reasoning"
    ) -> Dict[str, Any]:
        """Invoke LLM and parse strictly into structured JSON."""
        full_system = (
            (system_instruction or "") +
            "\n\nCRITICAL OUTPUT REQUIREMENT:\n"
            "Return ONLY a valid, standard JSON object or array matching the requested schema.\n"
            "Do NOT include any conversational introduction, markdown preambles, or postscript explanations.\n"
            "Ensure all strings are properly quoted and escaped."
        )

        raw_text = self.invoke(prompt, system_instruction=full_system.strip(), task_type=task_type)
        return repair_and_parse_json(raw_text)


_GLOBAL_LLM_SERVICE = None


def get_llm_service() -> LLMService:
    global _GLOBAL_LLM_SERVICE
    if _GLOBAL_LLM_SERVICE is None:
        _GLOBAL_LLM_SERVICE = LLMService()
    return _GLOBAL_LLM_SERVICE
