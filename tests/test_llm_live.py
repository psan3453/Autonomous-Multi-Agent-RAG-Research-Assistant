import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.llm_service import get_llm_service

llm = get_llm_service()
print("Initialized LLM service.")
print("Testing Gemini invocation...")
try:
    res = llm.invoke("Reply in 1 sentence: What is RAG in AI?")
    print("Gemini response:", res.strip())
    print("Provider used:", llm.last_provider_used, "| Model:", llm.last_model_used)
except Exception as e:
    print("Gemini failed:", e)

print("\nTesting structured invocation...")
try:
    struct_res = llm.invoke_structured("Return a JSON object with key 'concept' and value 'RAG', and key 'status' with value 'active'.")
    print("Structured response:", struct_res)
except Exception as e:
    print("Structured failed:", e)
