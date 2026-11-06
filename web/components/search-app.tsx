"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import ResultCard from "@/components/result-card";
import { BASIS_GROUPS, sourceName } from "@/lib/format";
import type { SearchResponse, SourceStatus } from "@/lib/types";

const ZIP_KEY = "aislescout:zip";
const SUGGESTIONS = ["apples", "whole milk", "eggs", "chicken breast", "bread"];
const ZIP_RE = /^\d{5}$/;

type Outcome = { key: string; data?: SearchResponse; error?: string };

export default function SearchApp() {
  const router = useRouter();
  const params = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const zip = (params.get("zip") ?? "").trim();
  const saleOnly = params.get("sale") === "1";

  const requestKey = q.length >= 3 && ZIP_RE.test(zip) ? `${q}|${zip}|${saleOnly}` : null;
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  useEffect(() => {
    if (!requestKey) return;
    const controller = new AbortController();
    const url = `/api/search?${new URLSearchParams({ q, zip, sale_only: String(saleOnly) })}`;
    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (res.ok) return setOutcome({ key: requestKey, data: (await res.json()) as SearchResponse });
        const message =
          res.status === 422 ? "Check the search term (3+ letters) and the 5-digit zip code." : `The API returned an error (${res.status}).`;
        setOutcome({ key: requestKey, error: message });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // a newer search replaced this one
        console.error(err);
        setOutcome({
          key: requestKey,
          error: "Can't reach the AisleScout API. Is the backend running? (python -m aislescout serve)",
        });
      });
    return () => controller.abort();
  }, [requestKey, q, zip, saleOnly]);

  function runSearch(term: string, zipCode: string, sale: boolean) {
    window.localStorage.setItem(ZIP_KEY, zipCode);
    const next = new URLSearchParams({ q: term, zip: zipCode });
    if (sale) next.set("sale", "1");
    router.replace(`/?${next}`, { scroll: false });
  }

  const loading = requestKey !== null && outcome?.key !== requestKey;
  const current = !loading && outcome?.key === requestKey ? outcome : null;

  return (
    <div className="flex flex-col gap-8">
      {/* Remount the form when the URL changes (e.g. back button) so its fields match the URL. */}
      <SearchForm key={`${q}|${zip}|${saleOnly}`} initialTerm={q} initialZip={zip} initialSale={saleOnly} onSearch={runSearch} />

      {!requestKey && <Intro />}
      {loading && <LoadingList />}
      {current?.error && <ErrorBox message={current.error} />}
      {current?.data && <Results data={current.data} />}
    </div>
  );
}

function SearchForm({
  initialTerm,
  initialZip,
  initialSale,
  onSearch,
}: {
  initialTerm: string;
  initialZip: string;
  initialSale: boolean;
  onSearch: (term: string, zip: string, sale: boolean) => void;
}) {
  const [term, setTerm] = useState(initialTerm);
  // Fall back to the last zip used on this device.
  const [zip, setZip] = useState(() => initialZip || (typeof window !== "undefined" ? window.localStorage.getItem(ZIP_KEY) ?? "" : ""));
  const [sale, setSale] = useState(initialSale);
  const [problem, setProblem] = useState("");

  function submit(event: FormEvent, override?: string) {
    event.preventDefault();
    const t = (override ?? term).trim();
    if (t.length < 3) return setProblem("Type at least 3 letters, like “eggs”.");
    if (!ZIP_RE.test(zip)) return setProblem("Enter a 5-digit zip code.");
    setProblem("");
    if (override) setTerm(override);
    onSearch(t, zip, sale);
  }

  return (
    <form onSubmit={submit} className="rounded-3xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="flex-1">
          <span className="sr-only">What are you shopping for?</span>
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="What are you shopping for? e.g. apples"
            className="w-full rounded-xl border border-stone-300 px-4 py-3 text-base outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            maxLength={80}
            autoFocus
          />
        </label>
        <label className="sm:w-32">
          <span className="sr-only">Zip code</span>
          <input
            value={zip}
            onChange={(e) => setZip(e.target.value.replace(/\D/g, "").slice(0, 5))}
            placeholder="Zip"
            inputMode="numeric"
            autoComplete="postal-code"
            className="w-full rounded-xl border border-stone-300 px-4 py-3 text-base tabular-nums outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          />
        </label>
        <button
          type="submit"
          className="rounded-xl bg-emerald-600 px-6 py-3 font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-300"
        >
          Search
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-stone-600">
          <input type="checkbox" checked={sale} onChange={(e) => setSale(e.target.checked)} className="h-4 w-4 accent-emerald-600" />
          On sale only
        </label>
        <div className="flex flex-wrap items-center gap-2 text-sm text-stone-500">
          Try:
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={(e) => submit(e, s)}
              className="rounded-full border border-stone-200 px-3 py-1 text-stone-600 hover:border-emerald-400 hover:text-emerald-700"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
      {problem && <p className="mt-3 text-sm text-rose-600">{problem}</p>}
    </form>
  );
}

function Results({ data }: { data: SearchResponse }) {
  const groups = BASIS_GROUPS.map((g) => ({ ...g, items: data.results.filter((r) => r.deal.unit_basis === g.key) })).filter(
    (g) => g.items.length > 0,
  );
  const working = data.sources.filter((s) => s.status === "ok");

  return (
    <section className="flex flex-col gap-6">
      {data.demo && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Sample data.</strong> These stores and prices are made up for testing the app. Add API keys in{" "}
          <code className="rounded bg-amber-100 px-1">backend/.env</code> to see real deals.
        </div>
      )}

      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-stone-900">
          {data.results.length} {data.results.length === 1 ? "result" : "results"} for “{data.query}” near {data.zip_code}
          {data.sale_only && <span className="font-normal text-stone-500"> · on sale only</span>}
        </h2>
        <SourceChips sources={data.sources} />
      </div>

      {data.results.length === 0 ? (
        <EmptyState noSources={working.length === 0} />
      ) : (
        groups.map((group) => (
          <div key={group.title}>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
              {group.title} <span className="font-normal normal-case tracking-normal text-stone-400">· {group.hint}</span>
            </h3>
            <ul className="flex flex-col gap-3">
              {group.items.map((r, i) => (
                <ResultCard
                  key={`${r.deal.source}:${r.deal.store_id}:${r.deal.product_id}`}
                  result={r}
                  best={i === 0 && group.key !== null && group.items.length > 1}
                />
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}

function SourceChips({ sources }: { sources: SourceStatus[] }) {
  const styles = {
    ok: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    skipped: "bg-stone-100 text-stone-500 ring-stone-200",
    error: "bg-rose-50 text-rose-700 ring-rose-200",
  } as const;
  return (
    <ul className="flex flex-wrap gap-2 text-xs">
      {sources.map((s) => (
        <li key={s.source} className={`rounded-full px-2.5 py-1 ring-1 ${styles[s.status]}`} title={s.message || undefined}>
          {sourceName(s.source)}:{" "}
          {s.status === "ok" ? `${s.result_count} found` : s.status === "skipped" ? "not set up" : "error"}
          {s.status === "ok" && s.message ? ` (${s.message})` : ""}
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ noSources }: { noSources: boolean }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-10 text-center text-stone-600">
      {noSources ? (
        <>
          <p className="font-medium">No data sources are working yet.</p>
          <p className="mt-1 text-sm">
            Add Kroger or Walmart API keys to <code>backend/.env</code>, or run the backend with <code>--demo</code> for sample data.
          </p>
        </>
      ) : (
        <>
          <p className="font-medium">No matches.</p>
          <p className="mt-1 text-sm">Try a simpler word (“milk” instead of “organic 2% milk”), or turn off “On sale only”.</p>
        </>
      )}
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{message}</div>;
}

function LoadingList() {
  return (
    <ul className="flex flex-col gap-3" aria-busy="true" aria-label="Loading results">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex h-28 animate-pulse gap-4 rounded-2xl border border-stone-200 bg-white p-4">
          <div className="h-20 w-20 rounded-xl bg-stone-100" />
          <div className="flex flex-1 flex-col gap-2">
            <div className="h-3 w-24 rounded bg-stone-100" />
            <div className="h-4 w-2/3 rounded bg-stone-100" />
            <div className="h-3 w-1/3 rounded bg-stone-100" />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Intro() {
  const steps = [
    ["Search once", "Type an item and your zip. AisleScout checks every store it knows about at the same time."],
    ["Compare fairly", "A 3 lb bag and a single apple can't be compared by sticker price, so everything becomes $/lb, $/fl oz or $/item."],
    ["Spot real deals", "Sales, member prices and multi-buy offers are folded into the price you'd actually pay."],
  ];
  return (
    <ol className="grid gap-4 sm:grid-cols-3">
      {steps.map(([title, body], i) => (
        <li key={title} className="rounded-2xl border border-stone-200 bg-white p-5">
          <span className="text-sm font-semibold text-emerald-700">{i + 1}</span>
          <h3 className="mt-1 font-semibold text-stone-900">{title}</h3>
          <p className="mt-1 text-sm text-stone-600">{body}</p>
        </li>
      ))}
    </ol>
  );
}
