import type { SearchResult } from "@/lib/types";
import { money, shortDate, unitPrice } from "@/lib/format";

const CHAIN_COLORS: Record<string, string> = {
  WALMART: "bg-sky-100 text-sky-800 ring-sky-200",
  KROGER: "bg-blue-100 text-blue-800 ring-blue-200",
  RALPHS: "bg-blue-100 text-blue-800 ring-blue-200",
};

function chainClasses(chain: string): string {
  return CHAIN_COLORS[chain] ?? "bg-stone-100 text-stone-700 ring-stone-200";
}

function Stars({ rating, count }: { rating: number; count: number | null }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-stone-600" title={`${rating.toFixed(1)} out of 5`}>
      <span aria-hidden className="text-amber-500">★</span>
      {rating.toFixed(1)}
      {count ? <span className="text-stone-400">({count.toLocaleString()})</span> : null}
    </span>
  );
}

export default function ResultCard({ result, best }: { result: SearchResult; best: boolean }) {
  const { deal, store } = result;
  const details = [deal.brand, deal.size_text || (deal.sold_by === "weight" ? "sold by weight" : "")].filter(Boolean);

  return (
    <li
      className={`flex gap-3 rounded-2xl border bg-white p-3 shadow-sm transition hover:shadow-md sm:gap-4 sm:p-4 ${
        best ? "border-emerald-400 ring-1 ring-emerald-300" : "border-stone-200"
      }`}
    >
      <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-stone-50 sm:h-20 sm:w-20">
        {deal.image_url ? (
          // Product images come from many retailer CDNs, so a plain <img> avoids
          // maintaining an allowlist for next/image.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={deal.image_url} alt="" className="h-full w-full object-contain" loading="lazy" />
        ) : (
          <span aria-hidden className="text-3xl">🛒</span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide ring-1 ${chainClasses(store.chain)}`}>
            {store.chain}
          </span>
          {best && (
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] font-semibold text-white">Best value</span>
          )}
          {deal.on_sale && deal.savings_pct ? (
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700">
              Save {Math.round(deal.savings_pct)}%
            </span>
          ) : null}
          {deal.member_only && (
            <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-700">Member price</span>
          )}
          {deal.min_quantity > 1 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
              Buy {deal.min_quantity}+
            </span>
          )}
        </div>

        <h3 className="mt-1.5 line-clamp-2 font-medium leading-snug text-stone-900" title={deal.name}>
          {deal.name}
        </h3>
        <p className="truncate text-sm text-stone-500">{details.join(" · ") || " "}</p>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          {deal.product_rating !== null && <Stars rating={deal.product_rating} count={deal.review_count} />}
          {deal.on_sale && deal.valid_to && <span className="text-xs text-stone-500">Sale ends {shortDate(deal.valid_to)}</span>}
          {deal.product_url && (
            <a
              href={deal.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-emerald-700 hover:underline"
            >
              View at {store.chain === "WALMART" ? "walmart.com" : "store"} ↗
            </a>
          )}
        </div>
      </div>

      <div className="shrink-0 text-right">
        <div className="text-xl font-semibold tabular-nums text-stone-900">
          {money(deal.price)}
          {deal.sold_by === "weight" && <span className="text-sm font-normal text-stone-500">/lb</span>}
        </div>
        {deal.on_sale && deal.regular_price !== null && (
          <div className="text-sm tabular-nums text-stone-400 line-through">{money(deal.regular_price)}</div>
        )}
        {/* Items sold by weight are already priced per lb above, so don't repeat it. */}
        {deal.unit_price !== null && deal.unit_basis && !(deal.sold_by === "weight" && deal.unit_basis === "lb") && (
          <div className={`mt-1 text-sm tabular-nums ${best ? "font-semibold text-emerald-700" : "text-stone-600"}`}>
            {unitPrice(deal.unit_price, deal.unit_basis)}
          </div>
        )}
      </div>
    </li>
  );
}
