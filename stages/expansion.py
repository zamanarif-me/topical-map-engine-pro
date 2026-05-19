"""
Stage 3: Topic Expansion.

The most important call in the pipeline. Given the central entity, supporting
entity, source context, and intake, generate 8-12 pillars with 6-10 clusters each.

If this produces weak pillars, everything downstream is weak. Evaluate this
stage against the WordPress fixture before trusting downstream stages.
"""

import json

from pydantic import BaseModel

from models import SeedInput, CentralEntity, Pillar
from stages._client import call_structured, load_prompt


class TopicExpansionResponse(BaseModel):
    """LLM response wrapper — just a list of pillars at this stage."""
    pillars: list[Pillar]


def expand_topics(seed: SeedInput, central: CentralEntity) -> list[Pillar]:
    """Run stage 3. Returns the list of pillars (with clusters but no queries/supplementary yet)."""
    system_prompt = load_prompt("topic_expansion")

    user_message = f"""Generate the topical map pillars and clusters for this site.

# Central Entity
{central.primary}

# Supporting Authority Entity
{central.supporting}

# Source Context
{central.source_context}

# Key Entities
{', '.join(central.key_entities)}

# Reasoning Behind These Choices
{central.reasoning}

# User Intake
```json
{json.dumps(seed.intake.model_dump(mode="json"), indent=2)}
```

# Seed Keyword
{seed.seed_keyword}

Generate 8-12 pillars with 6-10 clusters each, following all rules in the system prompt. Pay special attention to:
- At least 60% commercial intent pillars
- Priority assignment based on revenue services and focus areas
- Geographic pillars if geo targeting is specified
- No generic or duplicate pillars

Output ONLY valid JSON matching the schema."""

    response = call_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=TopicExpansionResponse,
        max_tokens=16000,  # this stage produces a lot of output
    )

    # Light validation: enforce the 8-12 pillar count and 6-10 cluster count
    # so problems surface here, not 5 stages later.
    pillar_count = len(response.pillars)
    if not (6 <= pillar_count <= 14):
        raise ValueError(
            f"Topic expansion returned {pillar_count} pillars, expected 8-12. "
            f"Inspect the output or retry. Pillars: {[p.title for p in response.pillars]}"
        )

    for pillar in response.pillars:
        cluster_count = len(pillar.clusters)
        if not (4 <= cluster_count <= 12):
            raise ValueError(
                f"Pillar '{pillar.title}' has {cluster_count} clusters, expected 6-10. "
                f"Inspect the output or retry."
            )

    return response.pillars
