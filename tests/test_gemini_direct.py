import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import GEMINI_API_KEY
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)

models_to_test = ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]

for m in models_to_test:
    t0 = time.time()
    print(f"Testing model: {m}...")
    try:
        response = client.models.generate_content(
            model=m,
            contents="Say 'Hello World' in 2 words."
        )
        dt = time.time() - t0
        print(f"  Success in {dt:.2f}s: {response.text.strip()}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  Failed in {dt:.2f}s: {type(e).__name__} - {e}")
