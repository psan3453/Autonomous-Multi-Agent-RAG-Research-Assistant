import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import GEMINI_API_KEY
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)

models_to_test = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3-flash-preview"
]

for m in models_to_test:
    t0 = time.time()
    try:
        response = client.models.generate_content(
            model=m,
            contents="Say 'OK' in 1 word."
        )
        dt = time.time() - t0
        print(f"Model {m}: SUCCESS ({dt:.2f}s) -> {response.text.strip()}")
    except Exception as e:
        dt = time.time() - t0
        print(f"Model {m}: FAILED ({dt:.2f}s) -> {type(e).__name__}: {str(e)[:100]}")
