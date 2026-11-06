# Data sources

Researched 2026-11-05. "Verified" means checked on the official page or the live site.

| Store | Access | Status |
|---|---|---|
| Kroger family (Kroger, Ralphs, Fred Meyer, QFC, King Soopers, ...) | Official API, free | **Implemented** |
| Walmart | Official Affiliate API (approval through Impact) | Planned once approved |
| Safeway / Albertsons | No public API. Weekly ad is served by Flipp. | On hold (see below) |
| Target | No public API; internal APIs behind PerimeterX bot protection | Not planned |
| Store ratings | Google Places API (New) | Planned |

## Kroger (verified on developer.kroger.com)
- OAuth2 client credentials: `POST https://api.kroger.com/v1/connect/oauth2/token`, scope `product.compact`, token lasts 1800 s.
- `GET /v1/locations`: `filter.zipCode.near`, `filter.radiusInMiles`, `filter.chain`, `filter.limit` (max 200).
- `GET /v1/products`: `filter.term` (min 3 chars), `filter.locationId` (**required for prices**), `filter.limit` (max 50), `filter.start`.
- Item price fields: `price.regular`, `price.promo` (sale price, 0 when none), `regularPerUnitEstimate`, `promoPerUnitEstimate`, `effectiveDate`, `expirationDate`. Also `size`, `soldBy` (`unit` / `weight`), fulfillment flags, aisle locations.
- Limit: **10,000 calls/day** across all /products operations.
- **Terms:** no databases or permanent copies of API content, and no caching beyond the response's cache headers. So AisleScout fetches Kroger prices live and caches only for `Cache-Control: max-age`.
- No Kroger-family stores in the SF Bay Area.

## Walmart
- Official Affiliates API on walmart.io (verified): Search, Product Lookup, Stores, Taxonomy, Trending, Reviews.
- Access (third-party sources): join the Walmart affiliate program through Impact, then create a walmart.io app with an RSA key to get a Consumer ID.
- Walmart's Terms of Use prohibit scraping.

## Safeway / Albertsons (on hold)
- The weekly ad on safeway.com is rendered by Flipp, which loads structured deal JSON in the browser (names, `price_text`, `post_price_text` like "lb member price", validity dates).
- Flipp has no public developer API, and calling that endpoint means reusing an access token embedded in the retailer's page. **Not used until there's an approved way** (e.g. a Flipp or Albertsons partnership).
- The deal text is useful as **parser test data**: real examples are in `backend/tests/`.

## Store ratings: Google Places API (New)
- `rating` / `userRatingCount` fields are in a higher-priced tier. Check the official SKU page for current prices and free monthly caps.
- Look up each store once and keep its `place_id`. Refresh ratings rarely.

## Sources
- https://developer.kroger.com/api-products/api/product-api-public
- https://developer.kroger.com/terms
- https://walmart.io/docs/affiliates/v1/introduction
- https://affiliates.walmart.com/faqs
- https://developers.google.com/maps/billing-and-pricing/sku-details/places
- https://providers.apievangelist.com/providers/flipp-wishabi/
- https://scrapfly.io/blog/posts/how-to-scrape-target-com
