# Multilingual Translator (Ollama CLI)

A lightweight terminal translator for casual texting.

This tool translates messages between English and a target language using a local Ollama model. It is designed for quick back-and-forth chat help and automatically copies each translation to your clipboard.

## Features

- Bidirectional translation: English <-> target language
- Casual or exact translation style
- Local inference with Ollama (no cloud API required)
- Automatic clipboard copy after each translation
- Windows UTF-8 console handling
- Clean CLI with model, timeout, and style flags

## Requirements

- Python 3.9+
- Ollama installed and running
- A pulled Ollama model (default: llama3.2:3b)

## Quick Start

1. Clone the repository.
2. Start Ollama:

~~~bash
ollama serve
~~~

3. Pull a model (if needed):

~~~bash
ollama pull llama3.2:3b
~~~

4. Run the translator:

~~~bash
python translate.py
~~~

## Usage

Start with defaults:

~~~bash
python translate.py
~~~

Use a different model:

~~~bash
python translate.py --model llama3.2:3b
~~~

Switch style:

~~~bash
python translate.py --style casual
python translate.py --style exact
~~~

Set startup defaults:

~~~bash
python translate.py --default-language German --timeout 30
~~~

## CLI Options

- --model: Ollama model name
- --style: casual or exact
- --timeout: request timeout in seconds
- --default-language: startup default language shown in prompt

## How It Works

1. Prompts for your target language.
2. Detects whether each input is English or target language.
3. Translates in the opposite direction.
4. Prints result and copies it to clipboard.

## Supported Languages

The script includes aliases for many common languages, including:

- Spanish
- French
- German
- Italian
- Portuguese
- Japanese
- Korean
- Chinese
- Arabic
- Russian
- Hindi
- Dutch
- Polish
- Turkish
- Swedish
- Greek
- Ukrainian
- Romanian
- Czech
- Hungarian
- Indonesian
- Vietnamese
- Thai
- Hebrew

You can also type a language name directly. Model quality may vary by language pair.

## Troubleshooting

If Ollama is not reachable:

~~~text
Error: Could not connect to Ollama. Is it running at http://localhost:11434?
~~~

Actions:

- Ensure Ollama is running: ollama serve
- Confirm the model is installed: ollama list
- Verify model name passed to --model

If clipboard copy fails on Linux, install xclip.

## Example Session

~~~text
Multilingual Translator - English <-> Any Language
Model: llama3.2:3b
Style: casual

Target language (default: Spanish): de

Translating English <-> German
Type your message and press Enter. Ctrl+C to quit.

You: hello
Translated: Hallo
(copied to clipboard)
~~~

## Project Status

Personal utility script, polished for public sharing.
Contributions and issue reports are welcome.
