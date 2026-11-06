# AisleScout

Search for a grocery item ("apples", "oat milk") and see the best current deals at nearby stores, ranked by **price per unit**, store rating and distance.

> Status: early development. Two data sources (Kroger family and Walmart), the price/size parser, a FastAPI backend and a Next.js web app work end to end. Cross-store product matching is next.

## Why it's harder than it looks
- **Every store describes products differently.** "Honeycrisp Apples 3 lb Bag", "Apple, Honeycrisp, each" and "Fresh Honeycrisp Apples, 2 lb" are the same thing. AisleScout normalizes sizes and prices first, then matches products across stores.
- **Sticker price lies.** "2/$5", "Buy 1 Get 1", "$6.99 lb member price" and "10 to 12-oz. bag" all need to become one comparable number: dollars per lb, per fl oz, or each.
- **Data sources come with rules.** Kroger's official API forbids storing its prices permanently, so those are fetched live and cached only as long as the API allows. See [docs/data-sources.md](docs/data-sources.md).

## Architecture
```
web/ (Next.js 16, React 19, Tailwind)  --/api/* proxy-->  backend/ (FastAPI)
                                                             │  SearchService: queries every source in parallel,
                                                             │  isolates failures, ranks by unit price
                                                             ├── Kroger API   (OAuth2, live store prices)
                                                             ├── Walmart API  (RSA-signed requests)
                                                             └── demo source  (labeled sample data, no keys needed)
```

## Roadmap
- [x] Kroger API client (stores by zip, product search with regular and sale prices)
- [x] Size and price-tag parser with unit-price normalization
- [x] Walmart Affiliate API client (RSA-signed requests, online prices, product ratings)
- [x] API + web app (parallel multi-source search, results grouped by $/lb, $/fl oz, $/item)
- [ ] LLM fallback for text the parser can't handle, plus cross-store product matching measured against a hand-labeled test set
- [ ] Ranking (unit price + distance + Google store rating, user-adjustable weights)
- [ ] Deploy

## Running it

### Backend
```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/python -m aislescout serve --demo   # API on http://127.0.0.1:8000 (docs at /docs)
```
`--demo` serves clearly labeled, made-up sample data, so the app works without any API keys. Drop it to use the real sources.

### Web app
In a second terminal:
```bash
cd web
npm install
npm run dev   # http://localhost:3000
```
The web app proxies `/api/*` to the backend. Set `AISLESCOUT_API_URL` if the backend isn't on `http://127.0.0.1:8000`.

### Live data
Copy `backend/.env.example` to `backend/.env`. Each source is optional; the app uses whichever ones are configured and shows the rest as "not set up".

- **Kroger:** register an app at [developer.kroger.com](https://developer.kroger.com) and fill in `KROGER_CLIENT_ID` / `KROGER_CLIENT_SECRET`.
- **Walmart:** run `.venv/Scripts/python -m aislescout walmart-keygen`, paste the printed public key into an app on [walmart.io](https://walmart.io) (environment: PRODUCTION), and fill in `WALMART_CONSUMER_ID`. The private key stays in `backend/keys/`, which is gitignored.

```bash
.venv/Scripts/python -m aislescout stores 90034
.venv/Scripts/python -m aislescout search 90034 "honeycrisp apples" --sale-only
```
Kroger-family stores aren't in the SF Bay Area. Use a Los Angeles zip (Ralphs), Seattle (QFC/Fred Meyer), Denver (King Soopers), etc. Walmart prices are walmart.com online prices, so they're the same for any zip.
