"""
Fact-Checking Web App — upload a PDF, extract claims, verify against the web.
Deploy: [Streamlit Community Cloud](https://streamlit.io/cloud) — set main file to `app.py`,
add optional secret `OPENAI_API_KEY` and optional `OPENAI_MODEL` (default `gpt-4o-mini`).
"""

from __future__ import annotations

import hashlib
import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from claim_extractor import extract_claims
from pdf_utils import pdf_bytes_to_text
from verifier import verify_claim

st.set_page_config(page_title="Truth Layer — PDF Fact Check", layout="wide")

try:
    for _k in ("OPENAI_API_KEY", "OPENAI_MODEL"):
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except (AttributeError, FileNotFoundError, KeyError, RuntimeError):
    pass

if "pdf_hash" not in st.session_state:
    st.session_state.pdf_hash = None
if "verify_cache" not in st.session_state:
    st.session_state.verify_cache = None  # list[dict] | None

st.title("Truth Layer")
st.caption("Upload a PDF. We extract quantifiable claims and cross-check them against live web results.")

with st.sidebar:
    st.header("Options")
    use_llm_extract = st.toggle(
        "Use OpenAI for claim extraction",
        value=bool(os.environ.get("OPENAI_API_KEY")),
        help="Requires OPENAI_API_KEY. More precise claims; falls back to heuristics if unavailable.",
    )
    st.info(
        "When **OPENAI_API_KEY** is set, verification also uses the model over search snippets "
        "for Verified / Inaccurate / False. Without it, verdicts use search heuristics only."
    )
    max_claims = st.slider("Max claims to verify", 3, 30, 12)
    st.divider()
    st.markdown(
        "**Statuses:** **Verified** — snippets support the claim; **Inaccurate** — conflicting or weak match; "
        "**False** — no support or search failure."
    )

uploaded = st.file_uploader("PDF document", type=["pdf"])

if uploaded is None:
    st.info("Upload a PDF above. The project folder did not include an attachment; use any text-based PDF to try the pipeline.")
    st.stop()

data = uploaded.getvalue()
file_hash = hashlib.sha256(data).hexdigest()[:16]
opts_key = (file_hash, use_llm_extract, max_claims)

if st.session_state.pdf_hash != opts_key:
    st.session_state.pdf_hash = opts_key
    st.session_state.verify_cache = None

with st.spinner("Extracting text from PDF…"):
    text = pdf_bytes_to_text(data)

if not text.strip():
    st.error("Could not extract text from this PDF (may be image-only). Try a text-based PDF or OCR first.")
    st.stop()

st.subheader("Extracted preview")
st.text_area("First ~4000 characters", text[:4000], height=220, label_visibility="collapsed")

claims = extract_claims(text, use_llm=use_llm_extract)[:max_claims]
if not claims:
    st.error("No candidate claims found. Try enabling OpenAI extraction or a denser numeric PDF.")
    st.stop()

with st.expander("Candidate claims (before web check)", expanded=False):
    for i, c in enumerate(claims, 1):
        st.markdown(f"{i}. {c.text}")

run = st.button("Run web verification", type="primary")

if run:
    rows: list[dict] = []
    progress = st.progress(0, text="Verifying…")
    for i, c in enumerate(claims):
        progress.progress((i) / max(len(claims), 1), text=f"Claim {i + 1} / {len(claims)}")
        vr = verify_claim(c.text)
        rows.append(
            {
                "Claim": c.text[:2000] + ("…" if len(c.text) > 2000 else ""),
                "Status": vr.status,
                "Summary": vr.summary,
                "Evidence": [
                    {"title": e.title, "url": e.url, "snippet": e.snippet}
                    for e in vr.evidence[:6]
                ],
            }
        )
    progress.progress(1.0, text="Done")
    st.session_state.verify_cache = rows

rows_out = st.session_state.verify_cache

if not rows_out:
    st.warning('Click **Run web verification** to query the web and label each claim.')
    st.stop()

st.subheader(f"Results ({len(rows_out)} claims)")

for r in rows_out:
    badge = r["Status"]
    color = {"Verified": "green", "Inaccurate": "orange", "False": "red"}.get(badge, "gray")
    st.markdown(f"### :{color}[{badge}]")
    st.markdown(f"**Claim:** {r['Claim']}")
    st.markdown(f"**Assessment:** {r['Summary']}")
    ev = r.get("Evidence") or []
    if ev and ev[0].get("url"):
        st.markdown(f"**Top source:** [{ev[0]['url']}]({ev[0]['url']})")
    st.divider()

compact = [{"Claim": x["Claim"], "Status": x["Status"], "Summary": x["Summary"]} for x in rows_out]
st.download_button(
    "Download report (JSON)",
    data=json.dumps(rows_out, indent=2, ensure_ascii=False),
    file_name="factcheck_report.json",
    mime="application/json",
    key="dl_full",
)
st.download_button(
    "Download summary (JSON)",
    data=json.dumps(compact, indent=2, ensure_ascii=False),
    file_name="factcheck_summary.json",
    mime="application/json",
    key="dl_sum",
)
