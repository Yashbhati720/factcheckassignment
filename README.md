# Truth Layer — PDF Fact Checker

A small **Streamlit** web app that treats marketing or technical PDFs as input, pulls out **checkable claims** (numbers, dates, money, percentages, specs), runs **live web search** (DuckDuckGo via [`ddgs`](https://pypi.org/project/ddgs/)), and labels each claim:

| Status | Meaning |
|--------|---------|
| **Verified** | Evidence in search snippets aligns with the claim (LLM judgment if OpenAI is configured; otherwise a numeric/snippet heuristic). |
| **Inaccurate** | Results exist but do not clearly support the stated figures or suggest mismatch/outdated material. |
| **False** | No usable support, or search failed. |

Use this as an **assistive** layer, not a legal or journalistic sign-off. Models and search snippets can be wrong or incomplete.

## Requirements

- Python **3.11+** (3.13 works with the pinned stack used in development)
- Network access for web search

## Quick start

```bash
cd factcheckassignment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Usage

1. **Upload** a text-based PDF (scanned/image-only PDFs need OCR first).
2. Review the **text preview** and **candidate claims** in the expander.
3. Click **Run web verification** to search the web once per claim (avoids re-querying on every sidebar change).
4. **Download** full JSON (includes evidence snippets) or a compact summary.

## Configuration

### Local `.env` (optional)

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

- **`OPENAI_API_KEY`**: If set, the app can (1) extract claims via the API when you enable that toggle, and (2) classify **Verified / Inaccurate / False** using model reasoning over search snippets.
- **`OPENAI_MODEL`**: Optional; defaults to `gpt-4o-mini`.

`python-dotenv` loads `.env` on startup.

### Streamlit Community Cloud

1. Connect this repo and set the **main file** to `app.py`.
2. Under **Secrets**, add at least:

   ```toml
   OPENAI_API_KEY = "sk-..."
   ```

   Optionally:

   ```toml
   OPENAI_MODEL = "gpt-4o-mini"
   ```

Secrets are copied into the process environment so the OpenAI client and sidebar defaults behave the same as locally.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI, session cache, exports |
| `pdf_utils.py` | PDF → plain text (`pypdf`) |
| `claim_extractor.py` | Regex heuristics and optional OpenAI claim extraction |
| `verifier.py` | DuckDuckGo search + heuristic or LLM verdict |
| `requirements.txt` | Dependencies |

## Limitations

- **Search**: Depends on DuckDuckGo and `ddgs`; rate limits or empty results can occur.
- **No key**: Without OpenAI, extraction is **regex-only** and verdicts are **heuristic** (e.g. number overlap in snippets)—good for demos, not for high-stakes decisions.
- **PDF quality**: Garbage in (bad OCR, layout) means weak claims and weak checks.

## License

No license is set by default; add one if you open-source the repo.
