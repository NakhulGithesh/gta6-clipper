"""Finding today's streams worth clipping."""
from __future__ import annotations

DEFAULT_QUERIES = (
    "GTA 6 reaction",
    "GTA 6 gameplay reaction",
    "GTA 6 trailer reaction",
    "GTA 6 first look",
)

GAME = "GTA6"


def rank_streams(streams: list[dict], limit: int = 10, live_only: bool = True) -> list[dict]:
    """Biggest live streams first."""
    candidates = []
    for stream in streams:
        if live_only and not stream.get("is_live"):
            continue
        candidates.append(stream)
    candidates.sort(key=lambda s: int(s.get("view_count") or 0), reverse=True)
    return candidates[:limit]


def collect_streams(
    queries: tuple[str, ...] = DEFAULT_QUERIES, limit: int = 20, cookies: str | None = None
) -> list[dict]:
    """Search every query, drop duplicates, keep the live ones."""
    from . import fetch

    seen: dict[str, dict] = {}
    for query in queries:
        try:
            results = fetch.search_live(query, limit=limit, cookies=cookies)
        except Exception:
            continue
        for stream in results:
            key = stream.get("id") or stream.get("url")
            if key and key not in seen:
                seen[key] = stream
    return list(seen.values())


def top_streams(count: int = 7, cookies: str | None = None, queries: tuple[str, ...] = DEFAULT_QUERIES) -> list[dict]:
    streams = collect_streams(queries=queries, cookies=cookies)
    return rank_streams(streams, limit=count, live_only=True)
