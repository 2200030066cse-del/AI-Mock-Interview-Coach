"""Thin wrapper around a LangChain chat model client.

Centralizing LLM access here means:
  * API keys / model names / provider choice are read from environment
    variables in exactly one place.
  * Every agent gets consistent retry + JSON-repair behaviour "for free".
  * Token usage can be tracked centrally (see `TokenUsageTracker`).

No agent should import `langchain_openai` / `langchain_groq` directly --
everything goes through `get_llm()` / `call_llm_json()` below. Swapping
providers (OpenAI <-> Groq <-> any other LangChain chat model) is a
one-place change in `get_llm()`, never an agent-level change.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional, Type, TypeVar

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from utils.parser import extract_json

load_dotenv()

T = TypeVar("T", bound=BaseModel)

# "openai" or "groq". Groq offers a free tier and is handy for development/
# demoing this project without an OpenAI billing setup; OpenAI remains the
# default per the original tech-stack spec.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

_DEFAULT_MODELS = {
    "openai": "gpt-4.1",
    "groq": "llama-3.3-70b-versatile",
}
DEFAULT_MODEL = os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(LLM_PROVIDER, "gpt-4.1")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_prompt_cache: dict[str, str] = {}


def load_prompt(filename: str) -> str:
    """Load a system prompt from the `prompts/` directory, cached in memory.

    Keeping prompts in plain text files (rather than inline strings) lets
    them be edited, reviewed, and versioned independently of agent code.
    """
    if filename not in _prompt_cache:
        path = _PROMPTS_DIR / filename
        _prompt_cache[filename] = path.read_text(encoding="utf-8")
    return _prompt_cache[filename]


class TokenUsageTracker:
    """Process-wide, thread-safe counter for prompt/completion tokens.

    Used by the UI sidebar to show a running "Token Usage" metric. This is
    a lightweight bonus feature, not a billing-grade accounting system.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_calls = 0

    def add(self, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.total_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def reset(self) -> None:
        with self._lock:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_calls = 0

    def snapshot(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
        }


usage_tracker = TokenUsageTracker()


def get_llm(temperature: Optional[float] = None, streaming: bool = False) -> BaseChatModel:
    """Build a configured chat model client for whichever `LLM_PROVIDER` is set.

    Raises a clear error rather than a confusing SDK stack trace if the API
    key hasn't been set up yet.
    """
    temp = DEFAULT_TEMPERATURE if temperature is None else temperature

    if LLM_PROVIDER == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env, set "
                "LLM_PROVIDER=groq, and add a free key from https://console.groq.com/keys."
            )
        from langchain_groq import ChatGroq

        return ChatGroq(model=DEFAULT_MODEL, temperature=temp, api_key=api_key)

    if LLM_PROVIDER == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=DEFAULT_MODEL, temperature=temp, api_key=api_key, streaming=streaming)

    raise RuntimeError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Use 'openai' or 'groq'.")


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    temperature: Optional[float] = None,
    max_retries: int = 2,
) -> T:
    """Call the LLM and parse its response into `schema`.

    On a validation/parsing failure, retries with the raw error appended to
    the prompt so the model can self-correct -- this is far more reliable
    than a single hopeful call, especially for nested JSON schemas.
    """
    llm = get_llm(temperature=temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        response = llm.invoke(messages)
        _track_usage(response)
        raw_text = response.content if isinstance(response.content, str) else str(response.content)

        try:
            payload = extract_json(raw_text)
            return schema.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - broad on purpose, we retry
            last_error = exc
            messages.append(HumanMessage(
                content=(
                    "Your previous response could not be parsed as valid JSON matching "
                    f"the required schema. Error: {exc}\n\n"
                    "Respond again with ONLY a single valid JSON object matching the "
                    "required schema. No markdown fences, no commentary."
                )
            ))

    raise ValueError(f"LLM failed to produce valid '{schema.__name__}' JSON after retries: {last_error}")


def call_llm_text(system_prompt: str, user_prompt: str, temperature: Optional[float] = None) -> str:
    """Call the LLM and return raw text (used for simple, non-JSON turns)."""
    llm = get_llm(temperature=temperature)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    response = llm.invoke(messages)
    _track_usage(response)
    return response.content if isinstance(response.content, str) else str(response.content)


def _track_usage(response) -> None:
    usage = getattr(response, "response_metadata", {}).get("token_usage") if hasattr(response, "response_metadata") else None
    if usage:
        usage_tracker.add(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
