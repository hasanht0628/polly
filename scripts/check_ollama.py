import os
from pathlib import Path

import ollama   
import sys
from dotenv import load_dotenv

# Load .env from project root (parent of tutorials/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

def main() -> None:
    models = ollama.list()
    names = [m.model for m in models.models]
    print("Installed models:", names)
    if not any(MODEL in n for n in names):
        print(f"Model {MODEL!r} not found. Run: ollama pull {MODEL}")
        sys.exit(1)
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: ok"}],
    )
    print("Smoke test:", response.message.content)

if __name__ == "__main__":
    main()