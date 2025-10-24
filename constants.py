from __future__ import annotations
from typing import Tuple, List, Dict, Any
import os
from pathlib import Path

__all__ = [
    "DEFAULT_REALTIME_MODEL",
    "DEFAULT_VOICE",
    "DEFAULT_TRANSCRIBE_MODEL",
    "DEFAULT_MODALITIES",
    "OPENAI_BASE_URL",
    "OPENAI_BETA_HEADER_VALUE",
    "AI_AGENT_NAME",
    "AI_AGENT_ROLE",
    "SYSTEM_INSTRUCTIONS",
    "VAD_CONFIG",
    "MODEL_TEMPERATURE",
    "TOOL_DEFINITIONS",
    "get_realtime_session_url",
    "get_session_payload",
    "get_openai_headers",
]

DEFAULT_REALTIME_MODEL = os.getenv("DEFAULT_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "echo")
DEFAULT_TRANSCRIBE_MODEL = os.getenv("DEFAULT_TRANSCRIBE_MODEL", "whisper-1")
DEFAULT_MODALITIES: Tuple[str, ...] = ("text", "audio")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
OPENAI_BETA_HEADER_VALUE = os.getenv("OPENAI_BETA_HEADER_VALUE", "realtime=v1")

# --- Agent identity ---
AI_AGENT_NAME = "Ishmael"
AI_AGENT_ROLE = "Mahindra Automotive Sales Consultant"

# --- Load system instructions from external markdown file ---
def _load_system_instructions(path: str | None = None) -> str:
    # --- load my system_instructions.md ---
    base = Path(__file__).parent
    file_path = Path(path) if path else base / "system_instructions.md"
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback short instruction if file missing
        return f"You are {AI_AGENT_NAME}, a Mahindra sales consultant. (Detailed instructions file not found.)"

SYSTEM_INSTRUCTIONS = _load_system_instructions()

# --- VAD + Temperature config ---
VAD_CONFIG: Dict[str, Any] = {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 200,
    "silence_duration_ms": 1200,
}

# **No internal temperature validation — user requested removal**
MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.8"))

# --- Tools (immutable structure expected by runtime) ---
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "generate_conversation_summary",
        "description": (
            "Generate a structured summary of the conversation for internal storage: preferences, budget, "
            "vehicle interests, recommendations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "The current conversation session ID"}
            },
            "required": ["session_id"],
        },
    }
]

# --- Helper functions ---

def get_realtime_session_url(base: str | None = None) -> str:
    base_url = base or OPENAI_BASE_URL
    return f"{base_url.rstrip('/')}/v1/realtime/sessions"


def get_session_payload(
    *,
    model: str | None = None,
    modalities: Tuple[str, ...] | None = None,
    voice: str | None = None,
    instructions: str | None = None,
    vad: Dict[str, Any] | None = None,
    transcribe_model: str | None = None,
    temperature: float | None = None,
    tools: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    payload = {
        "model": model or DEFAULT_REALTIME_MODEL,
        "modalities": list(modalities or DEFAULT_MODALITIES),
        "voice": voice or DEFAULT_VOICE,
        "instructions": instructions or SYSTEM_INSTRUCTIONS,
        "turn_detection": vad or VAD_CONFIG,
        "input_audio_transcription": {"model": transcribe_model or DEFAULT_TRANSCRIBE_MODEL},
        "temperature": MODEL_TEMPERATURE if temperature is None else temperature,
        "tools": tools or TOOL_DEFINITIONS,
    }
    return payload

def get_openai_headers(api_key: str | None = None, include_beta: bool = True) -> Dict[str, str]:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OpenAI API key not provided (pass api_key or set OPENAI_API_KEY).")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if include_beta and OPENAI_BETA_HEADER_VALUE:
        headers["OpenAI-Beta"] = OPENAI_BETA_HEADER_VALUE
    return headers