"""
Hybrid client — supports both Anthropic (Claude) and Google Gemini.

Provider assignment per stage:
  Anthropic  → Stages 2, 3, 5, 7  (core reasoning, quality-critical)
  Gemini     → Stages 4, 6        (validation, supplementary — cost saving)
  Gemini Pro → Stage 4.5          (large-context competitor site audit)

Both providers share the same call_structured() interface so stages
don't need to know which model they're using.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Literal, TypeVar

from google import genai as google_genai
from anthropic import Anthropic, APIError
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)

# ── Model constants ──────────────────────────────────────────────────────────
ANTHROPIC_SONNET   = "claude-sonnet-4-6"          # main reasoning model
GEMINI_FLASH       = "gemini-1.5-flash"            # fast + cheap
GEMINI_PRO         = "gemini-1.5-pro"              # 1M context window

DEFAULT_MODEL      = ANTHROPIC_SONNET
DEFAULT_MAX_TOKENS = 8000

Provider = Literal["anthropic", "gemini"]


# ── Client builders ──────────────────────────────────────────────────────────

def get_anthropic_client() -> Anthropic:
    """Build Anthropic client from env or Colab Secrets."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. "
            "In Colab Secrets: add key named ANTHROPIC_API_KEY and enable notebook access."
        )
    return Anthropic(api_key=api_key)


def _get_gemini_client():
    """Build Gemini client from env or Colab Secrets (new google-genai SDK)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. "
            "In Colab Secrets: add key named GEMINI_API_KEY and enable notebook access."
        )
    return google_genai.Client(api_key=api_key)


def _detect_provider(model: str) -> Provider:
    """Infer provider from model string."""
    if model.startswith("gemini"):
        return "gemini"
    return "anthropic"


# ── JSON extraction (shared) ─────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """
    Strip markdown fences and preamble/postamble from any JSON object.
    Both Claude and Gemini sometimes wrap output in fences despite instructions.
    """
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    first_brace = text.find("{")
    last_brace  = text.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
        raise ValueError(f"No JSON object found in response. Got:\n{text[:500]}")
    return text[first_brace : last_brace + 1]


# ── Prompt loader ─────────────────────────────────────────────────────────────

def load_prompt(name: str) -> str:
    """Load a system prompt from the prompts/ directory."""
    path = Path(__file__).parent.parent / "prompts" / f"{name}.txt"
    return path.read_text()


# ── Unified call_structured ───────────────────────────────────────────────────

def call_structured(
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = 2,
    stage: str = "unknown",
) -> T:
    """
    Call either Anthropic or Gemini based on the model string,
    then parse the JSON response into a pydantic model.

    Retries on transient API errors and malformed JSON.
    """
    provider = _detect_provider(model)
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if provider == "anthropic":
                text = _call_anthropic(system_prompt, user_message, model, max_tokens, stage)
            else:
                text = _call_gemini(system_prompt, user_message, model, stage)

            json_str = _extract_json(text)
            data     = json.loads(json_str)
            return response_model.model_validate(data)

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                user_message += (
                    f"\n\nIMPORTANT: Your previous response failed JSON validation. "
                    f"Error: {type(e).__name__}: {str(e)[:200]}. "
                    f"Return ONLY valid JSON — no fences, no commentary."
                )
                continue
            raise RuntimeError(
                f"Failed after {max_retries + 1} attempts. Last error: {e}"
            ) from e

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise

    raise RuntimeError(f"Unreachable. Last error: {last_error}")


# ── Provider-specific call helpers ────────────────────────────────────────────

def _call_anthropic(
    system_prompt: str,
    user_message: str,
    model: str,
    max_tokens: int,
    stage: str = "unknown",
) -> str:
    from stages.cost_tracker import tracker
    client   = get_anthropic_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    usage = response.usage
    tracker.log_llm_call(
        stage=stage, model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    return response.content[0].text


def _call_gemini(
    system_prompt: str,
    user_message: str,
    model: str,
    stage: str = "unknown",
) -> str:
    from stages.cost_tracker import tracker
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=google_genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )
    try:
        meta = response.usage_metadata
        tracker.log_llm_call(
            stage=stage, model=model,
            input_tokens=meta.prompt_token_count or 0,
            output_tokens=meta.candidates_token_count or 0,
        )
    except Exception:
        pass
    return response.text


# ── Convenience wrappers for stages ──────────────────────────────────────────

def call_anthropic_structured(
    system_prompt: str,
    user_message: str,
    response_model: type[T],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> T:
    """Always uses Anthropic Sonnet. For quality-critical stages."""
    return call_structured(
        system_prompt, user_message, response_model,
        model=ANTHROPIC_SONNET, max_tokens=max_tokens,
    )


def call_gemini_flash_structured(
    system_prompt: str,
    user_message: str,
    response_model: type[T],
) -> T:
    """Always uses Gemini Flash. For cost-saving stages (4, 6)."""
    return call_structured(
        system_prompt, user_message, response_model,
        model=GEMINI_FLASH,
    )


def call_gemini_pro_structured(
    system_prompt: str,
    user_message: str,
    response_model: type[T],
) -> T:
    """Always uses Gemini Pro (1M context). For competitor site audit (Stage 4.5)."""
    return call_structured(
        system_prompt, user_message, response_model,
        model=GEMINI_PRO,
    )
