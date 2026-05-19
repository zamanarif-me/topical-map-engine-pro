"""
Stage 4: Topic Validation (Hybrid — Gemini Flash)

Validates each pillar and cluster against SERP data from Stage 3.5.
Uses Gemini Flash (free tier) instead of Anthropic web_search — saves ~$0.20/run.

Validation logic:
  - If Serper found organic results for the pillar → "strong"
  - If PAA questions exist for the pillar → boosts to "strong"
  - If only thin results → "medium"
  - If no results at all → "weak"

This is data-driven validation, not LLM guessing.
"""

from typing import Literal

from models import Pillar
from stages.serp import SerpData, serp_data_to_summary
from stages._client import call_gemini_flash_structured, load_prompt
from pydantic import BaseModel


class TopicValidation(BaseModel):
    topic_id: str
    topic_title: str
    signal: Literal["strong", "medium", "weak"]
    reasoning: str


class ValidationResponse(BaseModel):
    validations: list[TopicValidation]


def _data_driven_signal(serp: SerpData) -> tuple[str, str]:
    """
    Determine validation signal purely from Serper data — no LLM needed.
    Returns (signal, reasoning).
    """
    organic_count = len(serp.organic)
    paa_count     = len(serp.paa)

    if organic_count >= 5:
        signal    = "strong"
        reasoning = f"Found {organic_count} organic results and {paa_count} PAA questions — strong real-world footprint."
    elif organic_count >= 2:
        signal    = "medium"
        reasoning = f"Found {organic_count} organic results — topic exists but coverage is thin."
    else:
        signal    = "weak"
        reasoning = f"Only {organic_count} organic results found — limited search demand evidence."

    # PAA presence upgrades medium → strong
    if signal == "medium" and paa_count >= 3:
        signal    = "strong"
        reasoning += f" Upgraded to strong: {paa_count} PAA questions indicate active search intent."

    return signal, reasoning


def validate_topics(
    pillars: list[Pillar],
    serp_data: dict[str, SerpData] | None = None,
) -> dict[str, TopicValidation]:
    """
    Validate all pillars and clusters.

    If serp_data is provided (from Stage 3.5), uses data-driven signals — fast and free.
    If serp_data is None, falls back to Gemini Flash LLM validation.
    """
    validations: dict[str, TopicValidation] = {}

    if serp_data:
        # Fast path — purely data-driven from Serper results
        for pillar in pillars:
            serp = serp_data.get(pillar.id)
            if serp:
                signal, reasoning = _data_driven_signal(serp)
            else:
                signal, reasoning = "medium", "No SERP data available — defaulting to medium."

            validations[pillar.id] = TopicValidation(
                topic_id=pillar.id,
                topic_title=pillar.title,
                signal=signal,
                reasoning=reasoning,
            )

            # Clusters: if parent pillar is strong, clusters default to medium
            # (we don't burn Serper calls on every cluster — too expensive)
            for cluster in pillar.clusters:
                cluster_signal = "medium" if signal == "strong" else "weak"
                validations[cluster.id] = TopicValidation(
                    topic_id=cluster.id,
                    topic_title=cluster.title,
                    signal=cluster_signal,
                    reasoning=f"Inherited from parent pillar signal: {signal}.",
                )
    else:
        # Fallback: Gemini Flash LLM validation (no Serper data available)
        _validate_with_gemini(pillars, validations)

    # Ensure every topic has an entry
    for pillar in pillars:
        if pillar.id not in validations:
            validations[pillar.id] = TopicValidation(
                topic_id=pillar.id,
                topic_title=pillar.title,
                signal="medium",
                reasoning="Validation not completed — defaulting to medium.",
            )
        for cluster in pillar.clusters:
            if cluster.id not in validations:
                validations[cluster.id] = TopicValidation(
                    topic_id=cluster.id,
                    topic_title=cluster.title,
                    signal="medium",
                    reasoning="Validation not completed — defaulting to medium.",
                )

    return validations


def _validate_with_gemini(
    pillars: list[Pillar],
    validations: dict[str, TopicValidation],
) -> None:
    """Gemini Flash fallback validation when no Serper data is available."""
    import json
    system_prompt = load_prompt("web_validation")

    for pillar in pillars:
        batch = [{"id": pillar.id, "title": pillar.title, "type": "pillar"}]
        batch.extend(
            {"id": c.id, "title": c.title, "type": "cluster"}
            for c in pillar.clusters
        )

        user_message = f"""Validate these SEO topics. For each one, assess whether it has real-world search demand.
Output ONLY valid JSON.

Topics to validate:
{json.dumps(batch, indent=2)}"""

        try:
            response = call_gemini_flash_structured(
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=ValidationResponse,
            )
            for v in response.validations:
                validations[v.topic_id] = v
        except Exception as e:
            for item in batch:
                if item["id"] not in validations:
                    validations[item["id"]] = TopicValidation(
                        topic_id=item["id"],
                        topic_title=item["title"],
                        signal="medium",
                        reasoning=f"Gemini validation failed: {type(e).__name__}",
                    )

