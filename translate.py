#!/usr/bin/env python3
"""
translate.py — Multilingual English <-> Any Language translator
Uses your local Ollama setup. Pick your target language at startup.
Usage: python translate.py
"""

import subprocess
import sys
import json
import re

# Windows: set console to UTF-8 so accented chars and foreign scripts render correctly
if sys.platform == "win32":
    # chcp is a shell built-in on Windows, so run it through cmd.
    subprocess.run("chcp 65001 >NUL", shell=True, check=False)
    stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
    stdin_reconfigure = getattr(sys.stdin, "reconfigure", None)
    stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
    if callable(stdout_reconfigure):
        stdout_reconfigure(encoding="utf-8", errors="replace")
    if callable(stdin_reconfigure):
        stdin_reconfigure(encoding="utf-8", errors="replace")
    if callable(stderr_reconfigure):
        stderr_reconfigure(encoding="utf-8", errors="replace")


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
- Output exactly one line. Do not add labels like "Translation:" or quote marks.
- Never explain, never add context, never respond conversationally. Output only the translated text."""


def sanitize_translation(text: str) -> str:
    """Keep only the translated line if the model adds wrappers or labels."""
    cleaned = text.strip().strip('"').strip("'")

    # Keep the first non-empty line to avoid extra explanations.
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = lines[0] if lines else cleaned

    # Remove common prefixes some models add.
    cleaned = re.sub(r"^(translation|translated text|english|german|spanish|french)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def translate(text: str, system_prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST",
             "http://localhost:11434/api/chat",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, timeout=30
        )
        stdout_text = result.stdout.decode("utf-8", errors="replace")
        response = json.loads(stdout_text)
        return sanitize_translation(response["message"]["content"])
    except subprocess.TimeoutExpired:
        print("❌ Ollama timed out. Is it running? Try: ollama serve")
        sys.exit(1)
    except (json.JSONDecodeError, KeyError):
        raw = result.stdout.decode("utf-8", errors="replace") if "result" in locals() else ""
        print("❌ Unexpected response from Ollama.")
        print("Raw output:", raw[:300])
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