import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import GEMINI_API_KEY
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)

try:
    models = list(client.models.list())
    print(f"Total Gemini models available: {len(models)}")
    gemini_names = [m.name for m in models if "gemini" in m.name.lower()]
    for name in gemini_names[:15]:
        print(" ", name)
except Exception as e:
    print("Error listing models:", e)
