/* Landing + marketing pages */
import { SERVICES, CATEGORIES } from "./services-data.js";
import { initTheme, revealOnScroll, qs, qsa, esc, icon, toast, setLoading } from "../core/ui.js";
import { api, errorMessage } from "../core/api.js";
import { isLoggedIn, cachedUser, homeFor } from "../core/auth.js";
import { getCurrency, setCurrency, onCurrency, money } from "./currency.js";
import { initChrome } from "./chrome.js";

initTheme();

const user = isLoggedIn() ? cachedUser() : null;

/* Nav */
const nav = qs("#nav");
const onScroll = () => nav && nav.classList.toggle("scrolled", window.scrollY > 10);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

const burger = qs("[data-burger]");
const mobile = qs("#mobile-menu");
if (burger && mobile) {
  burger.addEventListener("click", () => {
    const open = mobile.classList.toggle("open");
    burger.innerHTML = icon(open ? "x" : "menu");
    document.body.style.overflow = open ? "hidden" : "";
  });
  qsa("a", mobile).forEach((a) => a.addEventListener("click", () => {
    mobile.classList.remove("open");
    burger.innerHTML = icon("menu");
    document.body.style.overflow = "";
  }));
}

/* Logged-in state */
if (user) {
  const home = homeFor(user);
  qsa("[data-auth-link]").forEach((a) => {
    a.textContent = "Dashboard";
    a.href = home;
  });
  qsa("[data-cta]").forEach((a) => {
    if (user.role === "client") {
      const svc = a.dataset.service;
      a.href = svc ? `/portal#/new?service=${svc}` : "/portal#/new";
      if (!a.dataset.keepLabel) a.innerHTML = `Order a design ${icon("arrow-right")}`;
    } else a.href = home;
  });
}

/* Year */
const year = qs("#year");
if (year) year.textContent = new Date().getFullYear();

/* Services grid */
const grid = qs("#services-grid");
const filters = qs("#cat-filters");

function serviceCard(s) {
  return `<a class="service-card reveal in" href="/services/${esc(s.slug)}" data-cat="${esc(s.category)}">
    <span class="service-icon">${icon("svc-" + esc(s.icon))}</span>
    <h3>${esc(s.name)}</h3>
    <p>${esc(s.tagline)}</p>
    <div class="meta"><span class="price font-semibold text-2">${money(s.prices)}</span><span>${s.turnaround_days}-day delivery</span></div>
  </a>`;
}

function renderServices(cat = "All") {
  if (!grid) return;
  const list = cat === "All" ? SERVICES : SERVICES.filter((s) => s.category === cat);
  grid.innerHTML = list.map(serviceCard).join("");
}

if (grid) {
  if (grid.children.length === 0) renderServices();
  else qsa(".price[data-usd]", grid).forEach((el) => {
    el.textContent = money({ USD: +el.dataset.usd, GBP: +el.dataset.gbp, INR: +el.dataset.inr });
  });
  if (filters && !filters.children.length) {
    filters.innerHTML = ["All", ...CATEGORIES].map((c, i) => `<button class="pill ${i === 0 ? "active" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`).join("");
    filters.addEventListener("click", (e) => {
      const b = e.target.closest("[data-cat]");
      if (!b) return;
      qsa(".pill", filters).forEach((p) => p.classList.toggle("active", p === b));
      const cat = b.dataset.cat;
      if (grid.dataset.static !== undefined || qsa(".service-card[data-cat]", grid).length === SERVICES.length && !grid.dataset.rendered) {
        qsa(".service-card", grid).forEach((c) => (c.style.display = cat === "All" || c.dataset.cat === cat ? "" : "none"));
      } else renderServices(cat);
    });
  }
}

/* Price table + currency switch */
const priceTable = qs("#price-table tbody");
function renderPrices() {
  if (!priceTable) return;
  priceTable.innerHTML = SERVICES.map((s) => `<tr>
    <td><a href="/services/${esc(s.slug)}" class="font-semibold">${esc(s.name)}</a><div class="text-xs text-3">${esc(s.price_unit || "per request")}</div></td>
    <td class="text-3">${esc(s.category)}</td>
    <td class="font-semibold">${money(s.prices)}</td>
    <td>${s.turnaround_days} day${s.turnaround_days === 1 ? "" : "s"}</td>
    <td class="text-right"><a class="btn btn-sm btn-secondary" href="/register?service=${esc(s.slug)}" data-cta data-service="${esc(s.slug)}" data-keep-label="1">Order</a></td>
  </tr>`).join("");
  if (user && user.role === "client") qsa("[data-cta][data-service]", priceTable).forEach((a) => (a.href = `/portal#/new?service=${a.dataset.service}`));
}
renderPrices();
const sw = qs("#currency-switch");
function syncSwitch() {
  if (!sw) return;
  qsa("button", sw).forEach((b) => {
    const on = b.dataset.cur === getCurrency();
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
}
if (sw) {
  syncSwitch();
  sw.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cur]");
    if (b) setCurrency(b.dataset.cur);
  });
}
onCurrency(() => {
  syncSwitch();
  renderPrices();
  if (grid) {
    if (qsa(".price[data-usd]", grid).length) qsa(".price[data-usd]", grid).forEach((el) => (el.textContent = money({ USD: +el.dataset.usd, GBP: +el.dataset.gbp, INR: +el.dataset.inr })));
    else renderServices(qs(".pill.active", filters)?.dataset.cat || "All");
  }
});

/* Contact form service options */
const svcSelect = qs("#c-service");
if (svcSelect) {
  SERVICES.forEach((s) => {
    const o = document.createElement("option");
    o.value = s.slug;
    o.textContent = `${s.name} (${money(s.prices)})`;
    svcSelect.appendChild(o);
  });
}

/* Contact form */
const form = qs("#contact-form");
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = qs("#contact-error");
    err.classList.add("hidden");
    const data = Object.fromEntries(new FormData(form).entries());
    if (!data.name || !data.email || !data.message) {
      err.textContent = "Please fill in your name, email and message.";
      err.classList.remove("hidden");
      return;
    }
    const btn = qs("button[type=submit]", form);
    setLoading(btn, true);
    try {
      const res = await api.post("/public/contact", data);
      toast({ title: "Message sent", body: res.message, type: "success" });
      form.reset();
    } catch (ex) {
      err.textContent = errorMessage(ex);
      err.classList.remove("hidden");
    } finally {
      setLoading(btn, false);
    }
  });
}

/* ---------- Smooth FAQ open/close ---------- */
(function smoothFaq() {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
  document.querySelectorAll(".faq details").forEach((d) => {
    const summary = d.querySelector("summary");
    const answer = d.querySelector(".answer");
    if (!summary || !answer || !answer.animate) return;
    let busy = false;
    summary.addEventListener("click", (e) => {
      e.preventDefault();
      if (busy) return;
      if (reduce.matches) {
        d.open = !d.open;
        document.dispatchEvent(new CustomEvent("df:layout"));
        return;
      }
      busy = true;
      const pad = getComputedStyle(answer).paddingBottom;
      answer.style.overflow = "hidden";
      if (d.open) {
        const h = answer.offsetHeight;
        const anim = answer.animate(
          [
            { height: h + "px", paddingBottom: pad, opacity: 1 },
            { height: "0px", paddingBottom: "0px", opacity: 0 },
          ],
          { duration: 240, easing: EASE }
        );
        anim.onfinish = () => {
          d.open = false;
          answer.style.overflow = "";
          busy = false;
          document.dispatchEvent(new CustomEvent("df:layout"));
        };
      } else {
        d.open = true;
        const h = answer.offsetHeight;
        const anim = answer.animate(
          [
            { height: "0px", paddingBottom: "0px", opacity: 0 },
            { height: h + "px", paddingBottom: pad, opacity: 1 },
          ],
          { duration: 300, easing: EASE }
        );
        anim.onfinish = () => {
          answer.style.overflow = "";
          busy = false;
          document.dispatchEvent(new CustomEvent("df:layout"));
        };
      }
    });
  });
})();

revealOnScroll();
initChrome();
