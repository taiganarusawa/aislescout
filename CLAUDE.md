# AisleScout

Grocery deal finder: search an item (e.g. "apples") and see current deals across nearby stores, ranked by price per unit, store rating and distance.

## Git rules (set by the repo owner)
- **Never run `git add`, `git commit`, or `git push`** (or anything else that stages, commits, or pushes). The owner does all of that.
- Creating or switching branches is fine when the owner agrees to it.
- At the end of every change, give the owner a **short one-line commit message** to use.

## Data source rules
- Use official APIs, or sources the owner has explicitly approved. Don't pull access tokens out of retailer web pages to call their undocumented APIs.
- **Kroger** (official API): don't store Kroger price data permanently, and don't cache it longer than the response's `Cache-Control` header allows. Fetch live per search.
- **Walmart** (official Affiliate API): 5,000 calls/day, online prices only. Never scrape walmart.com. The private key lives in `backend/keys/` (gitignored); never print, log, or commit it.
- See `docs/data-sources.md` for the research behind each source.

## Layout
- `backend/`: Python 3.13 package `aislescout` (data sources, parsing, CLI), tests in `backend/tests/`.

## Dev commands (run from `backend/`)
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m aislescout --help
```
Secrets go in `backend/.env` (copy `.env.example`). Never commit `.env`.
