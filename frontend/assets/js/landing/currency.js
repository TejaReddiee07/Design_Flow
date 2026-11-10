/* Shared display currency for the marketing pages (price table, storefront sections). */
import { isLoggedIn, cachedUser } from "../core/auth.js";

export const SYMBOL = { USD: "$", GBP: "£", INR: "₹" };
const CUR_KEY = "df-currency";

let currency = "USD";
try {
  currency = localStorage.getItem(CUR_KEY) || "USD";
} catch {}
const user = isLoggedIn() ? cachedUser() : null;
if (user && user.client && user.client.currency) currency = user.client.currency;
if (!SYMBOL[currency]) currency = "USD";

export function getCurrency() {
  return currency;
}

export function setCurrency(next) {
  if (!SYMBOL[next] || next === currency) return;
  currency = next;
  try {
    localStorage.setItem(CUR_KEY, currency);
  } catch {}
  document.dispatchEvent(new CustomEvent("df:currency", { detail: { currency } }));
}

export function onCurrency(fn) {
  document.addEventListener("df:currency", (e) => fn(e.detail.currency));
}

export function money(prices) {
  const v = prices ? prices[currency] : null;
  if (v === undefined || v === null) return "";
  return `${SYMBOL[currency]}${new Intl.NumberFormat().format(v)}`;
}
