"""
enrichment/providers.py

LLM provider adapters for the FEG enrichment pipeline.

Each provider wraps a specific SDK and normalises the call interface and
usage reporting. Switch providers at runtime via env vars or CLI flags:

  FEG_PROVIDER=anthropic (default) | gemini
  FEG_MODEL=<model id>            (overrides per-provider default)

  python3 pipeline/enrich.py --provider gemini --model gemini-3.1-pro-preview
  python3 pipeline/enrich.py --provider gemini --thinking low

API keys:
  Anthropic: ANTHROPIC_API_KEY
  Gemini:    GEMINI_API_KEY

Gemini context cache:
  The system prompt (~9k tokens) is uploaded once to Gemini's Context Cache
  API with a 30-day TTL. The cache ID is written to pipeline/gemini_cache_id.txt
  and reused across sessions. On restart, the file is read and the cache is
  validated before use. Falls back to per-call system prompt if caching fails
  (e.g. model minimum token threshold not met).
"""

from __future__ import annotations

import datetime
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import anthropic as _anthropic
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_CACHE_ID_FILE = Path(__file__).resolve().parent.parent / "pipeline" / "gemini_cache_id.txt"
_CACHE_TTL_DAYS = 30

# google-genai SDK (replaces deprecated google-generativeai)
# from google import genai; from google.genai import types


# ─── Normalized usage ─────────────────────────────────────────────────────────


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    thinking_tokens: int = 0

    def __str__(self) -> str:
        parts = [f"in={self.input_tokens}", f"out={self.output_tokens}"]
        if self.cached_tokens:
            parts.append(f"cached={self.cached_tokens}")
        if self.thinking_tokens:
            parts.append(f"thinking={self.thinking_tokens}")
        return " ".join(parts)


# ─── Anthropic ────────────────────────────────────────────────────────────────

DEFAULT_MODEL_ANTHROPIC = "claude-sonnet-4-6"


class AnthropicProvider:
    def __init__(self, model: str = DEFAULT_MODEL_ANTHROPIC) -> None:
        self.model = model
        self._client = _anthropic.Anthropic()

    @retry(
        retry=retry_if_exception_type(
            (_anthropic.RateLimitError, _anthropic.InternalServerError)
        ),
        wait=wait_exponential(multiplier=30, min=30, max=180),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def call(self, system_prompt: str, user_message: str) -> tuple[str, Usage]:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )
        if not response.content or not response.content[0].text.strip():
            raise ValueError(f"Empty response (stop_reason={response.stop_reason!r})")
        raw = response.content[0].text
        u = response.usage
        return raw, Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cached_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        )


# ─── Gemini ───────────────────────────────────────────────────────────────────

DEFAULT_MODEL_GEMINI = "gemini-3.1-pro-preview"


def _is_transient_gemini_error(exc: BaseException) -> bool:
    return type(exc).__name__ in {
        "ResourceExhausted", "ServiceUnavailable", "InternalServerError",
        "ClientError",  # google-genai wraps some 429s as ClientError
    }


class GeminiProvider:
    def __init__(
        self,
        model: str = DEFAULT_MODEL_GEMINI,
        thinking_level: str | None = None,
        cache_id_file: Path = _CACHE_ID_FILE,
    ) -> None:
        from google import genai  # lazy — not required for Anthropic users
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set")

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self.model = model
        self._cache_id_file = cache_id_file
        self._thinking_level = thinking_level

        # Context cache state — initialised lazily on first call.
        self._cache_name: str | None = None   # cache resource name, or None = no cache
        self._cache_initialized = False
        self._cache_lock = threading.Lock()

    def _build_config(self, cache_name: str | None, system_prompt: str | None) -> object:
        """Build a GenerateContentConfig for a single call."""
        from enrichment.schema import ExerciseEnrichment

        kwargs: dict = {
            "response_mime_type": "application/json",
            "response_schema": ExerciseEnrichment,
        }
        if cache_name:
            kwargs["cached_content"] = cache_name
        else:
            kwargs["system_instruction"] = system_prompt

        kwargs["thinking_config"] = self._types.ThinkingConfig(
            thinking_level=self._thinking_level if self._thinking_level else None,
            thinking_budget=0 if not self._thinking_level else None,
        )
        return self._types.GenerateContentConfig(**kwargs)

    def _ensure_cache(self, system_prompt: str) -> str | None:
        """Return a valid cache resource name, or None if caching is unavailable.

        Thread-safe. Persists cache name to file so it survives across sessions
        for the full multi-day enrichment run (TTL = 30 days).
        """
        with self._cache_lock:
            if self._cache_initialized:
                return self._cache_name

            # Try to reuse a cache from a previous session.
            if self._cache_id_file.exists():
                saved_name = self._cache_id_file.read_text().strip()
                try:
                    cache = self._client.caches.get(name=saved_name)
                    # Verify not expired.
                    if cache.expire_time and cache.expire_time > datetime.datetime.now(datetime.timezone.utc):
                        print(f"  [gemini cache] Reusing {saved_name} (expires {cache.expire_time.date()})")
                        self._cache_name = saved_name
                        self._cache_initialized = True
                        return self._cache_name
                    print(f"  [gemini cache] {saved_name!r} has expired — creating new cache")
                except Exception:
                    print(f"  [gemini cache] {saved_name!r} not found — creating new cache")

            # Create a new cache.
            try:
                cache = self._client.caches.create(
                    model=self.model,
                    config=self._types.CreateCachedContentConfig(
                        system_instruction=system_prompt,
                        ttl=f"{_CACHE_TTL_DAYS * 86400}s",
                    ),
                )
                self._cache_id_file.write_text(cache.name)
                print(
                    f"  [gemini cache] Created {cache.name} "
                    f"(TTL={_CACHE_TTL_DAYS}d) → {self._cache_id_file}"
                )
                self._cache_name = cache.name
            except Exception as e:
                print(f"  [gemini cache] Unavailable ({e}) — using per-call system prompt")
                self._cache_name = None

            self._cache_initialized = True
            return self._cache_name

    @retry(
        retry=retry_if_exception(_is_transient_gemini_error),
        wait=wait_exponential(multiplier=10, min=10, max=120),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def call(self, system_prompt: str, user_message: str) -> tuple[str, Usage]:
        cache_name = self._ensure_cache(system_prompt)
        config = self._build_config(
            cache_name=cache_name,
            system_prompt=system_prompt if not cache_name else None,
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=user_message,
            config=config,
        )
        u = response.usage_metadata
        return response.text, Usage(
            input_tokens=u.prompt_token_count or 0,
            output_tokens=u.candidates_token_count or 0,
            cached_tokens=u.cached_content_token_count or 0,
            thinking_tokens=u.thoughts_token_count or 0,
        )


# ─── Factory ──────────────────────────────────────────────────────────────────


def make_provider(
    provider: str | None = None,
    model: str | None = None,
    thinking_level: str | None = None,
) -> AnthropicProvider | GeminiProvider:
    """Create a provider instance.

    Resolution order for provider/model:
      1. Explicit argument
      2. FEG_PROVIDER / FEG_MODEL env vars
      3. Per-provider default
    """
    provider = provider or os.environ.get("FEG_PROVIDER", "anthropic")
    model = model or os.environ.get("FEG_MODEL") or None

    if provider == "anthropic":
        return AnthropicProvider(model=model or DEFAULT_MODEL_ANTHROPIC)
    elif provider == "gemini":
        return GeminiProvider(
            model=model or DEFAULT_MODEL_GEMINI,
            thinking_level=thinking_level,
        )
    else:
        raise ValueError(
            f"Unknown provider {provider!r}. "
            "Set FEG_PROVIDER to 'anthropic' or 'gemini'."
        )
