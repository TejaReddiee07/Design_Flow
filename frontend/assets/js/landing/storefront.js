/* Landing storefront: renders every section from the real service catalogue and
   drives the motion (GSAP + ScrollTrigger, smooth scroll from chrome.js).
   Only two sections pin (Pick a Format, The Identity Collection); the rest scrub
   or reveal. With reduced motion, or without the vendor scripts, every section
   renders its final, static state and stays fully usable. */
import { SERVICES, CATEGORIES } from "./services-data.js";
import { qs, qsa, esc, icon } from "../core/ui.js";
import { isLoggedIn, cachedUser, homeFor } from "../core/auth.js";
import { money, onCurrency } from "./currency.js";
import { getLenis, lockScroll } from "./chrome.js";
import { AgentOrb } from "../core/agent-orb.js";

const gsap = window.gsap;
const ST = window.ScrollTrigger;
const reduceMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
const MOTION = Boolean(gsap && ST) && !reduceMQ.matches;
const CAN_HOVER = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
if (gsap && ST) gsap.registerPlugin(ST);

window.__sfReady = true; // tells the <head> failsafe that the motion layer is alive
const SF_MOTION = document.documentElement.classList.contains("sf-motion");
const BY = Object.fromEntries(SERVICES.map((s) => [s.slug, s]));
const IMG = (slug, kind = "") => `/assets/img/showcase/${slug}${kind ? `-${kind}` : ""}.webp`;
// Every image ships at two sizes; the browser picks the one that fits the screen (crisp on 4K,
// light to decode and paint on 1080p).
const SRCSET = { tall: ["tall-sm", 480, "tall", 960], main: ["sm", 600, "", 1200], thumb: ["thumb-sm", 240, "thumb", 480] };
const srcAttrs = (slug, kind, sizes) => {
  const [a, aw, b, bw] = SRCSET[kind];
  return `src="${IMG(slug, b)}" srcset="${IMG(slug, a)} ${aw}w, ${IMG(slug, b)} ${bw}w" sizes="${sizes}"`;
};
const setSrc = (img, slug, kind, sizes) => {
  const [a, aw, b, bw] = SRCSET[kind];
  img.sizes = sizes;
  img.srcset = `${IMG(slug, a)} ${aw}w, ${IMG(slug, b)} ${bw}w`;
  img.src = IMG(slug, b);
};
const user = isLoggedIn() ? cachedUser() : null;
const orderHref = (slug) => {
  if (user) return user.role === "client" ? `/portal#/new?service=${encodeURIComponent(slug)}` : homeFor(user);
  return `/register?service=${encodeURIComponent(slug)}`;
};
const daysLabel = (n) => `${n}‑day delivery`;
// Pieces whose source artwork is landscape or square: shown whole (contain), never cropped to portrait.
const WIDE = new Set(["logo-design", "youtube-thumbnail-design", "website-banner-design", "pitch-deck-design", "presentation-design", "brochure-design", "business-card-design", "custom-design-requests", "ecommerce-creative-design"]);
const fromPrice = (slugs) => {
  const list = slugs.map((s) => BY[s]).filter(Boolean);
  const cheapest = list.reduce((a, b) => (a.prices.USD <= b.prices.USD ? a : b));
  return money(cheapest.prices);
};
const layoutChanged = () => document.dispatchEvent(new CustomEvent("df:layout"));
const currencyHooks = [];

/* ---------------------------------------------------------------- entrances */
// One-shot entrances are CSS animations (compositor thread) started by a class when the element
// scrolls into view; JS only flips classes, it never touches styles frame by frame.
const ENTER_MS = { rise: 1000, look: 1300, hang: 1350, chip: 600, fade: 1000, words: 1150 };
const byDomOrder = (a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);

function enter(els, type, { step = 70, maxSteps = 8 } = {}) {
  if (!SF_MOTION || !els.length) return;
  els.forEach((el) => el.setAttribute("data-enter", type));
  const io = new IntersectionObserver(
    (entries) => {
      const hits = entries.filter((e) => e.isIntersecting).map((e) => e.target).sort(byDomOrder);
      hits.forEach((el, k) => {
        io.unobserve(el);
        // Staggered by starting each element at its own moment (not a CSS delay): a delayed CSS
        // animation is composited immediately, so a big group would build all its layers in one frame.
        const d = Math.min(k, maxSteps) * step;
        const words = type === "words" ? qsa(".sf-w > span", el).length * 60 : 0;
        setTimeout(() => {
          el.classList.add("is-in");
          setTimeout(() => {
            el.classList.remove("is-in");
            el.classList.add("is-done");
          }, ENTER_MS[type] + words + 80);
        }, d);
      });
    },
    { rootMargin: "0px 0px -8% 0px" }
  );
  els.forEach((el) => io.observe(el));
}

/* ---------------------------------------------------------------- split text */
function splitWords(el) {
  if (el.dataset.splitDone) return qsa(".sf-w > span", el);
  let wordIndex = 0;
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
          w.className = "sf-w";
          const inner = document.createElement("span");
          inner.textContent = part;
          inner.style.setProperty("--wd", `${wordIndex++ * 60}ms`);
          w.appendChild(inner);
          frag.appendChild(w);
        });
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        walk(child);
      }
    });
  };
  walk(el);
  el.dataset.splitDone = "1";
  return qsa(".sf-w > span", el);
}

/* ---------------------------------------------------------------- dialogs */
function makeDialog(root, panelSel, from) {
  const panel = qs(panelSel, root);
  const scrim = qs("[class$='-scrim']", root);
  let lastFocus = null;
  let isOpen = false;
  const focusables = () =>
    qsa('a[href], button:not([disabled]), select, input, textarea, [tabindex]:not([tabindex="-1"])', root).filter(
      (el) => el.offsetParent !== null
    );

  function show() {
    lastFocus = document.activeElement;
    root.hidden = false;
    isOpen = true;
    lockScroll(true);
    panel.scrollTop = 0;
    if (MOTION) {
      gsap.killTweensOf([panel, scrim]);
      gsap.fromTo(scrim, { opacity: 0 }, { opacity: 1, duration: 0.45, ease: "power2.out" });
      gsap.fromTo(panel, from, { x: 0, y: 0, scale: 1, opacity: 1, duration: 0.8, ease: "expo.out", clearProps: "transform" });
    }
    requestAnimationFrame(() => {
      const close = qs(".sf-close", root);
      if (close) close.focus({ preventScroll: true });
    });
  }

  function hide() {
    if (!isOpen) return;
    isOpen = false;
    const done = () => {
      root.hidden = true;
      lockScroll(false);
      if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
    };
    if (MOTION) {
      gsap.to(scrim, { opacity: 0, duration: 0.35, ease: "power2.in" });
      gsap.to(panel, { ...from, duration: 0.45, ease: "power3.in", onComplete: done });
    } else done();
  }

  root.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) hide();
  });
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      hide();
    } else if (e.key === "Tab") {
      const f = focusables();
      if (!f.length) return;
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
  return { show, hide, get open() { return isOpen; } };
}

/* ---------------------------------------------------------------- marquee + prices */
function initMarquee() {
  const el = qs("#marquee");
  if (!el) return;
  const names = SERVICES.map((s) => `<span>${esc(s.name)}</span>`).join("");
  el.innerHTML = names + names;
}

function initPriceSpans() {
  const paint = () =>
    qsa("[data-price-of]").forEach((el) => {
      const s = BY[el.dataset.priceOf];
      if (s) el.textContent = money(s.prices);
    });
  paint();
  currencyHooks.push(paint);
}

/* ---------------------------------------------------------------- shop the look */
const LOOKS = [
  { id: "launch", name: "The Launch", kicker: "Branding", img: "company-profile-design",
    slugs: ["logo-design", "business-card-design", "company-profile-design"],
    intro: "Everything a new brand needs on day one: the mark, the card and the story." },
  { id: "feed", name: "The Feed", kicker: "Social media", img: "reels-cover-design",
    slugs: ["social-media-design", "instagram-post-design", "linkedin-carousel-design", "youtube-thumbnail-design", "reels-cover-design"],
    intro: "A consistent, scroll-stopping presence across Instagram, LinkedIn and YouTube." },
  { id: "campaign", name: "The Campaign", kicker: "Advertising", img: "ad-creative-design",
    slugs: ["ad-creative-design", "website-banner-design", "ecommerce-creative-design", "product-advertisement-design"],
    intro: "Creatives that sell: ads, banners and product visuals for every placement." },
  { id: "pitch", name: "The Pitch", kicker: "Presentations & content", img: "infographic-design",
    slugs: ["pitch-deck-design", "presentation-design", "infographic-design"],
    intro: "Decks and data that make people lean in, from investors to the board." },
  { id: "print", name: "The Print Run", kicker: "Print", img: "poster-design",
    slugs: ["brochure-design", "flyer-design", "poster-design"],
    intro: "Paper that earns a second look: brochures, flyers and posters, press-ready." },
].map((l) => ({ ...l, slugs: l.slugs.filter((s) => BY[s]) }));

function initLooks() {
  const row = qs("#looks-row");
  const root = qs("#look-panel");
  if (!row || !root) return;
  const dialog = makeDialog(root, ".sf-sheet-panel", { x: 60, opacity: 0 });
  let openLook = null;

  const card = (l, i) => `<li>
    <button class="look" type="button" data-look="${l.id}" aria-haspopup="dialog" aria-controls="look-panel">
      <span class="look-figure">
        <img ${srcAttrs(l.img, "tall", "(max-width: 900px) 62vw, 15vw")} alt="" loading="lazy" decoding="async">
        <span class="look-cta" aria-hidden="true">View the look ${icon("arrow-right", "icon-sm")}</span>
      </span>
      <span class="look-floor" aria-hidden="true"></span>
      <span class="look-meta">
        <span class="look-index">${String(i + 1).padStart(2, "0")}</span>
        <b>${esc(l.name)}</b>
        <small>${l.slugs.length} pieces · from <span data-look-from="${l.id}">${fromPrice(l.slugs)}</span></small>
      </span>
    </button>
  </li>`;
  row.innerHTML = LOOKS.map(card).join("");

  const items = (l) =>
    l.slugs
      .map((slug) => {
        const s = BY[slug];
        return `<li><a class="look-item" href="/services/${esc(slug)}">
          <img ${srcAttrs(slug, "thumb", "5rem")} alt="" width="76" height="76" loading="lazy" decoding="async">
          <span><b>${esc(s.name)}</b><small>${esc(s.tagline)}</small><small>${daysLabel(s.turnaround_days)}</small></span>
          <span class="li-price">${money(s.prices)}<small>${esc(s.price_unit || "per request")}</small></span>
        </a></li>`;
      })
      .join("");

  const fill = (l) => {
    qs("#look-panel-kicker").textContent = l.kicker;
    qs("#look-panel-title").textContent = l.name;
    qs("#look-panel-intro").textContent = l.intro;
    qs("#look-items").innerHTML = items(l);
  };

  row.addEventListener("click", (e) => {
    const b = e.target.closest("[data-look]");
    if (!b) return;
    openLook = LOOKS.find((l) => l.id === b.dataset.look);
    fill(openLook);
    dialog.show();
    if (MOTION) {
      gsap.fromTo(qsa(".look-item", root), { x: 30, opacity: 0 }, { x: 0, opacity: 1, duration: 0.7, ease: "expo.out", stagger: 0.06, delay: 0.15 });
    }
  });

  currencyHooks.push(() => {
    LOOKS.forEach((l) => {
      const el = qs(`[data-look-from="${l.id}"]`, row);
      if (el) el.textContent = fromPrice(l.slugs);
    });
    if (dialog.open && openLook) qs("#look-items").innerHTML = items(openLook);
  });

  enter(qsa(".look", row), "look", { step: 90 });
  if (MOTION) {
    const lis = qsa("li", row);
    lis.forEach((li, i) => {
      gsap.fromTo(li, { yPercent: i % 2 ? 6 : 0 }, {
        yPercent: i % 2 ? -6 : -2,
        ease: "none",
        scrollTrigger: { trigger: row, start: "top bottom", end: "bottom top", scrub: 1.2 },
      });
    });
  }
}

/* ---------------------------------------------------------------- pick a format (horizontal) */
const FORMATS = [
  { slug: "logo-design", word: "Logos", label: "Logos & identity", sub: "Vector, every format", fc: "#6e1f33", fi: "#f1e3bd" },
  { slug: "youtube-thumbnail-design", word: "Thumbnails", label: "YouTube thumbnails", sub: "Built for click-through", fc: "#c9a24b", fi: "#3b0f1b" },
  { slug: "linkedin-carousel-design", word: "Carousels", label: "LinkedIn carousels", sub: "Swipeable PDFs", fc: "#efe3cf", fi: "#6e1f33" },
  { slug: "pitch-deck-design", word: "Decks", label: "Pitch decks", sub: "Investor-ready", fc: "#2b1520", fi: "#e6cd8e" },
  { slug: "ad-creative-design", word: "Ads", label: "Ad creatives", sub: "Every placement size", fc: "#9a3b4f", fi: "#fbf3e6" },
  { slug: "poster-design", word: "Posters", label: "Posters & print", sub: "Press-ready files", fc: "#1f3b33", fi: "#e6cd8e" },
  { slug: "reels-cover-design", word: "Reels", label: "Reels covers", sub: "A grid that looks curated", fc: "#d9b65f", fi: "#4a1322" },
  { slug: "business-card-design", word: "Cards", label: "Business cards", sub: "Foil-ready print files", fc: "#3b0f1b", fi: "#f1e3bd" },
  { slug: "infographic-design", word: "Data", label: "Infographics", sub: "Numbers people remember", fc: "#b5536b", fi: "#fff4e6" },
].filter((f) => BY[f.slug]);

function initFormats(mm) {
  const section = qs("#work");
  const track = qs("#formats-track");
  if (!section || !track) return;
  track.innerHTML = FORMATS.map((f) => {
    const s = BY[f.slug];
    const k = Math.min(0.34, 0.9 / (f.word.length * 0.52)).toFixed(3);
    const wide = WIDE.has(f.slug);
    return `<li class="format${wide ? " is-wide" : ""}">
      <a class="format-link" href="/services/${esc(f.slug)}" style="--fc:${f.fc};--fi:${f.fi};--k:${k}">
        <span class="format-media"><img ${srcAttrs(f.slug, wide ? "main" : "tall", "(max-width: 900px) 70vw, 20vw")} alt="Designflow ${esc(s.name.toLowerCase())} example" loading="lazy" decoding="async"></span>
        <span class="format-title" aria-hidden="true">${esc(f.word)}</span>
        <span class="format-meta"><b>${esc(f.label)}</b><span>${esc(f.sub)}</span><span class="fm-price" data-fm="${esc(f.slug)}">${esc(s.name)} · ${money(s.prices)} · ${daysLabel(s.turnaround_days)}</span></span>
      </a>
    </li>`;
  }).join("");

  currencyHooks.push(() =>
    qsa("[data-fm]", track).forEach((el) => {
      const s = BY[el.dataset.fm];
      el.textContent = `${s.name} · ${money(s.prices)} · ${daysLabel(s.turnaround_days)}`;
    })
  );

  if (MOTION && CAN_HOVER) {
    qsa(".format-link", track).forEach((cardEl) => {
      const rx = gsap.quickTo(cardEl, "rotationX", { duration: 0.6, ease: "power3" });
      const ry = gsap.quickTo(cardEl, "rotationY", { duration: 0.6, ease: "power3" });
      const sc = gsap.quickTo(cardEl, "scale", { duration: 0.6, ease: "power3" });
      cardEl.addEventListener("pointermove", (e) => {
        const r = cardEl.getBoundingClientRect();
        ry(((e.clientX - r.left) / r.width - 0.5) * 12);
        rx(-((e.clientY - r.top) / r.height - 0.5) * 10);
        sc(1.035);
      });
      cardEl.addEventListener("pointerleave", () => {
        rx(0);
        ry(0);
        sc(1);
      });
    });
  }

  if (!MOTION) {
    section.classList.add("is-native");
    return;
  }

  mm.add({ wide: "(min-width: 960px)", narrow: "(max-width: 959px)" }, (ctx) => {
    if (ctx.conditions.narrow) {
      section.classList.add("is-native");
      return () => section.classList.remove("is-native");
    }
    section.classList.add("is-pinned");
    const bar = qs(".formats-progress span", section);
    const distance = () => Math.max(0, track.scrollWidth - document.documentElement.clientWidth);
    const tween = gsap.to(track, {
      x: () => -distance(),
      ease: "none",
      scrollTrigger: {
        trigger: section,
        start: "top top",
        end: () => `+=${distance()}`,
        pin: true,
        scrub: 1,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        onUpdate: (self) => bar && gsap.set(bar, { scaleX: self.progress }),
      },
    });
    qsa(".format", track).forEach((li) => {
      const img = qs(".format-media img", li);
      gsap.fromTo(img, { xPercent: -5 }, {
        xPercent: 5,
        ease: "none",
        scrollTrigger: { trigger: li, containerAnimation: tween, start: "left right", end: "right left", scrub: true },
      });
    });
    return () => section.classList.remove("is-pinned");
  });
}

/* ---------------------------------------------------------------- the rack */
const HOOK = `<svg class="hanger-hook" viewBox="0 0 96 58" aria-hidden="true"><path d="M48 25V18c0-3.4 5.5-4.4 5.5-9.6a5.5 5.5 0 0 0-11 0" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/><path d="M48 25 7 52.5c-2.6 1.8-1.6 4.5 1.4 4.5h79.2c3 0 4-2.7 1.4-4.5Z" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linejoin="round"/></svg>`;

function initRack() {
  const chipsEl = qs("#rack-chips");
  const grid = qs("#rack-grid");
  const root = qs("#rack-focus");
  if (!chipsEl || !grid || !root) return;
  const dialog = makeDialog(root, ".rack-focus-card", { y: 50, scale: 0.96, opacity: 0 });
  let focused = null;

  const cats = ["All", ...CATEGORIES.filter((c) => SERVICES.some((s) => s.category === c))];
  chipsEl.innerHTML = cats
    .map((c, i) => {
      const n = c === "All" ? SERVICES.length : SERVICES.filter((s) => s.category === c).length;
      return `<button type="button" class="rack-chip" data-cat="${esc(c)}" aria-pressed="${i === 0}">${esc(c)} <small>${n}</small></button>`;
    })
    .join("");

  grid.innerHTML = SERVICES.map((s) => `<li class="hanger" data-cat="${esc(s.category)}">
    <button type="button" class="hanger-btn" data-slug="${esc(s.slug)}" aria-haspopup="dialog" aria-controls="rack-focus">
      ${HOOK}
      <span class="hanger-card">
        <span class="hanger-img"><img ${srcAttrs(s.slug, "thumb", "(max-width: 760px) 45vw, 13vw")} alt="" loading="lazy" decoding="async" width="280" height="280"></span>
        <span class="hanger-tag"><b>${esc(s.name)}</b><span class="hp" data-hp="${esc(s.slug)}">${money(s.prices)}</span><small>${daysLabel(s.turnaround_days)}</small></span>
      </span>
    </button>
  </li>`).join("");

  const btns = () => qsa(".hanger", grid).filter((li) => !li.hidden).map((li) => li.firstElementChild);
  let busy = null;

  function applyFilter(cat) {
    qsa(".rack-chip", chipsEl).forEach((c) => c.setAttribute("aria-pressed", c.dataset.cat === cat ? "true" : "false"));
    const lis = qsa(".hanger", grid);
    const keep = (li) => cat === "All" || li.dataset.cat === cat;
    if (!MOTION) {
      lis.forEach((li) => (li.hidden = !keep(li)));
      layoutChanged();
      return;
    }
    if (busy) busy.progress(1).kill();
    const outgoing = btns();
    busy = gsap.timeline({ onComplete: () => (busy = null) });
    busy
      .to(outgoing, {
        y: -26,
        rotation: () => gsap.utils.random(-8, 8),
        opacity: 0,
        duration: 0.3,
        ease: "power2.in",
        stagger: { amount: 0.18 },
      })
      .add(() => {
        lis.forEach((li) => (li.hidden = !keep(li)));
        layoutChanged();
        gsap.fromTo(
          btns(),
          { y: -48, rotation: () => gsap.utils.random(-10, 10), opacity: 0 },
          { y: 0, rotation: 0, opacity: 1, duration: 1.2, ease: "elastic.out(1, 0.55)", stagger: { amount: 0.45 }, overwrite: true, clearProps: "transform,opacity" }
        );
      });
  }

  chipsEl.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cat]");
    if (b && b.getAttribute("aria-pressed") !== "true") applyFilter(b.dataset.cat);
  });

  const fill = (s) => {
    const img = qs("#rf-img");
    setSrc(img, s.slug, "main", "(max-width: 760px) 90vw, 30vw");
    img.alt = `Designflow ${s.name.toLowerCase()} example`;
    qs("#rf-cat").textContent = s.category;
    qs("#rf-title").textContent = s.name;
    qs("#rf-tagline").textContent = s.tagline;
    qs("#rf-desc").textContent = s.description;
    qs("#rf-deliv").innerHTML = (s.deliverables || []).map((d) => `<li>${esc(d)}</li>`).join("");
    qs("#rf-price").textContent = money(s.prices);
    qs("#rf-unit").textContent = s.price_unit || "per request";
    qs("#rf-days").textContent = `${daysLabel(s.turnaround_days)} · unlimited revisions`;
    qs("#rf-order").href = orderHref(s.slug);
    qs("#rf-view").href = `/services/${s.slug}`;
  };

  grid.addEventListener("click", (e) => {
    const b = e.target.closest(".hanger-btn");
    if (!b) return;
    focused = BY[b.dataset.slug];
    fill(focused);
    dialog.show();
  });

  currencyHooks.push(() => {
    qsa("[data-hp]", grid).forEach((el) => (el.textContent = money(BY[el.dataset.hp].prices)));
    if (dialog.open && focused) qs("#rf-price").textContent = money(focused.prices);
  });

  const hangers = qsa(".hanger-btn", grid);
  hangers.forEach((b, k) => b.style.setProperty("--r", `${(k % 2 ? -1 : 1) * (4 + ((k * 37) % 5))}deg`));
  enter(hangers, "hang", { step: 60, maxSteps: 10 });
}

/* ---------------------------------------------------------------- watch it build */
const PIPELINE = [
  ["project_manager", "Project Manager", "Plans the work and sets priority"],
  ["strategy", "Strategy", "Researches your brand and competitors"],
  ["content", "Content", "Writes the copy and concept directions"],
  ["design", "Design", "Drafts the visuals from your brief"],
  ["qa", "QA", "Scores every draft against your brief"],
  ["approval", "Designer approval", "A designer finishes and approves the work"],
  ["delivery", "Delivery", "Files land in your portal, ready to download"],
];

function initBuild(mm) {
  const stage = qs("#build-stage");
  const canvas = qs("#build-orb");
  if (!stage || !canvas) return;
  const nameEl = qs("#build-agent");
  const noteEl = qs("#build-note");
  let orb = null;
  let step = 0;
  let timer = 0;

  const show = (i, animate) => {
    const [key, name, note] = PIPELINE[i];
    if (orb) orb.set(key, "running");
    if (animate && MOTION) {
      gsap.to([nameEl, noteEl], {
        y: -10,
        opacity: 0,
        duration: 0.25,
        ease: "power2.in",
        onComplete: () => {
          nameEl.textContent = name;
          noteEl.textContent = note;
          gsap.fromTo([nameEl, noteEl], { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, ease: "expo.out", stagger: 0.05 });
        },
      });
    } else {
      nameEl.textContent = name;
      noteEl.textContent = note;
    }
  };

  const io = new IntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting) {
        if (!orb) {
          orb = new AgentOrb(canvas, { seed: 11, particles: 380, maxDpr: 1.5, fps: 30 });
          show(step, false);
        }
        if (MOTION && !timer) {
          timer = window.setInterval(() => {
            step = (step + 1) % PIPELINE.length;
            show(step, true);
          }, 2800);
        }
      } else if (timer) {
        window.clearInterval(timer);
        timer = 0;
      }
    },
    { rootMargin: "120px 0px" }
  );
  io.observe(stage);
  // build the orb while the browser is idle, not at the moment its section scrolls into view
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 600));
  const prepare = () => idle(() => {
    if (!orb) {
      orb = new AgentOrb(canvas, { seed: 11, particles: 380, maxDpr: 1.5, fps: 30 });
      show(step, false);
    }
  });
  if (document.readyState === "complete") prepare();
  else window.addEventListener("load", prepare, { once: true });

  if (!MOTION) return;
  mm.add("(min-width: 961px)", () => {
    gsap.fromTo("[data-build-center]", { scale: 0.8 }, {
      scale: 1.08,
      ease: "none",
      scrollTrigger: { trigger: stage, start: "top 90%", end: "bottom 15%", scrub: 1.2 },
    });
    qsa(".build-side", stage).forEach((fig) => {
      const d = parseFloat(fig.dataset.drift || "0");
      gsap.fromTo(fig, { x: d * 18, y: 56 * Math.abs(d) }, {
        x: -d * 38,
        y: -44 * Math.abs(d),
        ease: "none",
        scrollTrigger: { trigger: stage, start: "top bottom", end: "bottom top", scrub: 1.4 },
      });
    });
  });
  enter(qsa(".build-pipeline li"), "chip", { step: 45, maxSteps: 9 });
}

/* ---------------------------------------------------------------- identity collection */
const COLLECTION = ["logo-design", "business-card-design", "company-profile-design", "pitch-deck-design", "brochure-design"].filter((s) => BY[s]);

function initArches(mm) {
  const section = qs("#collection");
  const wrap = qs("#arches");
  if (!section || !wrap || !COLLECTION.length) return;
  const n = COLLECTION.length;
  wrap.innerHTML = COLLECTION.map((slug, i) => `<div class="arch" data-i="${i}" aria-hidden="true"><div class="arch-frame"><img ${srcAttrs(slug, "tall", "(max-width: 900px) 60vw, 20vw")} alt="""" loading="lazy" decoding="async" draggable="false"></div></div>`).join("");
  const arches = qsa(".arch", wrap);
  const state = { p: Math.floor(n / 2) };
  let shown = -1;
  let st = null;
  let syncing = false;
  const clamp = (v) => Math.max(0, Math.min(n - 1, v));

  const caption = (i, animate) => {
    const s = BY[COLLECTION[i]];
    const fillText = () => {
      qs("#arch-cat").textContent = `${String(i + 1).padStart(2, "0")} / ${String(n).padStart(2, "0")} · ${s.category}`;
      qs("#arch-name").textContent = s.name;
      qs("#arch-tag").textContent = s.tagline;
      qs("#arch-price").textContent = money(s.prices);
      qs("#arch-days").textContent = daysLabel(s.turnaround_days);
      qs("#arch-order").href = orderHref(s.slug);
      qs("#arch-order").setAttribute("aria-label", `Order ${s.name}`);
    };
    if (animate && MOTION) {
      const parts = qsa(".arch-text > *", section);
      gsap.killTweensOf(parts);
      gsap.to(parts, {
        y: -8,
        opacity: 0,
        duration: 0.18,
        ease: "power2.in",
        onComplete: () => {
          fillText();
          gsap.fromTo(parts, { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.55, ease: "expo.out", stagger: 0.04 });
        },
      });
    } else fillText();
  };

  // The fan is a ring: every arch sits at its shortest distance from the centre, so there are
  // always two arches either side and the set never bunches up at one end.
  const ring = (v) => ((v % n) + n) % n;
  let spacing = 200;
  const measure = () => {
    spacing = (arches[0].offsetWidth || 260) * 0.78;
  };
  const layout = () => {
    const half = n / 2;
    arches.forEach((el, i) => {
      let o = ring(i - state.p + half) - half;
      if (o === -half) o = half;
      const a = Math.abs(o);
      const x = o * spacing * (1 - Math.min(a, 3) * 0.05);
      const y = Math.pow(a, 1.35) * 24;
      const s = 1 - Math.min(a, 3) * 0.13;
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) rotate(${(o * 8).toFixed(2)}deg) scale(${s.toFixed(3)})`;
      el.style.zIndex = String(100 - Math.round(a * 10));
      el.style.opacity = a > half - 0.5 ? Math.max(0, (half - a) / 0.5).toFixed(3) : "1";
      el.style.pointerEvents = a > half - 0.5 ? "none" : "";
    });
    const idx = ring(Math.round(state.p));
    if (idx !== shown) {
      const first = shown === -1;
      shown = idx;
      arches.forEach((el, i) => el.classList.toggle("is-center", i === idx));
      caption(idx, !first);
    }
  };

  const goTo = (target) => {
    const pinned = st && section.classList.contains("is-pinned");
    const idx = pinned ? clamp(Math.round(target)) : Math.round(target);
    if (pinned) {
      const y = st.start + (idx / (n - 1)) * (st.end - st.start);
      syncing = true;
      gsap.to(state, { p: idx, duration: 0.9, ease: "expo.out", onUpdate: layout, overwrite: true });
      const lenis = getLenis();
      if (lenis) lenis.scrollTo(y, { duration: 0.9, onComplete: () => (syncing = false) });
      else {
        window.scrollTo({ top: y, behavior: "smooth" });
        setTimeout(() => (syncing = false), 900);
      }
    } else if (MOTION) {
      gsap.to(state, { p: idx, duration: 0.9, ease: "expo.out", onUpdate: layout, overwrite: true });
    } else {
      state.p = idx;
      layout();
    }
  };

  qsa("[data-arch]", section).forEach((b) => b.addEventListener("click", () => goTo(Math.round(state.p) + Number(b.dataset.arch))));
  wrap.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      goTo(Math.round(state.p) + (e.key === "ArrowRight" ? 1 : -1));
    }
  });

  // drag / swipe
  let drag = null;
  wrap.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    drag = { x: e.clientX, p: state.p, id: e.pointerId, moved: false };
    if (MOTION) gsap.killTweensOf(state);
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x;
    if (Math.abs(dx) > 4) drag.moved = true;
    const next = drag.p - dx / spacing;
    state.p = st && section.classList.contains("is-pinned") ? Math.max(-0.35, Math.min(n - 0.65, next)) : next;
    layout();
  });
  const endDrag = (e) => {
    if (!drag || (e && e.pointerId !== drag.id)) return;
    const moved = drag.moved;
    drag = null;
    if (moved) goTo(state.p);
  };
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);

  layout();
  measure();
  window.addEventListener("resize", () => {
    measure();
    layout();
  }, { passive: true });
  currencyHooks.push(() => {
    const s = BY[COLLECTION[shown]];
    if (s) qs("#arch-price").textContent = money(s.prices);
  });

  if (!MOTION) return;
  mm.add("(min-width: 961px)", () => {
    section.classList.add("is-pinned");
    state.p = 0;
    measure();
    layout();
    st = ST.create({
      trigger: section,
      start: "top top",
      end: () => `+=${(n - 1) * window.innerHeight * 0.55}`,
      pin: true,
      scrub: 0.8,
      anticipatePin: 1,
      invalidateOnRefresh: true,
      onUpdate: (self) => {
        if (syncing || drag) return;
        state.p = self.progress * (n - 1);
        layout();
      },
    });
    return () => {
      section.classList.remove("is-pinned");
      st = null;
      state.p = Math.floor(n / 2);
      measure();
      layout();
    };
  });
  enter(qsa(".arch-frame", wrap), "fade", { step: 80 });
}

/* ---------------------------------------------------------------- made for the feed */
const STORIES = ["instagram-post-design", "reels-cover-design", "social-media-design", "linkedin-carousel-design", "youtube-thumbnail-design"].filter((s) => BY[s]);

function initStories() {
  const player = qs("#story");
  const slidesEl = qs("#story-slides");
  const barsEl = qs("#story-bars");
  const list = qs("#feed-list");
  if (!player || !slidesEl || !STORIES.length) return;
  const n = STORIES.length;
  slidesEl.innerHTML = STORIES.map((slug, i) => `<figure class="story-slide${i === 0 ? " is-active" : ""}"><img ${srcAttrs(slug, "tall", "(max-width: 900px) 70vw, 18vw")} alt="Designflow ${esc(BY[slug].name.toLowerCase())} example" ${i ? 'loading="lazy"' : ""} decoding="async"></figure>`).join("");
  barsEl.innerHTML = STORIES.map(() => "<i><span></span></i>").join("");
  list.innerHTML = STORIES.map((slug, i) => {
    const s = BY[slug];
    return `<li><button type="button" class="feed-item" data-story-go="${i}" aria-current="${i === 0}">
      <img ${srcAttrs(slug, "thumb", "4rem")} alt="" width="52" height="52" loading="lazy" decoding="async">
      <span><b>${esc(s.name)}</b><small>${esc(s.tagline)}</small></span>
      <span class="fi-price" data-fp="${esc(slug)}">${money(s.prices)}</span>
    </button></li>`;
  }).join("");

  const slides = qsa(".story-slide", slidesEl);
  const bars = qsa(".story-bars span", barsEl);
  const pauseBtn = qs("#story-pause");
  const leftImg = qs("#phone-left-img");
  const rightImg = qs("#phone-right-img");
  let i = 0;
  let userPaused = !MOTION;
  let visible = false;
  let holding = false;
  const STORY_MS = 5500;

  const paintCta = () => {
    const s = BY[STORIES[i]];
    const cta = qs("#story-cta");
    cta.textContent = `Order · ${money(s.prices)}`;
    cta.href = orderHref(s.slug);
  };

  const running = () => MOTION && visible && !userPaused && !holding;
  const syncPlayback = () => player.classList.toggle("story-paused", !running());

  function go(next) {
    i = (next + n) % n;
    const s = BY[STORIES[i]];
    slides.forEach((el, k) => el.classList.toggle("is-active", k === i));
    bars.forEach((b, k) => {
      b.classList.remove("is-running");
      b.classList.toggle("is-done", k < i || (!MOTION && k === i));
    });
    qs("#story-label").textContent = s.name;
    qs("#story-caption").textContent = `${s.tagline} ${daysLabel(s.turnaround_days)}.`;
    paintCta();
    setSrc(leftImg, STORIES[(i - 1 + n) % n], "tall", "14vw");
    setSrc(rightImg, STORIES[(i + 1) % n], "tall", "14vw");
    qsa("[data-story-go]", list).forEach((b) => b.setAttribute("aria-current", Number(b.dataset.storyGo) === i ? "true" : "false"));
    if (MOTION) {
      const bar = bars[i];
      requestAnimationFrame(() => requestAnimationFrame(() => bar.classList.add("is-running")));
    }
    syncPlayback();
  }
  barsEl.style.setProperty("--story-ms", `${STORY_MS}ms`);
  barsEl.addEventListener("animationend", (e) => {
    if (MOTION && e.target === bars[i]) go(i + 1);
  });

  const setPaused = (p) => {
    userPaused = p;
    pauseBtn.innerHTML = icon(p ? "play" : "pause", "icon-sm");
    pauseBtn.setAttribute("aria-label", p ? "Play stories" : "Pause stories");
    syncPlayback();
  };

  pauseBtn.addEventListener("click", () => setPaused(!userPaused));
  list.addEventListener("click", (e) => {
    const b = e.target.closest("[data-story-go]");
    if (b) go(Number(b.dataset.storyGo));
  });

  // tap left/right, hold to pause, swipe
  let press = null;
  player.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".story-cta, .story-pause")) return;
    press = { x: e.clientX, t: performance.now() };
    holding = true;
    syncPlayback();
  });
  const release = (e) => {
    if (!press) return;
    const dx = e.clientX - press.x;
    const held = performance.now() - press.t;
    press = null;
    holding = false;
    if (Math.abs(dx) > 40) {
      go(i + (dx < 0 ? 1 : -1));
      player.dataset.swallow = "1";
    } else if (held > 260) {
      player.dataset.swallow = "1";
    }
    syncPlayback();
  };
  player.addEventListener("pointerup", release);
  player.addEventListener("pointercancel", () => {
    press = null;
    holding = false;
    syncPlayback();
  });
  qsa("[data-story]", player).forEach((b) =>
    b.addEventListener("click", () => {
      if (player.dataset.swallow) {
        delete player.dataset.swallow;
        return;
      }
      go(i + Number(b.dataset.story));
    })
  );
  player.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") go(i + 1);
    else if (e.key === "ArrowLeft") go(i - 1);
  });

  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    syncPlayback();
  }, { threshold: 0.35 }).observe(player);

  currencyHooks.push(() => {
    paintCta();
    qsa("[data-fp]", list).forEach((el) => (el.textContent = money(BY[el.dataset.fp].prices)));
  });
  if (!MOTION) pauseBtn.hidden = true;
  go(0);

  if (MOTION) {
    gsap.fromTo(".phone-left", { xPercent: -30, rotation: -3 }, { xPercent: -46, rotation: -7, ease: "none", scrollTrigger: { trigger: "#feed", start: "top bottom", end: "center center", scrub: 1 } });
    gsap.fromTo(".phone-right", { xPercent: 30, rotation: 3 }, { xPercent: 46, rotation: 7, ease: "none", scrollTrigger: { trigger: "#feed", start: "top bottom", end: "center center", scrub: 1 } });
    gsap.fromTo(".phone-main", { y: 80 }, { y: -20, ease: "none", scrollTrigger: { trigger: "#feed", start: "top bottom", end: "bottom top", scrub: 1.2 } });
  }
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
          <img ${srcAttrs(s.slug, "thumb", "2.5rem")} alt="" width="40" height="40" loading="lazy" decoding="async">
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
    setSrc(qs("#showcase-btn-thumb"), s.slug, "thumb", "2.5rem");
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
  const cover = qs("#showcase-cover");
  const media = qs("#showcase-media");
  if (!img || !media) return;
  let current = BY["logo-design"] ? "logo-design" : SERVICES[0].slug;
  let onPick = () => {};
  const picker = initPicker({ initial: current, onChange: (v) => onPick(v) });
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
    const wide = WIDE.has(slug);
    media.classList.toggle("is-wide", wide);
    setSrc(img, slug, wide ? "main" : "tall", "(max-width: 900px) 90vw, 36vw");
    img.alt = `Designflow ${BY[slug].name.toLowerCase()} example`;
  };
  paintText();
  setImage(current);
  currencyHooks.push(paintText);

  let swapping = null;
  onPick = (value) => {
    current = value;
    paintText();
    if (!MOTION) {
      setImage(current);
      return;
    }
    gsap.fromTo([qs("#showcase-name"), qs("#showcase-tag"), qs("#showcase-price")], { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, ease: "expo.out", stagger: 0.05 });
    if (swapping) swapping.kill();
    media.classList.add("is-waving");
    swapping = gsap.timeline({ onComplete: () => media.classList.remove("is-waving") });
    swapping
      .to(cover, { yPercent: 0, duration: 0.55, ease: "power3.inOut" })
      .add(() => {
        setImage(current);
        return img.decode ? img.decode().catch(() => {}) : null;
      })
      .to(cover, { yPercent: 104, duration: 1, ease: "expo.out" }, "+=0.08")
      .fromTo(img, { scale: 1.12 }, { scale: 1, duration: 1.4, ease: "expo.out" }, "<");
  };

  if (!MOTION) {
    cover.style.display = "none";
    return;
  }
  // The wave curtain plays once, start to finish, when the image comes into view (never left half-way).
  gsap.set(cover, { yPercent: 0 });
  gsap.set(img, { scale: 1.14 });
  ST.create({
    trigger: media,
    start: "top 78%",
    once: true,
    onEnter: () => {
      media.classList.add("is-waving");
      gsap.timeline({ onComplete: () => media.classList.remove("is-waving") })
        .to(cover, { yPercent: 104, duration: 1.6, ease: "expo.inOut" }, 0)
        .to(img, { scale: 1, duration: 2.2, ease: "expo.out" }, 0.15);
    },
  });
  gsap.fromTo(media, { y: 40 }, { y: -40, ease: "none", scrollTrigger: { trigger: media, start: "top bottom", end: "bottom top", scrub: 1.2 } });
}

/* ---------------------------------------------------------------- generic reveals + hero */
function initReveals() {
  const heads = qsa("[data-split]").filter((el) => el.dataset.split !== "hero");
  if (SF_MOTION) heads.forEach((h) => splitWords(h));
  enter(heads, "words", { step: 0 });
  enter(qsa("[data-reveal]"), "rise", { step: 80 });
}

function initHero() {
  // the intro (zoom, words, items, nav) is pure CSS from the first paint; only scroll-linked parallax here
  const hero = qs(".sf-hero");
  if (!hero || !MOTION) return;
  const media = qs("[data-hero-media]", hero);
  gsap.to(media, {
    yPercent: 12,
    ease: "none",
    scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
  });
  gsap.fromTo(qs(".sf-hero-zoom img", hero), { scale: 1.06 }, {
    scale: 1.16,
    ease: "none",
    scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
  });
  gsap.to("[data-hero-inner]", {
    yPercent: -14,
    opacity: 0.2,
    ease: "none",
    scrollTrigger: { trigger: hero, start: "top top", end: "bottom 25%", scrub: true },
  });
}

/* ---------------------------------------------------------------- smoothness */
function pauseOffscreenLoops() {
  const io = new IntersectionObserver((entries) => entries.forEach((e) => e.target.classList.toggle("is-offscreen", !e.isIntersecting)));
  qsa(".sf-hero, .sf-marquee, .sf-build").forEach((el) => io.observe(el));
}

function warmImages() {
  // Fetch + decode every below-the-fold image while the browser is idle, a few at a time,
  // so nothing has to decode in the middle of a scroll.
  const imgs = qsa("main img[loading='lazy'], .sf-sheet img, .rack-focus img");
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

/* ---------------------------------------------------------------- boot */
function boot() {
  const mm = MOTION ? gsap.matchMedia() : { add: () => {} };
  initMarquee();
  initPriceSpans();
  initHero();
  initLooks();
  initFormats(mm);
  initRack();
  initBuild(mm);
  initArches(mm);
  initStories();
  initShowcase();
  initReveals();
  onCurrency(() => currencyHooks.forEach((fn) => fn()));
  pauseOffscreenLoops();
  if (document.readyState === "complete") warmImages();
  else window.addEventListener("load", warmImages, { once: true });
  if (MOTION) {
    window.addEventListener("load", () => ST.refresh(), { once: true });
    reduceMQ.addEventListener("change", () => window.location.reload());
  }
}

boot();
