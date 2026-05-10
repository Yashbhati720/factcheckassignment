"""Web search + verdict: Verified | Inaccurate | False."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from ddgs import DDGS


@dataclass
class EvidenceHit:
    title: str
    url: str
    snippet: str


@dataclass
class VerdictResult:
    status: str  # Verified | Inaccurate | False
    summary: str
    evidence: list[EvidenceHit]


def _search_snippets(query: str, max_results: int = 6) -> list[EvidenceHit]:
    hits: list[EvidenceHit] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                hits.append(
                    EvidenceHit(
                        title=str(r.get("title") or "")[:200],
                        url=str(r.get("href") or r.get("url") or "")[:500],
                        snippet=str(r.get("body") or "")[:600],
                    )
                )
    except Exception as e:  # noqa: BLE001 — network / rate limits
        hits.append(
            EvidenceHit(
                title="Search error",
                url="",
                snippet=str(e)[:400],
            )
        )
    return hits


def _numbers_in(text: str) -> set[str]:
    # Normalize numeric tokens for loose matching
    found = set()
    for m in re.finditer(
        r"(?:[$€£¥]\s*)?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:%|percent|billion|million|thousand)?",
        text,
        re.I,
    ):
        t = m.group(0).replace(",", "").lower()
        if len(t) >= 1:
            found.add(t)
    return found


def _heuristic_verdict(claim: str, evidence: list[EvidenceHit]) -> VerdictResult:
    claim_nums = _numbers_in(claim)
    blob = " \n ".join(f"{e.title} {e.snippet}" for e in evidence).lower()

    if not evidence or (len(evidence) == 1 and "error" in evidence[0].title.lower()):
        return VerdictResult(
            status="False",
            summary="No usable web results (or search failed). Treat as unverified.",
            evidence=evidence,
        )

    matched = sum(1 for n in claim_nums if n and n in blob)
    # Weak support: any substantive overlap of a long numeric token
    if matched >= 1 and len(blob) > 80:
        # Check for obvious contradiction: same context word with different % or large number
        return VerdictResult(
            status="Verified",
            summary=(
                f"Heuristic: {matched} numeric/currency token(s) from the claim appear in search snippets. "
                "Manual review recommended."
            ),
            evidence=evidence,
        )

    # Snippets exist but no number alignment
    if len(blob) > 120:
        return VerdictResult(
            status="Inaccurate",
            summary=(
                "Search returned text, but snippets did not clearly corroborate the specific figures in the claim. "
                "The claim may be outdated, imprecise, or not reflected in top results."
            ),
            evidence=evidence,
        )

    return VerdictResult(
        status="False",
        summary="Insufficient evidence in search snippets to support the claim.",
        evidence=evidence,
    )


def _llm_verdict(claim: str, evidence: list[EvidenceHit]) -> VerdictResult | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None

    from openai import OpenAI

    client = OpenAI(api_key=key)
    pack = [
        {"title": e.title, "url": e.url, "snippet": e.snippet}
        for e in evidence[:8]
    ]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful fact-checking assistant. Given ONE claim and web search snippets, "
                    "choose exactly one label: Verified, Inaccurate, or False.\n"
                    "- Verified: reputable or consistent sources in snippets support the claim as stated.\n"
                    "- Inaccurate: snippets show conflicting numbers/dates/facts vs the claim.\n"
                    "- False: no adequate support, or snippets contradict the claim outright.\n"
                    "Respond as JSON: {\"status\":\"Verified|Inaccurate|False\",\"summary\":\"one short paragraph\"}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"claim": claim, "search_results": pack}, ensure_ascii=False),
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return None
    status = str(data.get("status", "")).strip()
    if status not in ("Verified", "Inaccurate", "False"):
        return None
    summary = str(data.get("summary", "")).strip() or "No summary."
    return VerdictResult(status=status, summary=summary, evidence=evidence)


def verify_claim(claim: str) -> VerdictResult:
    """Run a focused web search and produce a verdict."""
    q = claim[:240].strip()
    evidence = _search_snippets(q)
    llm = _llm_verdict(claim, evidence)
    if llm is not None:
        return llm
    return _heuristic_verdict(claim, evidence)
