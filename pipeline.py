"""
Top-level pipeline — v1.5 (Hybrid: Anthropic + Gemini + Serper)

Stage assignments:
  Anthropic Sonnet → Stages 2, 3, 5, 7  (quality-critical reasoning)
  Gemini Flash     → Stages 4, 6        (validation, supplementary — cost saving)
  Serper.dev       → Stage 3.5          (SERP + PAA + competitor data)
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

from models import SeedInput, TopicalMap, EngineOutput
from stages.intake import load_intake_from_json
from stages.central_entity import extract_central_entity
from stages.expansion import expand_topics
from stages.serp import pull_serp_for_pillars
from stages.validation import validate_topics
from stages.queries import generate_queries_for_all
from stages.tiering import generate_supplementary_for_all
from stages.linking import build_linking_plan
from stages.geo import derive_geo_pages
from stages.render import save_outputs
from stages.cost_tracker import tracker


def _log(msg: str):
    print(f"[pipeline] {msg}", flush=True)


def run_pipeline(
    seed: SeedInput,
    output_dir: str | Path,
    skip_serp: bool = False,
    skip_validation: bool = False,
    serp_geo: str = "us",
    serp_lang: str = "en",
) -> EngineOutput:
    """
    Run all stages end-to-end.

    skip_serp:       Skip Stage 3.5 (saves Serper calls during prompt iteration)
    skip_validation: Skip Stage 4 entirely
    serp_geo:        Serper country code — "us", "gb", "au" etc.
    serp_lang:       Language code — "en" etc.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tracker.reset()

    # Stage 2: Central Entity (Anthropic)
    _log("Stage 2: extracting central entity [Anthropic]...")
    central = extract_central_entity(seed)
    _log(f"  Primary: {central.primary}")
    _checkpoint(output_dir, "stage2", {"central_entity": central.model_dump(mode="json")})

    # Stage 3: Topic Expansion (Anthropic)
    _log("Stage 3: expanding pillars and clusters [Anthropic]...")
    pillars = expand_topics(seed, central)
    _log(f"  {len(pillars)} pillars, {sum(len(p.clusters) for p in pillars)} clusters")
    _checkpoint(output_dir, "stage3", {
        "central_entity": central.model_dump(mode="json"),
        "pillars": [p.model_dump(mode="json") for p in pillars],
    })

    # Stage 3.5: SERP Intelligence (Serper.dev)
    serp_data = None
    if not skip_serp:
        _log("Stage 3.5: pulling SERP data [Serper.dev]...")
        serp_data = pull_serp_for_pillars(pillars, geo=serp_geo, lang=serp_lang)
        tracker.log_serper_call("Stage 3.5 — Serper.dev", len(pillars))
        total_paa     = sum(len(s.paa) for s in serp_data.values())
        total_related = sum(len(s.related_searches) for s in serp_data.values())
        _log(f"  PAA questions: {total_paa} | Related searches: {total_related}")
        _checkpoint(output_dir, "stage3_5", {
            pid: {
                "organic": len(s.organic),
                "paa": s.paa,
                "related_searches": s.related_searches,
                "featured_snippet": s.featured_snippet,
            }
            for pid, s in serp_data.items()
        })
    else:
        _log("Stage 3.5: SKIPPED (skip_serp=True)")

    # Stage 4: Validation (data-driven if serp_data, else Gemini Flash)
    if not skip_validation:
        provider_label = "data-driven" if serp_data else "Gemini Flash"
        _log(f"Stage 4: validating topics [{provider_label}]...")
        validations = validate_topics(pillars, serp_data)
        strong = sum(1 for v in validations.values() if v.signal == "strong")
        medium = sum(1 for v in validations.values() if v.signal == "medium")
        weak   = sum(1 for v in validations.values() if v.signal == "weak")
        _log(f"  strong: {strong} | medium: {medium} | weak: {weak}")
        for pillar in pillars:
            if pillar.id in validations:
                v = validations[pillar.id]
                pillar.validation_signal    = v.signal
                pillar.validation_reasoning = v.reasoning
            for cluster in pillar.clusters:
                if cluster.id in validations:
                    v = validations[cluster.id]
                    cluster.validation_signal    = v.signal
                    cluster.validation_reasoning = v.reasoning
    else:
        _log("Stage 4: SKIPPED")

    # Stage 5: Query Generation (Anthropic + Serper PAA)
    _log("Stage 5: generating queries [Anthropic + Serper PAA]...")
    pillars = generate_queries_for_all(pillars, serp_data)
    total_queries = sum(
        len(p.representative_queries) + sum(len(c.represented_queries) for c in p.clusters)
        for p in pillars
    )
    _log(f"  {total_queries} queries total")
    _checkpoint(output_dir, "stage5", {
        "pillars": [p.model_dump(mode="json") for p in pillars],
    })

    # Stage 6: Supplementary Nodes (Gemini Flash + Serper related searches)
    _log("Stage 6: generating supplementary nodes [Gemini Flash + Serper related]...")
    pillars = generate_supplementary_for_all(pillars, serp_data)
    total_supp = sum(
        sum(len(c.supplementary_nodes) for c in p.clusters)
        for p in pillars
    )
    _log(f"  {total_supp} supplementary nodes")
    _checkpoint(output_dir, "stage6", {
        "pillars": [p.model_dump(mode="json") for p in pillars],
    })

    # Geo pages
    _log("Deriving geographic service pages...")
    geo_pages = derive_geo_pages(pillars, seed.intake.geo)
    _log(f"  {len(geo_pages)} geo pages")

    topical_map = TopicalMap(
        central_entity=central,
        pillars=pillars,
        geo_pages=geo_pages,
    )

    # Stage 7: Internal Linking (Anthropic)
    _log("Stage 7: building internal linking plan [Anthropic]...")
    linking_plan = build_linking_plan(pillars)
    _log(f"  {len(linking_plan.links)} links | {len(linking_plan.homepage_links)} homepage links")

    final_output = EngineOutput(
        input=seed,
        topical_map=topical_map,
        linking_plan=linking_plan,
    )

    # Stage 8: Render
    _log("Stage 8: rendering JSON + Markdown report...")
    paths = save_outputs(final_output, output_dir)
    _log(f"  JSON:     {paths['json']}")
    _log(f"  Markdown: {paths['markdown']}")

    _log("Pipeline complete.")
    tracker.print_report()
    tracker.save_report(output_dir / "cost_report.json")

    # Auto-save session
    try:
        from ui.session_manager import save_session, _session_id
        session_id = _session_id(seed.seed_keyword)
        save_session(final_output, session_id)
        _log(f"Session saved: {session_id}")
        final_output._session_id = session_id
    except Exception as e:
        _log(f"Session save skipped: {e}")

    return final_output


def _checkpoint(output_dir: Path, name: str, data: dict):
    path = output_dir / f"_checkpoint_{name}.json"
    path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m pipeline <input.json> <output_dir>")
        sys.exit(1)
    seed = load_intake_from_json(sys.argv[1])
    run_pipeline(seed, sys.argv[2])
