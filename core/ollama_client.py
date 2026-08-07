"""Ollama HTTP client – communicates with the local Ollama server."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL


# ---------------------------------------------------------------------------
# Vision chat
# ---------------------------------------------------------------------------

def chat_vision(
    prompt: str,
    images: list[Path],
    *,
    model: str | None = None,
    stream: bool = False,
) -> str:
    """Send a vision chat request to Ollama.

    Args:
        prompt: The text prompt/system instruction.
        images: List of image file paths to attach.
        model: Override the default model name.
        stream: Request a streaming response (not yet implemented).

    Returns:
        The assistant's text response.
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"

    # Encode images as base64
    image_b64: list[str] = []
    for img in images:
        if not img.is_file():
            raise FileNotFoundError(f"Image not found: {img}")
        with open(img, "rb") as f:
            import base64
            image_b64.append(base64.b64encode(f.read()).decode("ascii"))

    payload: dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": image_b64,
            }
        ],
        "stream": stream,
    }

    start = time.time()
    response = requests.post(url, json=payload, timeout=300)
    elapsed = time.time() - start

    response.raise_for_status()
    data = response.json()

    return data.get("message", {}).get("content", "")


def generate_vision(
    prompt: str,
    images: list[Path],
    *,
    model: str | None = None,
) -> str:
    """Send a /api/generate vision request to Ollama.

    This is the simpler non-chat endpoint, suitable for batch frame analysis.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    image_b64: list[str] = []
    for img in images:
        if not img.is_file():
            raise FileNotFoundError(f"Image not found: {img}")
        with open(img, "rb") as f:
            import base64
            image_b64.append(base64.b64encode(f.read()).decode("ascii"))

    payload: dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "images": image_b64,
        "stream": False,
    }

    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    data = response.json()

    return data.get("response", "")


# ---------------------------------------------------------------------------
# Health / introspection
# ---------------------------------------------------------------------------

def is_ollama_running() -> bool:
    """Return ``True`` when the Ollama server is reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def list_available_models() -> list[str]:
    """Return the names of models available in Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except (requests.RequestException, KeyError):
        return []


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def parse_json_from_response(text: str) -> Any:
    """Best-effort JSON extraction from an LLM text response.

    Handles:
      - Pure JSON
      - JSON wrapped in ```json ... ``` fences
      - JSON embedded in prose
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Look for fenced code block
    import re
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Look for first [...] or {...} block
    bracket_match = re.search(r"[\[\{].*[\]\}]", text, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract JSON from AI response")