/* Designflow "Prism" landing page: sections rendered from the real service catalogue.
   Motion rules: one-shot entrances are CSS animations started by a class (compositor only),
   the only scroll-linked work is the hero parallax (transform/opacity), and every video
   plays only while it is on screen. Reduced motion = static page with video posters. */
import { SERVICES, CATEGORIES } from "./services-data.js";
import { qs, qsa, esc } from "../core/ui.js";
import { isLoggedIn, cachedUser, homeFor } from "../core/auth.js";
import { money, onCurrency } from "./currency.js";
import { scrollToTarget } from "./chrome.js";
import { mockup, MAIN_W } from "./mockups.js";

const gsap = window.gsap;
const ST = window.ScrollTrigger;
const reduceMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
const MOTION = Boolean(gsap && ST) && !reduceMQ.matches;
if (gsap && ST) gsap.registerPlugin(ST);

window.__sfReady = true; // tells the <head> failsafe that the motion layer is alive
const SF_MOTION = document.documentElement.classList.contains("sf-motion");

const BY = Object.fromEntries(SERVICES.map((s) => [s.slug, s]));
const IMG = (slug, kind = "") => `/assets/img/showcase/${slug}${kind ? `-${kind}` : ""}.webp?v=2`;
// every image ships at two sizes; the browser picks the one that fits (crisp on 4K, light on 1080p)
const SRCSET = { tall: ["tall-sm", 480, "tall", 960], main: ["sm", 600, "", 1200], thumb: ["thumb-sm", 240, "thumb", 480] };
// srcset with the real pixel widths (main renders are 600-1200 px wide, in each service's own format)
const srcsetFor = (slug, kind) => {
  const [a, aw, b, bwDefault] = SRCSET[kind];
  const bw = kind === "main" ? MAIN_W[slug] || bwDefault : bwDefault;
  return bw > aw ? `${IMG(slug, a)} ${aw}w, ${IMG(slug, b)} ${bw}w` : `${IMG(slug, b)} ${bw}w`;
};
const srcAttrs = (slug, kind, sizes) => `src="${IMG(slug, SRCSET[kind][2])}" srcset="${srcsetFor(slug, kind)}" sizes="${sizes}"`;
const setSrc = (img, slug, kind, sizes) => {
  img.sizes = sizes;
  img.srcset = srcsetFor(slug, kind);
  img.src = IMG(slug, SRCSET[kind][2]);
};
// pieces whose artwork is landscape or square are shown whole from the wide render
const WIDE = new Set(["logo-design", "youtube-thumbnail-design", "website-banner-design", "pitch-deck-design", "presentation-design", "brochure-design", "business-card-design", "custom-design-requests", "ecommerce-creative-design"]);
const kindFor = (slug) => (WIDE.has(slug) ? "main" : "tall");

const user = isLoggedIn() ? cachedUser() : null;
const orderHref = (slug) => {
  if (user) return user.role === "client" ? `/portal#/new?service=${encodeURIComponent(slug)}` : homeFor(user);
  return `/register?service=${encodeURIComponent(slug)}`;
};
const daysLabel = (n) => `${n}‑day delivery`;
const layoutChanged = () => document.dispatchEvent(new CustomEvent("df:layout"));
const currencyHooks = [];

/* ---------------------------------------------------------------- entrances */
const ENTER_MS = { rise: 1000, fade: 900, words: 1100 };
const byDomOrder = (a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);

function enter(els, type, { step = 80, maxSteps = 6 } = {}) {
  if (!SF_MOTION || !els.length) return;
  els.forEach((el) => el.setAttribute("data-enter", type));
  const io = new IntersectionObserver(
    (entries) => {
      const hits = entries.filter((e) => e.isIntersecting).map((e) => e.target).sort(byDomOrder);
      hits.forEach((el, k) => {
        io.unobserve(el);
        // staggered by start time (not CSS delay) so a big group never builds all its layers in one frame
        const words = type === "words" ? qsa(".pr-w", el).length * 70 : 0;
        setTimeout(() => {
          el.classList.add("is-in");
          setTimeout(() => {
            el.classList.remove("is-in");
            el.classList.add("is-done");
          }, ENTER_MS[type] + words + 80);
        }, Math.min(k, maxSteps) * step);
      });
    },
    { rootMargin: "0px 0px -8% 0px" }
  );
  els.forEach((el) => io.observe(el));
}

function splitWords(el) {
  if (el.dataset.splitDone) return;
  let i = 0;
  const walk = (node) => {
    Array.from(node.childNodes).forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        child.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) {
            frag.appendChild(document.createTextNode(" "));
            return;
          }
          const w = document.createElement("span");
          w.className = "pr-w";
          w.textContent = part;
          w.style.setProperty("--i", i++);
          frag.appendChild(w);
        });
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE) walk(child);
    });
  };
  walk(el);
  el.dataset.splitDone = "1";
}

/* ---------------------------------------------------------------- pipeline */
const PIPELINE = [
  ["Project manager", false],
  ["Strategy", false],
  ["Content", false],
  ["Design", false],
  ["QA", false],
  ["Designer approval", true],
  ["Delivery", false],
];

function initAgents() {
  const list = qs("#pr-agents");
  if (!list) return;
  const arrow = `<svg class="icon pr-agent-arrow" aria-hidden="true"><use href="/assets/img/icons.svg#chevron-right"></use></svg>`;
  list.innerHTML = PIPELINE.map(([name, human], i) => `<li class="pr-agent${human ? " is-human" : ""}" style="--i:${i}">${esc(name)}</li>${i < PIPELINE.length - 1 ? `<li aria-hidden="true">${arrow}</li>` : ""}`).join("");
}

/* ---------------------------------------------------------------- catalogue */
function initCatalogue() {
  const grid = qs("#pr-grid");
  const bar = qs("#pr-filters");
  if (!grid || !bar) return;
  const cats = CATEGORIES.filter((c) => SERVICES.some((s) => s.category === c));
  grid.innerHTML = SERVICES.map((s) => {
    return `<li data-cat="${esc(s.category)}">
      <a class="pr-svc" href="/services/${esc(s.slug)}">
        <span class="pr-svc-media" data-format="${mockup(s.slug).type}">${mockup(s.slug, { size: "(max-width: 600px) 70vw, max(14rem, 11.67vw)" }).html}</span>
        <span class="pr-svc-body">
          <span class="pr-svc-cat">${esc(s.category)}</span>
          <span class="pr-svc-name">${esc(s.name)}</span>
          <span class="pr-svc-tag">${esc(s.tagline)}</span>
          <span class="pr-svc-meta"><span><b data-price="${esc(s.slug)}">${money(s.prices)}</b> ${esc(s.price_unit || "per request")}</span><span>${daysLabel(s.turnaround_days)}</span></span>
        </span>
      </a>
    </li>`;
  }).join("");
  const count = (c) => SERVICES.filter((s) => s.category === c).length;
  bar.innerHTML = ["All", ...cats].map((c) => `<button type="button" class="pr-chip" data-filter="${esc(c)}" aria-pressed="${c === "All"}">${esc(c)}<small>${c === "All" ? SERVICES.length : count(c)}</small></button>`).join("");

  const items = qsa("li", grid);
  const setFilter = (cat) => {
    if (!["All", ...cats].includes(cat)) cat = "All";
    qsa(".pr-chip", bar).forEach((b) => b.setAttribute("aria-pressed", b.dataset.filter === cat ? "true" : "false"));
    const shown = [];
    items.forEach((li) => {
      const on = cat === "All" || li.dataset.cat === cat;
      if (on && li.hidden) shown.push(li);
      li.hidden = !on;
    });
    if (MOTION && !reduceMQ.matches) {
      shown.slice(0, 8).forEach((li, k) => li.animate([{ opacity: 0, transform: "translate3d(0, 1rem, 0)" }, { opacity: 1, transform: "none" }], { duration: 600, delay: k * 50, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "backwards" }));
    }
    layoutChanged();
  };
  bar.addEventListener("click", (e) => {
    const b = e.target.closest("[data-filter]");
    if (b) setFilter(b.dataset.filter);
  });
  // category names in the hero jump to the catalogue, already filtered
  qsa("[data-jump-cat]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      setFilter(a.dataset.jumpCat);
      scrollToTarget(qs(".pr-catalogue") || "#services");
    })
  );
  currencyHooks.push(() => qsa("[data-price]", grid).forEach((el) => (el.textContent = money(BY[el.dataset.price].prices))));
}

/* ---------------------------------------------------------------- work gallery */
// a bento wall: tall pieces span two rows, wide pieces two columns (auto-placed, dense)
const GALLERY = [
  ["poster-design", "tall"],
  ["logo-design", "wide"],
  ["instagram-post-design", "tall"],
  ["youtube-thumbnail-design", "wide"],
  ["business-card-design", "wide"],
  ["company-profile-design", "tall"],
  ["flyer-design", "tall"],
  ["website-banner-design", "wide contain"],
].filter(([s]) => BY[s]);

function initGallery() {
  const list = qs("#pr-gallery");
  if (!list) return;
  list.innerHTML = GALLERY.map(([slug, shape]) => {
    const s = BY[slug];
    const tall = shape.startsWith("tall");
    return `<li class="${shape.split(" ").map((c) => `g-${c}`).join(" ")}"><a class="pr-piece" href="/services/${esc(slug)}">
      <img ${srcAttrs(slug, tall ? "tall" : "main", tall ? "(max-width: 900px) 46vw, max(19rem, 15.83vw)" : "(max-width: 900px) 92vw, max(38rem, 31.67vw)")} alt="${esc(s.name)} made by Designflow" loading="lazy" decoding="async">
      <span class="pr-piece-cap"><b>${esc(s.name)}</b><span data-price="${esc(slug)}">${money(s.prices)}</span></span>
    </a></li>`;
  }).join("");

  currencyHooks.push(() => qsa("[data-price]", list).forEach((el) => (el.textContent = money(BY[el.dataset.price].prices))));
}

/* ---------------------------------------------------------------- price showcase */
/* Accessible custom select (listbox): thumbnails, prices, category groups, full keyboard support. */
function initPicker({ initial, onChange }) {
  const root = qs("#showcase-picker");
  const btn = qs("#showcase-btn");
  const pop = qs("#showcase-pop");
  const list = qs("#showcase-list");
  if (!root || !btn || !pop || !list) return null;
  const cats = CATEGORIES.filter((c) => SERVICES.some((s) => s.category === c));
  list.innerHTML = cats.map((c, gi) => `<li role="presentation" class="sf-picker-group">
      <span class="sf-picker-group-label" id="pick-grp-${gi}">${esc(c)}</span>
      <ul role="group" aria-labelledby="pick-grp-${gi}">${SERVICES.filter((s) => s.category === c).map((s) => `
        <li role="option" class="sf-picker-opt" id="pick-${esc(s.slug)}" data-value="${esc(s.slug)}" aria-selected="false">
          <img ${srcAttrs(s.slug, "thumb", "max(2.5rem, 2.08vw)")} alt="" width="40" height="40" loading="lazy" decoding="async">
          <span class="sf-picker-opt-text"><b>${esc(s.name)}</b><small>${daysLabel(s.turnaround_days)}</small></span>
          <span class="sf-picker-price" data-pp="${esc(s.slug)}">${money(s.prices)}</span>
          <svg class="icon icon-sm sf-picker-check" aria-hidden="true"><use href="/assets/img/icons.svg#check"></use></svg>
        </li>`).join("")}</ul>
    </li>`).join("");
  const opts = qsa("[role='option']", list);
  let value = initial;
  let active = Math.max(0, opts.findIndex((o) => o.dataset.value === value));
  let isOpen = false;
  let typed = "";
  let typedAt = 0;

  const paintButton = () => {
    const s = BY[value];
    qs("#showcase-btn-name").textContent = s.name;
    qs("#showcase-btn-meta").textContent = `${s.category} · ${money(s.prices)} · ${daysLabel(s.turnaround_days)}`;
    setSrc(qs("#showcase-btn-thumb"), s.slug, "thumb", "max(2.5rem, 2.08vw)");
    opts.forEach((o) => o.setAttribute("aria-selected", o.dataset.value === value ? "true" : "false"));
  };
  const setActive = (i, { scroll = true } = {}) => {
    active = (i + opts.length) % opts.length;
    opts.forEach((o, k) => o.classList.toggle("is-active", k === active));
    list.setAttribute("aria-activedescendant", opts[active].id);
    if (!scroll) return;
    const o = opts[active];
    const top = o.offsetTop - list.offsetTop;
    if (top < pop.scrollTop + 8) pop.scrollTop = Math.max(0, top - 36);
    else if (top + o.offsetHeight > pop.scrollTop + pop.clientHeight - 8) pop.scrollTop = top + o.offsetHeight - pop.clientHeight + 8;
  };
  const open = () => {
    if (isOpen) return;
    isOpen = true;
    const room = window.innerHeight - btn.getBoundingClientRect().bottom;
    root.classList.toggle("is-up", room < 380);
    pop.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    setActive(opts.findIndex((o) => o.dataset.value === value));
    requestAnimationFrame(() => root.classList.add("is-open"));
    list.focus({ preventScroll: true });
  };
  const close = (refocus = true) => {
    if (!isOpen) return;
    isOpen = false;
    root.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
    setTimeout(() => { if (!isOpen) pop.hidden = true; }, 220);
    if (refocus) btn.focus({ preventScroll: true });
  };
  const choose = (i) => {
    const next = opts[i].dataset.value;
    close();
    if (next !== value) {
      value = next;
      paintButton();
      onChange(value);
    }
  };

  btn.addEventListener("click", () => (isOpen ? close() : open()));
  btn.addEventListener("keydown", (e) => {
    if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
      e.preventDefault();
      open();
    }
  });
  list.addEventListener("keydown", (e) => {
    const k = e.key;
    if (k === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
    else if (k === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
    else if (k === "Home") { e.preventDefault(); setActive(0); }
    else if (k === "End") { e.preventDefault(); setActive(opts.length - 1); }
    else if (k === "Enter" || k === " ") { e.preventDefault(); choose(active); }
    else if (k === "Escape") { e.preventDefault(); close(); }
    else if (k === "Tab") close(false);
    else if (k.length === 1 && /\S/.test(k)) {
      const now = performance.now();
      typed = (now - typedAt > 600 ? "" : typed) + k.toLowerCase();
      typedAt = now;
      const start = typed.length === 1 ? active + 1 : active;
      for (let n = 0; n < opts.length; n++) {
        const i = (start + n) % opts.length;
        if (BY[opts[i].dataset.value].name.toLowerCase().startsWith(typed)) { setActive(i); break; }
      }
    }
  });
  list.addEventListener("click", (e) => {
    const o = e.target.closest("[role='option']");
    if (o) choose(opts.indexOf(o));
  });
  list.addEventListener("pointermove", (e) => {
    const o = e.target.closest("[role='option']");
    if (o && opts.indexOf(o) !== active) setActive(opts.indexOf(o), { scroll: false });
  });
  document.addEventListener("pointerdown", (e) => { if (isOpen && !root.contains(e.target)) close(false); });
  paintButton();
  return {
    repaint: () => {
      paintButton();
      qsa("[data-pp]", list).forEach((el) => (el.textContent = money(BY[el.dataset.pp].prices)));
    },
  };
}

function initShowcase() {
  const img = qs("#showcase-img");
  if (!img) return;
  let current = BY["logo-design"] ? "logo-design" : SERVICES[0].slug;
  const picker = initPicker({ initial: current, onChange: (v) => swap(v) });
  if (picker) currencyHooks.push(picker.repaint);

  const paintText = () => {
    const s = BY[current];
    qs("#showcase-name").textContent = s.name;
    qs("#showcase-tag").textContent = s.tagline;
    qs("#showcase-price").textContent = money(s.prices);
    qs("#showcase-unit").textContent = s.price_unit || "per request";
    qs("#showcase-days").textContent = `${daysLabel(s.turnaround_days)} · unlimited revisions · source files`;
    const order = qs("#showcase-order");
    order.href = orderHref(s.slug);
    order.dataset.service = s.slug;
  };
  const setImage = (slug) => {
    setSrc(img, slug, "main", "(max-width: 900px) 80vw, max(30rem, 25vw)");
    img.alt = `Designflow ${BY[slug].name.toLowerCase()} example`;
  };
  paintText();
  setImage(current);
  currencyHooks.push(paintText);

  const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
  let token = 0;
  async function swap(slug) {
    current = slug;
    paintText();
    if (!MOTION || !img.animate) {
      setImage(slug);
      return;
    }
    const mine = ++token;
    qsa("#showcase-name, #showcase-tag, #showcase-price").forEach((el, k) =>
      el.animate([{ opacity: 0, transform: "translate3d(0, 0.75rem, 0)" }, { opacity: 1, transform: "none" }], { duration: 550, delay: k * 50, easing: EASE, fill: "backwards" })
    );
    await img.animate([{ opacity: 1, filter: "blur(0)", transform: "none" }, { opacity: 0, filter: "blur(0.75rem)", transform: "scale(0.96)" }], { duration: 220, easing: "ease-in", fill: "forwards" }).finished.catch(() => {});
    if (mine !== token) return;
    setImage(slug);
    if (img.decode) await img.decode().catch(() => {});
    if (mine !== token) return;
    img.getAnimations().forEach((a) => a.cancel());
    img.animate([{ opacity: 0, filter: "blur(0.75rem)", transform: "scale(1.04)" }, { opacity: 1, filter: "blur(0)", transform: "none" }], { duration: 700, easing: EASE });
  }
}

/* ---------------------------------------------------------------- video */
function initVideos() {
  const vids = qsa("video[data-video]");
  if (!vids.length) return;
  const saveData = navigator.connection && navigator.connection.saveData;
  if (!MOTION || saveData) {
    vids.forEach((v) => v.removeAttribute("autoplay"));
    return; // posters only
  }
  const io = new IntersectionObserver(
    (entries) =>
      entries.forEach(({ target: v, isIntersecting }) => {
        if (isIntersecting) {
          if (v.preload !== "auto") v.preload = "auto";
          const p = v.play();
          if (p && p.catch) p.catch(() => {});
        } else if (!v.paused) v.pause();
      }),
    { rootMargin: "120px 0px" }
  );
  vids.forEach((v) => {
    v.muted = true; // required for autoplay everywhere
    io.observe(v);
  });
}

/* ---------------------------------------------------------------- hero scroll */
function initHero() {
  const hero = qs(".pr-hero");
  if (!hero || !MOTION) return;
  gsap.to("[data-hero-media]", { yPercent: 14, scale: 1.06, ease: "none", scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true } });
  gsap.to("[data-hero-inner]", { yPercent: -16, opacity: 0.15, ease: "none", scrollTrigger: { trigger: hero, start: "top top", end: "bottom 20%", scrub: true } });
}

/* ---------------------------------------------------------------- reveals + housekeeping */
function initReveals() {
  const heads = qsa("[data-split]");
  if (SF_MOTION) heads.forEach(splitWords);
  enter(heads, "words", { step: 0 });
  enter(qsa("[data-reveal]"), "rise", { step: 90 });
}

function pauseOffscreenLoops() {
  const io = new IntersectionObserver((entries) => entries.forEach((e) => e.target.classList.toggle("is-offscreen", !e.isIntersecting)));
  qsa(".pr-agents, .pr-feature-media").forEach((el) => io.observe(el));
}

function warmImages() {
  // fetch + decode below-the-fold images while the browser is idle, so nothing decodes mid-scroll
  const imgs = qsa("main img[loading='lazy']");
  const idle = window.requestIdleCallback || ((fn) => setTimeout(() => fn({ timeRemaining: () => 8 }), 120));
  const step = () =>
    idle((deadline) => {
      let k = 0;
      while (imgs.length && k < 3 && deadline.timeRemaining() > 4) {
        const img = imgs.shift();
        k += 1;
        if (!img.getAttribute("src")) continue;
        img.loading = "eager";
        if (img.decode) img.decode().catch(() => {});
      }
      if (imgs.length) step();
    });
  step();
}

function boot() {
  initAgents();
  initCatalogue();
  initGallery();
  initShowcase();
  initVideos();
  initHero();
  initReveals();
  pauseOffscreenLoops();
  onCurrency(() => currencyHooks.forEach((fn) => fn()));
  if (document.readyState === "complete") warmImages();
  else window.addEventListener("load", warmImages, { once: true });
  if (MOTION) {
    window.addEventListener("load", () => ST.refresh(), { once: true });
    reduceMQ.addEventListener("change", () => window.location.reload());
  }
}

boot();
