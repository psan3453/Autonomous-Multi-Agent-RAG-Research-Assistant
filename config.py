"""
Configuration module for Autonomous Multi-Agent RAG Research Assistant.
Centralizes environment variables, paths, and model hyperparameters.
"""

import os
# Prevent OpenBLAS / OMP thread allocation exhaustion on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

STORAGE_DIR = BASE_DIR / "storage"
PAPERS_DIR = STORAGE_DIR / "papers"
INDEXES_DIR = STORAGE_DIR / "indexes"
REPORTS_DIR = STORAGE_DIR / "reports"
LOGS_DIR = STORAGE_DIR / "logs"
DB_PATH = STORAGE_DIR / "research_assistant.db"
DIAGNOSTIC_LOG_PATH = LOGS_DIR / "diagnostics.log"

# Aliases for robust importing across modules
DIAGNOSTICS_LOG_PATH = DIAGNOSTIC_LOG_PATH
LOG_PATH = DIAGNOSTIC_LOG_PATH
LOG_FILE = DIAGNOSTIC_LOG_PATH

# Ensure runtime directories exist immediately
for folder in [STORAGE_DIR, PAPERS_DIR, INDEXES_DIR, REPORTS_DIR, LOGS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or ""
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# LLM Models
# Primary: gemini-3.1-flash-lite (fast, high quota) & openai/gpt-oss-120b on Groq
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
FALLBACK_GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
]

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Embedding Configuration
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIMENSION = 384  # BGE-small dimension

# Text Chunking Settings
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# RAG Retrieval Settings
TOP_K_RETRIEVAL = 6
SCORE_THRESHOLD = 0.30
MAX_CHAT_HISTORY = 25

# UI Theme styling constants
THEME_NAVY = "#0F172A"
THEME_ACCENT_BLUE = "#2563EB"
THEME_BG = "#F8FAFC"
THEME_CARD_BG = "#FFFFFF"
THEME_TEXT_PRIMARY = "#0F172A"
THEME_TEXT_MUTED = "#64748B"

__all__ = [
    "BASE_DIR",
    "STORAGE_DIR",
    "PAPERS_DIR",
    "INDEXES_DIR",
    "REPORTS_DIR",
    "LOGS_DIR",
    "DB_PATH",
    "DIAGNOSTIC_LOG_PATH",
    "DIAGNOSTICS_LOG_PATH",
    "LOG_PATH",
    "LOG_FILE",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "DEFAULT_GEMINI_MODEL",
    "FALLBACK_GEMINI_MODELS",
    "DEFAULT_GROQ_MODEL",
    "FALLBACK_GROQ_MODELS",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_DIMENSION",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "TOP_K_RETRIEVAL",
    "SCORE_THRESHOLD",
    "MAX_CHAT_HISTORY",
    "THEME_NAVY",
    "THEME_ACCENT_BLUE",
    "THEME_BG",
    "THEME_CARD_BG",
    "THEME_TEXT_PRIMARY",
    "THEME_TEXT_MUTED",
]
