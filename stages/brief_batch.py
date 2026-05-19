"""
Batch Brief Generator (Stage 9.2)

Generates content briefs for an entire pillar (pillar page + all cluster pages)
in one batch run. Validates all briefs automatically after generation.

This is the client delivery function — run once per pillar, get a full
brief package ready for the writing team.

Cost estimate per pillar:
  1 pillar brief  × ~$0.12 = $0.12
  N cluster briefs × ~$0.10 = $0.10 × N
  Total for 7 clusters: ~$0.82

Usage:
    from stages.brief_batch import run_batch_for_pillar
    package = run_batch_for_pillar(pillar, topical_map, output_dir)
    package.download_all()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from models import Pillar, TopicalMap
from stages.brief import (
    ContentBrief,
    generate_brief_for_pillar,
    generate_brief_for_cluster,
    save_briefs,
)
from stages.brief_validator import (
    validate_all_briefs,
    print_validation_summary,
    BriefValidationResult,
)


# ── Batch result ──────────────────────────────────────────────────────────────

@dataclass
class BatchPackage:
    """
    Complete brief package for one pillar.
    Contains original briefs, validation results, and corrected briefs.
    """
    pillar_id: str
    pillar_title: str
    briefs: dict[str, ContentBrief] = field(default_factory=dict)
    validation: dict[str, BriefValidationResult] = field(default_factory=dict)
    saved_paths: list[Path] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def total_generated(self) -> int:
        return len(self.briefs)

    @property
    def total_valid(self) -> int:
        return sum(1 for r in self.validation.values() if r.is_valid)

    @property
    def total_corrected(self) -> int:
        return sum(1 for r in self.validation.values() if r.corrected_brief is not None)

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"  BATCH PACKAGE: {self.pillar_title}",
            f"{'='*60}",
            f"  Briefs generated: {self.total_generated}",
            f"  Errors:           {len(self.errors)}",
            f"  Valid IDs:        {self.total_valid}",
            f"  Auto-corrected:   {self.total_corrected}",
            f"  Files saved:      {len(self.saved_paths)}",
            f"{'='*60}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for page_id, err in self.errors.items():
                lines.append(f"  {page_id}: {err[:100]}")
        return "\n".join(lines)

    def get_markdown_paths(self) -> list[Path]:
        return [p for p in self.saved_paths if p.suffix == '.md']


# ── Main batch runner ─────────────────────────────────────────────────────────

def run_batch_for_pillar(
    pillar: Pillar,
    topical_map: TopicalMap,
    output_dir: str | Path,
    include_clusters: bool = True,
    max_clusters: int | None = None,
    delay_between_calls: float = 1.0,
    auto_correct_ids: bool = True,
) -> BatchPackage:
    """
    Generate and validate briefs for an entire pillar.

    pillar:             the pillar to generate for
    topical_map:        full topical map (needed for semantic bridges)
    output_dir:         where to save the files
    include_clusters:   whether to generate cluster briefs
    max_clusters:       limit cluster count (None = all clusters)
    delay_between_calls: seconds between API calls (avoid rate limits)
    auto_correct_ids:   automatically fix hallucinated page IDs

    Returns a BatchPackage with all briefs, validation results, and file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    package = BatchPackage(
        pillar_id=pillar.id,
        pillar_title=pillar.title,
    )

    # ── Generate pillar brief ──────────────────────────────────────────────────
    print(f"\n[1/{_total_count(pillar, include_clusters, max_clusters)}] "
          f"Pillar: {pillar.title}")

    try:
        brief = generate_brief_for_pillar(pillar, topical_map)
        package.briefs[pillar.id] = brief
        print(f"  ✓ Done — {brief.content_specs.recommended_word_count:,} words, "
              f"{len(brief.headings)} headings, "
              f"{len(brief.semantic_bridges)} bridges")
        time.sleep(delay_between_calls)
    except Exception as e:
        package.errors[pillar.id] = str(e)
        print(f"  ✗ Failed: {str(e)[:80]}")

    # ── Generate cluster briefs ────────────────────────────────────────────────
    if include_clusters:
        clusters = pillar.clusters
        if max_clusters is not None:
            # Prioritize BOFU clusters first
            bofu = [c for c in clusters if c.funnel_stage.value == "BOFU"]
            others = [c for c in clusters if c.funnel_stage.value != "BOFU"]
            clusters = (bofu + others)[:max_clusters]

        for i, cluster in enumerate(clusters):
            step = i + 2  # pillar was step 1
            print(f"\n[{step}/{_total_count(pillar, include_clusters, max_clusters)}] "
                  f"Cluster: {cluster.title[:55]}")

            try:
                brief = generate_brief_for_cluster(cluster, pillar, topical_map)
                package.briefs[cluster.id] = brief
                print(f"  ✓ Done — {brief.content_specs.recommended_word_count:,} words, "
                      f"{len(brief.headings)} headings, "
                      f"{len(brief.semantic_bridges)} bridges")
                if i < len(clusters) - 1:
                    time.sleep(delay_between_calls)
            except Exception as e:
                package.errors[cluster.id] = str(e)
                print(f"  ✗ Failed: {str(e)[:80]}")

    # ── Validate all briefs ────────────────────────────────────────────────────
    if package.briefs:
        print(f"\n{'─'*55}")
        print(f"Validating {len(package.briefs)} briefs...")
        package.validation = validate_all_briefs(
            package.briefs, topical_map, auto_correct=auto_correct_ids
        )
        print_validation_summary(package.validation)

        # Use corrected briefs where available
        final_briefs: dict[str, ContentBrief] = {}
        for page_id, brief in package.briefs.items():
            result = package.validation.get(page_id)
            if result and result.corrected_brief:
                final_briefs[page_id] = result.corrected_brief
                print(f"  Auto-corrected: {page_id}")
            else:
                final_briefs[page_id] = brief

        # ── Save all briefs ────────────────────────────────────────────────────
        print(f"\nSaving briefs to: {output_dir}")
        package.saved_paths = save_briefs(final_briefs, output_dir)

        # Also save validation report
        report_path = output_dir / "_validation_report.txt"
        report_lines = []
        for result in package.validation.values():
            report_lines.append(result.report())
        report_path.write_text("\n\n".join(report_lines))
        package.saved_paths.append(report_path)
        print(f"  Validation report: {report_path.name}")

    print(f"\n{package.summary()}")
    return package


# ── Helper ────────────────────────────────────────────────────────────────────

def _total_count(
    pillar: Pillar,
    include_clusters: bool,
    max_clusters: int | None,
) -> int:
    if not include_clusters:
        return 1
    n_clusters = len(pillar.clusters) if max_clusters is None else min(max_clusters, len(pillar.clusters))
    return 1 + n_clusters
