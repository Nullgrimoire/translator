#!/usr/bin/env python3
"""
translate.py — Multilingual English <-> Any Language translator
Uses your local Ollama setup. Pick your target language at startup.
Usage: python translate.py
"""

import subprocess
import sys
import json
import io

# Force UTF-8 output so emoji and special characters render correctly
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


OLLAMA_MODEL = "llama3.2:3b"  # Change to whichever model you have

LANGUAGE_ALIASES = {
    "spanish": "Spanish", "espanol": "Spanish", "español": "Spanish", "es": "Spanish",
    "french": "French", "francais": "French", "français": "French", "fr": "French",
    "german": "German", "deutsch": "German", "de": "German",
    "italian": "Italian", "italiano": "Italian", "it": "Italian",
    "portuguese": "Portuguese", "portugues": "Portuguese", "português": "Portuguese", "pt": "Portuguese",
    "japanese": "Japanese", "jp": "Japanese", "ja": "Japanese",
    "korean": "Korean", "ko": "Korean", "kr": "Korean",
    "chinese": "Chinese", "mandarin": "Chinese", "zh": "Chinese",
    "arabic": "Arabic", "ar": "Arabic",
    "russian": "Russian", "ru": "Russian",
    "hindi": "Hindi", "hi": "Hindi",
    "dutch": "Dutch", "nl": "Dutch",
    "polish": "Polish", "pl": "Polish",
    "turkish": "Turkish", "tr": "Turkish",
    "swedish": "Swedish", "sv": "Swedish",
    "greek": "Greek", "el": "Greek",
}

DEFAULT_LANGUAGE = "Spanish"


def resolve_language(raw: str) -> str:
    """Normalize user input to a proper language name."""
    key = raw.strip().lower().replace("-", "").replace("_", "")
    return LANGUAGE_ALIASES.get(key, raw.strip().title())


def build_system_prompt(target_language: str) -> str:
    return f"""You are a translation engine. You only output translated text, nothing else.

- If the input is in English, output the {target_language} translation only.
- If the input is in {target_language}, output the English translation only.
- If the input is in neither, output only: "Couldn't detect English or {target_language}."
- Keep it casual, like texting a friend. Match the energy, slang, and emoji of the original.
- Single words are valid input — translate them directly with no extra output. "Hello" in English becomes "Hallo" in German, nothing else.
- Never explain, never add context, never respond conversationally. Output only the translated text."""


def translate(text: str, system_prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
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


def copy_to_clipboard(text: str) -> bool:
    """Try to copy to clipboard (Windows/macOS/Linux)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def prompt_for_language() -> str:
    """Ask user which language to translate to/from at startup."""
    print(f"  Target language (default: {DEFAULT_LANGUAGE}): ", end="")
    raw = input().strip()
    if not raw:
        return DEFAULT_LANGUAGE
    resolved = resolve_language(raw)
    return resolved


def main():
    print("🌎 Multilingual Translator — English ↔ Any Language")
    print(f"   Model: {OLLAMA_MODEL}")
    print()

    target_language = prompt_for_language()
    system_prompt = build_system_prompt(target_language)

    print(f"\n   Translating English ↔ {target_language}")
    print("   Type your message and press Enter. Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            print("⏳ Translating...", end="\r")
            translation = translate(user_input, system_prompt)

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