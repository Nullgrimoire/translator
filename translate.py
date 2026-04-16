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
import shutil

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
USE_EXACT_SINGLE_WORD_OVERRIDES = False

EXACT_SINGLE_WORD_OVERRIDES = {
    "german": {
        "en_to_target": {
            "hello": "Hallo",
            "hi": "Hallo",
        },
        "target_to_en": {
            "hallo": "Hello",
        },
    }
}


def resolve_language(raw: str) -> str:
    """Normalize user input to a proper language name."""
    key = raw.strip().lower().replace("-", "").replace("_", "")
    return LANGUAGE_ALIASES.get(key, raw.strip().title())


def build_translation_prompt(target_language: str, source_language: str, destination_language: str) -> str:
    return f"""You are a translation engine.

- Translate from {source_language} to {destination_language} only.
- Keep it casual, like texting a friend. Match the energy, slang, and emoji of the original.
- Single words are valid input. Keep output short and natural for texting.
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


def has_emoji(text: str) -> bool:
    """Basic emoji detector for common Unicode emoji blocks."""
    return bool(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text))


def normalize_short_translation(source_text: str, translated_text: str) -> str:
    """Keep short translations literal and clean when source is short/plain."""
    source_tokens = source_text.strip().split()
    candidate = translated_text.strip()
    source_lower = source_text.strip().lower()
    candidate_lower = candidate.lower()

    # Prefer literal greeting equivalents instead of casual paraphrases.
    if source_lower == "hallo" and candidate_lower in {"hi", "hey"}:
        candidate = "Hello"
    elif source_lower == "hello" and candidate_lower in {"hi", "hey"}:
        candidate = "Hallo"

    # If user did not include emoji, do not add emoji for single-word translation.
    if len(source_tokens) <= 2 and not has_emoji(source_text):
        candidate = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", candidate).strip()

    # Trim noisy trailing punctuation for short plain outputs.
    if len(source_tokens) <= 2:
        candidate = re.sub(r"[.!?]+$", "", candidate).strip()

    return candidate


def exact_single_word_override(text: str, target_language: str, direction: str) -> str:
    """Return deterministic single-word translation for known pairs, else empty string."""
    words = text.strip().split()
    if len(words) != 1:
        return ""

    key = words[0].lower()
    lang_rules = EXACT_SINGLE_WORD_OVERRIDES.get(target_language.lower(), {})
    direction_rules = lang_rules.get("en_to_target" if direction == "EN" else "target_to_en", {})
    return direction_rules.get(key, "")


def is_plausible_translation(source_text: str, translated_text: str) -> bool:
    """Reject obvious non-translation chatter from small models."""
    if not translated_text:
        return False

    lowered = translated_text.lower()
    if re.search(r"\b(very nice|sure|here you go|translation)\b", lowered):
        return False

    # For one-word input, a long sentence is usually model drift.
    source_tokens = source_text.strip().split()
    translated_tokens = translated_text.strip().split()
    if len(source_tokens) == 1 and len(translated_tokens) > 3:
        return False

    # Keep single-word outputs mostly literal and compact.
    if len(source_tokens) == 1 and has_emoji(translated_text) and not has_emoji(source_text):
        return False

    return True


def clear_status_line():
    """Clear spinner/status text so the next print does not leave artifacts."""
    width = shutil.get_terminal_size(fallback=(100, 20)).columns
    print("\r" + (" " * max(10, width - 1)) + "\r", end="")


def call_ollama(messages, num_predict: int = 80) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": num_predict
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

    return ""


def detect_input_language(text: str, target_language: str) -> str:
    """Return EN, TARGET, or OTHER."""
    detector_prompt = (
        "Classify the input language and output exactly one token: EN, TARGET, or OTHER.\n"
        "EN means the text is English.\n"
        f"TARGET means the text is {target_language}.\n"
        "OTHER means it is neither English nor target.\n"
        "Output one token only."
    )

    raw = call_ollama(
        [
            {"role": "system", "content": detector_prompt},
            {"role": "user", "content": text}
        ],
        num_predict=6
    ).strip().lower()

    if raw in {"en", "english"}:
        return "EN"
    if raw in {"target", target_language.lower()}:
        return "TARGET"
    if raw in {"other", "neither", "unknown"}:
        return "OTHER"

    # Lightweight fallback heuristics for common cases.
    lowered = text.lower()
    if re.search(r"\b(the|and|is|are|you|hello|thanks|please)\b", lowered):
        return "EN"
    if target_language.lower() == "german" and re.search(r"[äöüß]|\b(und|ist|du|hallo|danke|sch[oö]n|sehr)\b", lowered):
        return "TARGET"
    return "OTHER"


def translate(text: str, target_language: str) -> str:
    direction = detect_input_language(text, target_language)
    if direction == "OTHER":
        return f"Couldn't detect English or {target_language}."

    if USE_EXACT_SINGLE_WORD_OVERRIDES:
        exact = exact_single_word_override(text, target_language, direction)
        if exact:
            return exact

    if direction == "EN":
        source_language = "English"
        destination_language = target_language
    else:
        source_language = target_language
        destination_language = "English"

    system_prompt = build_translation_prompt(target_language, source_language, destination_language)
    strict_user_prompt = (
        f"Translate this from {source_language} to {destination_language}. "
        "Output only the translation text. No labels, no explanations.\n"
        f"Text: {text}"
    )

    for attempt in range(2):
        user_content = text if attempt == 0 else strict_user_prompt
        candidate = call_ollama(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            num_predict=80
        )
        candidate = normalize_short_translation(text, candidate)
        if is_plausible_translation(text, candidate) or attempt == 1:
            return candidate

    return text


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

    print(f"\n   Translating English ↔ {target_language}")
    print("   Type your message and press Enter. Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            print("⏳ Translating...", end="\r")
            translation = translate(user_input, target_language)
            clear_status_line()

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