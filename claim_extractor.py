"""Extract verifiable claims (stats, dates, figures) from raw PDF text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Claim:
    text: str
    source_span: str | None = None


# Sentence split (rough): period followed by space or newline, or standalone newlines
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Heuristic: line/sentence likely contains a verifiable fact
_HAS_NUMBER = re.compile(
    r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|percent|billion|million|thousand|k\b|m\b|bn\b|tn\b)?",
    re.I,
)
_HAS_CURRENCY = re.compile(r"[$€£¥]\s*\d|\d+\s*(?:USD|EUR|GBP|dollars?|euros?)", re.I)
_HAS_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_HAS_DATE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
    re.I,
)


def _is_candidate(s: str) -> bool:
    s = s.strip()
    if len(s) < 20 or len(s) > 800:
        return False
    return bool(
        _HAS_NUMBER.search(s)
        or _HAS_CURRENCY.search(s)
        or _HAS_YEAR.search(s)
        or _HAS_DATE.search(s)
    )


def extract_claims_regex(text: str, max_claims: int = 40) -> list[Claim]:
    """Pull candidate claims using lightweight heuristics (no API)."""
    if not text or not text.strip():
        return []
    chunks = _SENTENCE_SPLIT.split(text)
    seen: set[str] = set()
    out: list[Claim] = []
    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if not chunk or chunk in seen:
            continue
        if _is_candidate(chunk):
            seen.add(chunk)
            out.append(Claim(text=chunk))
        if len(out) >= max_claims:
            break
    return out


def extract_claims_openai(text: str, max_claims: int = 25) -> list[Claim]:
    """Use OpenAI to list discrete, searchable claims. Requires OPENAI_API_KEY."""
    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return extract_claims_regex(text, max_claims=max_claims)

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    truncated = text[:120_000]
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract ONLY concrete, checkable claims from document text: "
                    "statistics, dates, financial amounts, technical specifications, market shares, "
                    "growth rates, rankings, and named quantitative assertions. "
                    "Output a JSON object with key 'claims' whose value is an array of strings. "
                    "Each string is ONE standalone claim a fact-checker could web-search. "
                    "Skip vague marketing with no numbers or dates. Max 25 claims."
                ),
            },
            {
                "role": "user",
                "content": f"Document text:\n\n{truncated}",
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    import json

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return extract_claims_regex(text, max_claims=max_claims)
    items = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return extract_claims_regex(text, max_claims=max_claims)
    claims: list[Claim] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            claims.append(Claim(text=item.strip()[:800]))
        if len(claims) >= max_claims:
            break
    return claims if claims else extract_claims_regex(text, max_claims=max_claims)


def extract_claims(text: str, use_llm: bool) -> list[Claim]:
    if use_llm:
        return extract_claims_openai(text)
    return extract_claims_regex(text)
