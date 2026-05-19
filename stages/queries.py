"""
Stage 5: Query Generation — Batched (cost optimized)

Before: 10 separate LLM calls (one per pillar) = ~60,000 output tokens
After:  2 batched calls (5 pillars each) = ~20,000 output tokens
Saving: ~40,000 output tokens = ~$0.60
"""

import json
from pydantic import BaseModel

from models import Pillar, Query, QueryType, Intent
from stages._client import call_anthropic_structured, load_prompt
from stages.serp import SerpData, serp_data_to_summary


class _RawQuery(BaseModel):
    text: str
    intent: Intent


class _PillarQueries(BaseModel):
    pillar_id: str
    representative_queries: list[_RawQuery]
    clusters: list[dict]


class BatchQueryResponse(BaseModel):
    pillars: list[_PillarQueries]


BATCH_QUERY_PROMPT = """You are a semantic SEO strategist trained on Koray's query framework.

For each pillar, generate:
- 2 representative queries (broad intent, pillar-level)
- 3-4 represented queries per cluster (long-tail, specific)

Rules:
- Lowercase, natural search phrasing
- Commercial intent for commercial pillars
- No duplicates across pillars

Output ONLY valid JSON:
{
  "pillars": [
    {
      "pillar_id": "pillar_id_here",
      "representative_queries": [
        {"text": "query text", "intent": "commercial"}
      ],
      "clusters": [
        {
          "cluster_id": "cluster_id_here",
          "represented_queries": [
            {"text": "long tail query", "intent": "informational"}
          ]
        }
      ]
    }
  ]
}"""


def _build_pillar_context(
    pillar: Pillar,
    serp_data: dict[str, SerpData] | None,
) -> dict:
    """Compact pillar representation for the batch prompt."""
    ctx = {
        "pillar_id":    pillar.id,
        "title":        pillar.title,
        "intent":       pillar.intent.value,
        "entities":     pillar.related_entities[:4],
        "clusters": [
            {"cluster_id": c.id, "title": c.title, "intent": c.intent.value}
            for c in pillar.clusters
        ],
    }
    # Add PAA if available
    if serp_data and pillar.id in serp_data:
        paa = serp_data[pillar.id].paa[:5]
        if paa:
            ctx["paa_questions"] = paa
    return ctx


def generate_queries_for_all(
    pillars: list[Pillar],
    serp_data: dict[str, SerpData] | None = None,
    batch_size: int = 5,
) -> list[Pillar]:
    """
    Generate queries for all pillars in batches.
    batch_size=5 means 2 calls for 10 pillars instead of 10 calls.
    """
    system_prompt = BATCH_QUERY_PROMPT

    # Process in batches
    for i in range(0, len(pillars), batch_size):
        batch = pillars[i : i + batch_size]
        batch_ctx = [_build_pillar_context(p, serp_data) for p in batch]

        user_message = f"""Generate queries for these {len(batch)} pillars.

```json
{json.dumps(batch_ctx, indent=2)}
```

Output ONLY valid JSON with all {len(batch)} pillars in the response."""

        try:
            response = call_anthropic_structured(
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=BatchQueryResponse,
                max_tokens=6000,
            )

            # Map results back to pillar objects
            result_map = {r.pillar_id: r for r in response.pillars}

            for pillar in batch:
                result = result_map.get(pillar.id)
                if not result:
                    continue

                # Representative queries
                pillar.representative_queries = [
                    Query(
                        text=q.text,
                        type=QueryType.REPRESENTATIVE,
                        intent=q.intent,
                        parent_cluster_id=pillar.id,
                    )
                    for q in result.representative_queries
                ]

                # Represented queries
                cluster_lookup = {c.id: c for c in pillar.clusters}
                for cq in result.clusters:
                    cluster = cluster_lookup.get(cq.get("cluster_id", ""))
                    if not cluster:
                        continue
                    cluster.represented_queries = [
                        Query(
                            text=q["text"],
                            type=QueryType.REPRESENTED,
                            intent=Intent(q.get("intent", "informational")),
                            parent_cluster_id=cluster.id,
                        )
                        for q in cq.get("represented_queries", [])
                    ]

        except Exception as e:
            print(f"  [queries] Batch {i//batch_size + 1} failed: {e}")

    return pillars
