# Data sources

Researched 2026-11-05. "Verified" means checked on the official page or the live site.

| Store | Access | Status |
|---|---|---|
| Kroger family (Kroger, Ralphs, Fred Meyer, QFC, King Soopers, ...) | Official API, free | **Implemented** |
| Walmart | Official Affiliate API (walmart.io) | **Implemented** (online prices) |
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

## Walmart (verified on walmart.io docs and terms)
- **Access:** sign in to walmart.io with a walmart.com account, create an application, and upload an RSA public key. That gives you a Consumer ID. An Impact publisher ID is **optional**: it's only for affiliate commission links (`productTrackingUrl` has a `|PUBID|` placeholder).
- **Signing:** every request sends `WM_CONSUMER.ID`, `WM_CONSUMER.INTIMESTAMP` (epoch ms), `WM_SEC.KEY_VERSION` and `WM_SEC.AUTH_SIGNATURE`. The signature is SHA256-with-RSA over those three values in sorted-name order, each followed by `\n`, base64-encoded. It's valid for 180 s.
- Base URL `https://developer.api.walmart.com/api-proxy/service/affil/product/v2`:
  - `GET /search`: `query`, `categoryId`, `numItems` (max 25), `start`, `sort` (relevance, price, title, bestseller, customerRating, new), `order`, `responseGroup`, facets.
  - `GET /stores`: `zip` or `lat`/`lon`. Returns store `no`, `name`, `streetAddress`, `city`, `stateProvCode`, `zip`, `coordinates` [lon, lat].
- Item fields: `itemId`, `name`, `salePrice`, `msrp`, `size`, `brandName`, `upc`, `categoryPath`, images, `customerRating`, `numReviews`, `stock`, `marketplace`.
- **Prices are walmart.com online prices.** There's no zip or store parameter for pricing and no promo field. AisleScout treats `msrp > salePrice` as a sale, and skips marketplace (third-party seller) items by default.
- Category `976759` is assumed to be Food. Confirm it with `/taxonomy` on the first live run.
- **Terms:** 5,000 calls/day. No scraping walmart.com. No redistributing or syndicating the API data to third parties, or to sites that could be seen as Walmart's competitors.

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
- https://walmart.io/docs/affiliates/v1/quickstart
- https://walmart.io/docs/affiliates/v1/additional-headers
- https://walmart.io/docs/affiliates/v1/search
- https://walmart.io/docs/affiliates/v1/stores
- https://walmart.io/termsandcondition
- https://affiliates.walmart.com/faqs
- https://developers.google.com/maps/billing-and-pricing/sku-details/places
- https://providers.apievangelist.com/providers/flipp-wishabi/
- https://scrapfly.io/blog/posts/how-to-scrape-target-com
