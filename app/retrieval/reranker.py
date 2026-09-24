from collections import Counter
from typing import Any


def spread_across_sources(
    chunks: list[dict[str, Any]], limit: int, per_source: int
) -> list[dict[str, Any]]:
    """Keep the nearest chunks, at most `per_source` from any one source."""
    kept: list[dict[str, Any]] = []
    counts: Counter[Any] = Counter()
    for chunk in chunks:
        if counts[chunk["source_id"]] >= per_source:
            continue
        kept.append(chunk)
        counts[chunk["source_id"]] += 1
        if len(kept) == limit:
            break
    return kept
