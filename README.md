# Autonomous Multi-Agent RAG Research Assistant

**For Literature Review, Research Gap Discovery, and Research Direction Generation**  
*A Final-Year Engineering Capstone Project*

---

## 📌 Project Overview

The **Autonomous Multi-Agent RAG Research Assistant** is an end-to-end academic AI platform designed to automate and elevate the scientific literature review process. Powered by **LangGraph multi-agent orchestration**, **FAISS CPU vector database**, **Sentence-Transformers BGE embeddings**, and dual **Google Gemini / Groq LLM reasoning**, this application allows researchers, engineering students, and professors to:

1. Discover real, peer-reviewed research papers via **Semantic Scholar** and **arXiv** APIs.
2. Ingest and extract full-text PDFs page-by-page using **PyMuPDF**, preserving provenance metadata.
3. Index chunks into a local **FAISS CPU** vector database with **BGE-small-en-v1.5** embeddings.
4. Conduct strictly grounded **RAG Research Q&A** with exact paper title and page citations (`[Paper, Page X]`).
5. Execute a 3-agent **LangGraph workflow**:
   - **Research Analysis Agent**: Extracts objectives, methodologies, models, benchmarks, and author limitations.
   - **Research Gap Discovery Agent**: Uncovers categorized research gaps (Methodological, Dataset, Generalization, Computational, Evaluation) and distinguishes author-admitted limitations from inferred comparative gaps.
   - **Research Proposal Agent**: Synthesizes 3 feasible, prioritized research directions with complete technical architectures, loss functions, datasets, and 4-phase implementation roadmaps.
6. Generate and download a publication-ready **Microsoft Word (.docx)** report formatted with executive summaries, comparative tables, and real bibliographic citations.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend & UI** | Streamlit (Dark Navy & Academic Theme) |
| **Multi-Agent Orchestration** | LangGraph StateGraph |
| **Primary Reasoning LLM** | Google Gemini API (`gemini-2.5-flash`, `gemini-1.5-flash`) |
| **Fast Supporting LLM** | Groq API (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`) |
| **Local Vector Embeddings** | Sentence-Transformers (`BAAI/bge-small-en-v1.5`) |
| **Vector Database** | FAISS CPU (`IndexFlatIP` Cosine Similarity) |
| **PDF Extraction** | PyMuPDF (`fitz`) with page & section preservation |
| **Paper Discovery APIs** | Semantic Scholar Graph API & arXiv Atom API |
| **Persistence & Metadata** | SQLite (`projects`, `papers`, `analysis_results`, `chat_history`) |
| **Report Generation** | python-docx |
| **Environment Management** | python-dotenv |

---

## 🚀 Quick Start Guide

### 1. Clone / Open Directory
Open PowerShell or your terminal in the project directory:
```powershell
cd d:\Research_Assistant
```

### 2. Virtual Environment Setup (Recommended)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure API Keys
Copy `.env.example` to `.env` and insert your Gemini API Key:
```powershell
cp .env.example .env
```
Inside `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here  # Optional: for fast tasks
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```
*(Note: You can also enter or update API keys directly inside the application UI sidebar without restarting).*

### 5. Launch Application
Launch the complete academic dashboard:
```powershell
streamlit run app.py
```

The web dashboard will automatically open in your default browser at `http://localhost:8501`.

---

## 🖥️ Streamlit Application Walkthrough (9 Core Sections)

- **PAGE 1: Home Dashboard**: High-level telemetry showing total projects, discovered papers, processed documents, and identified gaps. Quick-loader for recent projects.
- **PAGE 2: Research Topic Search**: Search box supporting custom queries and presets with year filtering. Real-time API connection to Semantic Scholar & arXiv.
- **PAGE 3: Top Five Papers**: Interactive cards displaying real paper metadata, DOIs, authors, and relevance explanations. Enforces selection of **exactly two** papers.
- **PAGE 4: Paper Processing**: Automatic PDF downloader with manual upload fallback. PyMuPDF extracts text per page, checks for non-OCR scanned documents, and builds the local FAISS index.
- **PAGE 5: RAG Research Chat**: Grounded conversational chatbot. Answers user queries citing source paper names, section headers, and page numbers with similarity scores.
- **PAGE 6: Paper Comparison**: Side-by-side comparative matrix contrasting Objectives, Problem Statements, Methodologies, Datasets, Metrics, and Results.
- **PAGE 7: Research Gap Discovery**: Systematic gap cards categorized across 7 academic dimensions with explicit badges for *Author-Stated Limitation* vs *Inferred Comparative Gap*.
- **PAGE 8: Research Idea Generation**: 3 prioritized research directions tailored for undergraduate/master capstone timelines (3-4 months, standard compute).
- **PAGE 9: Report Generation**: One-click generation of a comprehensive, styled Microsoft Word (`.docx`) report ready for immediate academic submission.

---

## 🧪 Running Unit Tests

To run the automated test suite verifying database CRUD, PDF chunking, title deduplication, and JSON parsing:
```powershell
python -m unittest tests/test_basic.py
```

---

## 🎓 Evaluator Demonstration Script (5-Minute Walkthrough)

1. **Launch App**: Execute `streamlit run app.py` and present the Home Dashboard.
2. **Search Topic**: Go to **Research Topic Search**, click the preset *"Agentic RAG for Medical Question Answering"* (or your chosen topic), and click **Search Real Research Papers**.
3. **Select 2 Papers**: Show the 5 retrieved real papers on **Top Five Papers**. Select Paper 1 and Paper 2.
4. **Ingest & Index**: Navigate to **Paper Processing**, click **Extract & Build FAISS Index**. Point out the chunk count, page count, and local FAISS vector indexing.
5. **RAG Chat**: Open **RAG Research Chat**, ask *"What methodology does Paper A use and what are its key limitations?"*. Show the inline page citations `[Paper, Page X]` and expand the retrieved source excerpts.
6. **Multi-Agent Review**: Open **Paper Comparison** and click **Run LangGraph Multi-Agent Analysis Pipeline**. Show the comparative table, uncovered **Research Gaps**, and 3 prioritized **Research Proposals**.
7. **Download Report**: Go to **Report Generation**, click **Build Document (.docx)**, and click **Download Word Report** to demonstrate the generated submission document.
