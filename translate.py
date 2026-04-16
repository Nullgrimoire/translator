#!/usr/bin/env python3
"""
translate.py — Bilingual English <-> Spanish text translator
Uses your local Ollama setup. Auto-detects language direction.
Usage: python translate.py
"""

import subprocess
import sys
import json


OLLAMA_MODEL = "llama3.2:3b"  # Change to whichever model you have (e.g. mistral, llama3.2)

SYSTEM_PROMPT = """You are a casual bilingual translator helping someone text a friend in Mexico.

Rules:
- If the input is in English, translate it to casual Mexican Spanish (like you'd text a friend — natural, not formal).
- If the input is in Spanish, translate it to natural English.
- Return ONLY the translation. No explanations, no notes, no extra text.
- Keep the tone casual and conversational, matching the original message's energy.
- Preserve slang, emoji, and punctuation style where possible."""


def translate(text: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "stream": False
    }

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST",
             "http://localhost:11434/api/chat",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=30
        )
        response = json.loads(result.stdout)
        return response["message"]["content"].strip()
    except subprocess.TimeoutExpired:
        print("❌ Ollama timed out. Is it running? Try: ollama serve")
        sys.exit(1)
    except (json.JSONDecodeError, KeyError):
        print("❌ Unexpected response from Ollama.")
        print("Raw output:", result.stdout[:300])
        sys.exit(1)
    except FileNotFoundError:
        print("❌ curl not found. Make sure curl is installed.")
        sys.exit(1)


def copy_to_clipboard(text: str):
    """Try to copy to clipboard (Windows/macOS/Linux)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True
        else:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    print("🌎 Translator — English ↔ Spanish (auto-detect)")
    print("   Model:", OLLAMA_MODEL)
    print("   Type your message, press Enter. Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            print("⏳ Translating...", end="\r")
            translation = translate(user_input)

            print(f"✅ {translation}")

            copied = copy_to_clipboard(translation)
            if copied:
                print("   (copied to clipboard)\n")
            else:
                print()

        except KeyboardInterrupt:
            print("\n\nBye!")
            break


if __name__ == "__main__":
    main()