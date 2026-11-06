# AisleScout

Search for a grocery item ("apples", "oat milk") and see the best current deals at nearby stores, ranked by **price per unit**, store rating and distance.

> Status: early development. Two data sources (Kroger family and Walmart) and the price/size parser work, and the CLI ranks results from both by unit price. Matching and the web app are next.

## Why it's harder than it looks
- **Every store describes products differently.** "Honeycrisp Apples 3 lb Bag", "Apple, Honeycrisp, each" and "Fresh Honeycrisp Apples, 2 lb" are the same thing. AisleScout normalizes sizes and prices first, then matches products across stores.
- **Sticker price lies.** "2/$5", "Buy 1 Get 1", "$6.99 lb member price" and "10 to 12-oz. bag" all need to become one comparable number: dollars per lb, per fl oz, or each.
- **Data sources come with rules.** Kroger's official API forbids storing its prices permanently, so those are fetched live and cached only as long as the API allows. See [docs/data-sources.md](docs/data-sources.md).

## Roadmap
- [x] Kroger API client (stores by zip, product search with regular and sale prices)
- [x] Size and price-tag parser with unit-price normalization
- [x] Walmart Affiliate API client (RSA-signed requests, online prices, product ratings)
- [ ] LLM fallback for text the parser can't handle, plus cross-store product matching measured against a hand-labeled test set
- [ ] Ranking (unit price + distance + Google store rating, user-adjustable weights)
- [ ] API + web app

## Running it
```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest
```
### Live data
Copy `backend/.env.example` to `backend/.env`. Each source is optional; the CLI uses whichever ones are configured.

- **Kroger:** register an app at [developer.kroger.com](https://developer.kroger.com) and fill in `KROGER_CLIENT_ID` / `KROGER_CLIENT_SECRET`.
- **Walmart:** run `.venv/Scripts/python -m aislescout walmart-keygen`, upload the printed public key to an app on [walmart.io](https://walmart.io), and fill in `WALMART_CONSUMER_ID`. The private key stays in `backend/keys/`, which is gitignored.

```bash
.venv/Scripts/python -m aislescout stores 90034
.venv/Scripts/python -m aislescout search 90034 "honeycrisp apples" --sale-only
```
Kroger-family stores aren't in the SF Bay Area. Use a Los Angeles zip (Ralphs), Seattle (QFC/Fred Meyer), Denver (King Soopers), etc. Walmart prices are walmart.com online prices, so they're the same for any zip.
