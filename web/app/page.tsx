import { Suspense } from "react";

import SearchApp from "@/components/search-app";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-10 sm:py-14">
      <header>
        <p className="flex items-center gap-2 text-lg font-bold tracking-tight text-emerald-700">
          <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-base text-white">
            A
          </span>
          AisleScout
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-stone-900 sm:text-4xl">
          Find the cheapest groceries near you.
        </h1>
        <p className="mt-2 text-stone-600">Deals from nearby stores, compared by what you actually pay per pound, ounce or item.</p>
      </header>

      {/* useSearchParams needs a Suspense boundary so the static shell above can be prerendered. */}
      <Suspense fallback={<div className="h-40 rounded-3xl border border-stone-200 bg-white" />}>
        <SearchApp />
      </Suspense>

      <footer className="mt-auto pt-8 text-xs text-stone-400">
        Prices come from each store&apos;s official API and can change at any time. Always check at the store.
      </footer>
    </main>
  );
}
