#!/usr/bin/env python3
"""Terminal translator for casual English <-> target language chat using Ollama.

This script is designed for day-to-day texting support:
- choose a target language at startup
- auto-detect whether each message is English or target language
- translate in the opposite direction
- copy translated output to clipboard
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_NAME = "Multilingual Translator"
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_LANGUAGE = "Spanish"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

STYLE_CASUAL = "casual"
STYLE_EXACT = "exact"

LANGUAGE_ALIASES = {
    "spanish": "Spanish", "espanol": "Spanish", "español": "Spanish", "es": "Spanish",
    "french": "French", "francais": "French", "français": "French", "fr": "French",
    "german": "German", "deutsch": "German", "de": "German",
    "italian": "Italian", "italiano": "Italian", "it": "Italian",
    "portuguese": "Portuguese", "portugues": "Portuguese", "português": "Portuguese", "pt": "Portuguese",
    "japanese": "Japanese", "ja": "Japanese", "jp": "Japanese",
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
    "ukrainian": "Ukrainian", "uk": "Ukrainian",
    "romanian": "Romanian", "ro": "Romanian",
    "czech": "Czech", "cs": "Czech",
    "hungarian": "Hungarian", "hu": "Hungarian",
    "indonesian": "Indonesian", "id": "Indonesian",
    "vietnamese": "Vietnamese", "vi": "Vietnamese",
    "thai": "Thai", "th": "Thai",
    "hebrew": "Hebrew", "he": "Hebrew",
}


@dataclass(frozen=True)
class AppConfig:
    model: str
    style: str
    timeout_seconds: int


def ensure_windows_utf8() -> None:
    """Set UTF-8 console behavior on Windows terminals."""
    if sys.platform != "win32":
        return

    subprocess.run("chcp 65001 >NUL", shell=True, check=False)

    for stream in (sys.stdout, sys.stdin, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def resolve_language(raw: str) -> str:
    """Normalize user language input to a display name."""
    key = raw.strip().lower().replace("-", "").replace("_", "")
    if not key:
        return DEFAULT_LANGUAGE
    return LANGUAGE_ALIASES.get(key, raw.strip().title())


def clear_status_line() -> None:
    """Clear transient status text before printing final output."""
    width = shutil.get_terminal_size(fallback=(100, 20)).columns
    print("\r" + (" " * max(8, width - 1)) + "\r", end="")


def sanitize_output(text: str) -> str:
    """Trim common model wrappers to keep a clean single-line translation."""
    cleaned = text.strip().strip('"').strip("'")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = lines[0] if lines else cleaned
    cleaned = re.sub(
        r"^(translation|translated text|english|german|spanish|french)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def looks_noisy_translation(source_text: str, translated_text: str) -> bool:
    """Basic guardrail for obvious non-translation chatter."""
    if not translated_text:
        return True

    if re.search(r"\b(sure|here you go|translation|as an ai)\b", translated_text, re.IGNORECASE):
        return True

    source_words = source_text.strip().split()
    translated_words = translated_text.strip().split()
    if len(source_words) == 1 and len(translated_words) > 4:
        return True

    return False


def post_ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: int,
    num_predict: int,
) -> str:
    """Call Ollama chat endpoint and return message content."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": num_predict,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        OLLAMA_CHAT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        print(f"Error: Ollama HTTP {exc.code}: {exc.reason}")
        sys.exit(1)
    except URLError:
        print("Error: Could not connect to Ollama. Is it running at http://localhost:11434?")
        sys.exit(1)
    except TimeoutError:
        print("Error: Ollama request timed out.")
        sys.exit(1)

    try:
        data = json.loads(raw)
        return sanitize_output(data["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        print("Error: Unexpected response from Ollama.")
        print("Raw output:", raw[:300])
        sys.exit(1)


def build_translation_prompt(source_language: str, destination_language: str, style: str) -> str:
    """Build system prompt for translation style."""
    style_line = (
        "Keep the tone casual and natural for texting. Match slang and emoji from input."
        if style == STYLE_CASUAL
        else "Use direct, literal wording. Prefer dictionary-style translation."
    )
    return (
        "You are a translation engine.\n"
        f"Translate from {source_language} to {destination_language} only.\n"
        f"{style_line}\n"
        "Output exactly one line. No labels, no explanations, no quotes."
    )


def detect_input_direction(text: str, target_language: str, config: AppConfig) -> str:
    """Return EN, TARGET, or OTHER."""
    detector_prompt = (
        "Classify the input language and output one token only: EN, TARGET, or OTHER.\n"
        "EN: input is English.\n"
        f"TARGET: input is {target_language}.\n"
        "OTHER: input is neither."
    )

    result = post_ollama_chat(
        model=config.model,
        messages=[
            {"role": "system", "content": detector_prompt},
            {"role": "user", "content": text},
        ],
        timeout_seconds=config.timeout_seconds,
        num_predict=6,
    ).strip().lower()

    if result in {"en", "english"}:
        return "EN"
    if result in {"target", target_language.lower()}:
        return "TARGET"
    if result in {"other", "unknown", "neither"}:
        return "OTHER"
    return "OTHER"


def translate_message(text: str, target_language: str, config: AppConfig) -> str:
    """Translate text bidirectionally between English and target language."""
    direction = detect_input_direction(text, target_language, config)
    if direction == "OTHER":
        return f"Couldn't detect English or {target_language}."

    if direction == "EN":
        source_language = "English"
        destination_language = target_language
    else:
        source_language = target_language
        destination_language = "English"

    prompt = build_translation_prompt(source_language, destination_language, config.style)
    strict_retry_user_message = (
        f"Translate from {source_language} to {destination_language}. "
        "Output only translation text."
        f"\nText: {text}"
    )

    for attempt in range(2):
        user_content = text if attempt == 0 else strict_retry_user_message
        output = post_ollama_chat(
            model=config.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            timeout_seconds=config.timeout_seconds,
            num_predict=80,
        )
        if not looks_noisy_translation(text, output) or attempt == 1:
            return output

    return text


def copy_to_clipboard(text: str) -> bool:
    """Copy translated text to clipboard on Windows/macOS/Linux."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def prompt_for_language(default_language: str) -> str:
    """Interactive prompt for target language selection."""
    print(f"Target language (default: {default_language}): ", end="")
    raw = input().strip()
    return resolve_language(raw) if raw else default_language


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="English <-> Any Language translator powered by Ollama")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--style",
        choices=[STYLE_CASUAL, STYLE_EXACT],
        default=STYLE_CASUAL,
        help="Translation style (default: casual)",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)")
    parser.add_argument(
        "--default-language",
        default=DEFAULT_LANGUAGE,
        help=f"Default target language shown in prompt (default: {DEFAULT_LANGUAGE})",
    )
    return parser.parse_args()


def run() -> int:
    """Application entrypoint."""
    ensure_windows_utf8()
    args = parse_args()

    config = AppConfig(model=args.model, style=args.style, timeout_seconds=max(5, args.timeout))

    print(f"{APP_NAME} - English <-> Any Language")
    print(f"Model: {config.model}")
    print(f"Style: {config.style}")
    print()

    target_language = prompt_for_language(resolve_language(args.default_language))

    print(f"\nTranslating English <-> {target_language}")
    print("Type your message and press Enter. Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            print("Translating...", end="\r")
            translation = translate_message(user_input, target_language, config)
            clear_status_line()
            print(f"Translated: {translation}")

            if copy_to_clipboard(translation):
                print("(copied to clipboard)\n")
            else:
                print()
        except KeyboardInterrupt:
            print("\nBye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(run())