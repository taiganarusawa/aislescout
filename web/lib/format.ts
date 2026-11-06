import type { UnitBasis } from "./types";

export function money(value: number): string {
  return `$${value.toFixed(2)}`;
}

/** "$1.50/lb", "3.0¢/fl oz", "$0.27 each". Tiny unit prices read better in cents. */
export function unitPrice(value: number, basis: UnitBasis): string {
  const amount = value < 0.1 ? `${(value * 100).toFixed(1)}¢` : money(value);
  return basis === "each" ? `${amount} each` : `${amount}/${basis}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-10" -> "Nov 10", without the timezone shift `new Date(str)` would cause. */
export function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split("-").map(Number);
  return month && day ? `${MONTHS[month - 1]} ${day}` : isoDate;
}

export const BASIS_GROUPS: { key: UnitBasis | null; title: string; hint: string }[] = [
  { key: "lb", title: "By weight", hint: "compared by price per pound" },
  { key: "fl oz", title: "Liquids", hint: "compared by price per fluid ounce" },
  { key: "each", title: "By the item", hint: "compared by price per item" },
  { key: null, title: "Size unknown", hint: "couldn't work out a unit price, so sorted by shelf price" },
];

const SOURCE_NAMES: Record<string, string> = { kroger: "Kroger family", walmart: "Walmart", demo: "Sample data" };

export function sourceName(source: string): string {
  return SOURCE_NAMES[source] ?? source;
}
