/* Marketing-page chrome: Lenis smooth scrolling (synced with GSAP ScrollTrigger),
   the scroll progress bar, the floating pill nav with its active indicator,
   smooth in-page anchors and share links. Degrades to native scrolling when the
   vendor scripts are missing or the visitor prefers reduced motion. */

const reduceMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
const expoOut = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));
let lenis = null;
let started = false;

export function getLenis() {
  return lenis;
}

export function lockScroll(lock) {
  if (lenis) lock ? lenis.stop() : lenis.start();
  document.documentElement.classList.toggle("sf-locked", lock);
}

function navOffset() {
  const pill = document.querySelector(".nav-pill");
  return pill ? pill.getBoundingClientRect().bottom + 18 : 90;
}

export function scrollToTarget(target, { immediate = false } = {}) {
  const el = typeof target === "string" ? document.querySelector(target) : target;
  if (!el) return false;
  const offset = -navOffset();
  if (lenis) {
    lenis.scrollTo(el, { offset, duration: immediate ? 0 : 1.5, easing: expoOut, immediate });
  } else {
    const y = el.getBoundingClientRect().top + window.scrollY + offset;
    window.scrollTo({ top: y, behavior: immediate || reduceMQ.matches ? "auto" : "smooth" });
  }
  return true;
}

function initLenis() {
  const gsap = window.gsap;
  const ST = window.ScrollTrigger;
  if (gsap && ST) {
    gsap.registerPlugin(ST);
    ST.config({ ignoreMobileResize: true });
  }
  if (!window.Lenis || reduceMQ.matches) return;
  lenis = new window.Lenis({
    duration: 1.2,
    easing: expoOut,
    smoothWheel: true,
    wheelMultiplier: 1,
    touchMultiplier: 1.5,
  });
  if (gsap && ST) {
    lenis.on("scroll", ST.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
  } else {
    const raf = (t) => {
      lenis.raf(t);
      requestAnimationFrame(raf);
    };
    requestAnimationFrame(raf);
  }
}

function initProgress() {
  const bar = document.querySelector(".scroll-progress span");
  if (!bar) return;
  const ST = window.ScrollTrigger;
  if (ST) {
    // ScrollTrigger caches the page length on refresh: no layout reads while scrolling
    ST.create({ start: 0, end: "max", refreshPriority: -1, onUpdate: (self) => (bar.style.transform = `scaleX(${self.progress.toFixed(4)})`) });
    return;
  }
  let queued = false;
  let max = 1;
  const measure = () => (max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight));
  const paint = () => {
    queued = false;
    bar.style.transform = `scaleX(${Math.min(1, Math.max(0, window.scrollY / max)).toFixed(4)})`;
  };
  window.addEventListener("scroll", () => {
    if (!queued) {
      queued = true;
      requestAnimationFrame(paint);
    }
  }, { passive: true });
  window.addEventListener("resize", () => {
    measure();
    paint();
  }, { passive: true });
  measure();
  paint();
}

function initNavIndicator() {
  const nav = document.querySelector(".sf .nav-links");
  const ind = nav && nav.querySelector(".nav-indicator");
  if (!nav || !ind) return;
  const links = Array.from(nav.querySelectorAll("a[data-section]"));
  let current = null;

  const place = (a) => {
    if (!a) {
      ind.style.opacity = "0";
      return;
    }
    ind.style.width = `${a.offsetWidth}px`;
    ind.style.transform = `translateX(${a.offsetLeft}px)`;
    ind.style.opacity = "1";
  };
  const setActive = (a) => {
    if (a === current) return;
    current = a;
    links.forEach((l) => {
      const on = l === a;
      l.classList.toggle("active", on);
      if (on) l.setAttribute("aria-current", "true");
      else l.removeAttribute("aria-current");
    });
    place(a);
  };

  const fixed = document.body.dataset.navActive;
  if (fixed) {
    setActive(links.find((l) => l.dataset.section === fixed) || null);
    window.addEventListener("resize", () => place(current), { passive: true });
    return;
  }

  const pairs = links
    .map((l) => ({ link: l, el: document.getElementById(l.dataset.section) }))
    .filter((p) => p.el);
  if (!pairs.length) return;
  window.addEventListener("resize", () => place(current), { passive: true });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => place(current));

  const ST = window.ScrollTrigger;
  if (ST) {
    // section boundaries come from ScrollTrigger's cache: no getBoundingClientRect per frame
    const inside = new Set();
    const pick = () => setActive(pairs.filter((p) => inside.has(p.el)).map((p) => p.link).pop() || null);
    pairs.forEach((p) =>
      ST.create({
        trigger: p.el,
        start: "top 42%",
        end: "bottom 42%",
        refreshPriority: -1,
        onToggle: (self) => {
          if (self.isActive) inside.add(p.el);
          else inside.delete(p.el);
          pick();
        },
      })
    );
    return;
  }
  let queued = false;
  const compute = () => {
    queued = false;
    const line = window.innerHeight * 0.42;
    let active = null;
    for (const p of pairs) {
      const r = p.el.getBoundingClientRect();
      if (r.top <= line && r.bottom > line) active = p.link;
    }
    setActive(active);
  };
  window.addEventListener("scroll", () => {
    if (!queued) {
      queued = true;
      requestAnimationFrame(compute);
    }
  }, { passive: true });
  compute();
}

function initAnchors() {
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest('a[href^="/#"], a[href^="#"]');
    if (!a) return;
    const href = a.getAttribute("href");
    if (href.startsWith("/#") && window.location.pathname !== "/") return;
    const id = href.slice(href.indexOf("#") + 1);
    const el = id && document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    scrollToTarget(el);
    if (history.replaceState) history.replaceState(null, "", `#${id}`);
  });

  if (window.location.hash.length > 1) {
    const id = decodeURIComponent(window.location.hash.slice(1));
    const go = () => {
      if (window.ScrollTrigger) window.ScrollTrigger.refresh();
      const el = document.getElementById(id);
      if (el) scrollToTarget(el, { immediate: true });
    };
    if (document.readyState === "complete") setTimeout(go, 150);
    else window.addEventListener("load", () => setTimeout(go, 150), { once: true });
  }
}

function initMenuLock() {
  const menu = document.getElementById("mobile-menu");
  const burger = document.querySelector("[data-burger]");
  if (!menu) return;
  new MutationObserver(() => {
    const open = menu.classList.contains("open");
    if (lenis) open ? lenis.stop() : lenis.start();
    if (burger) {
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }
  }).observe(menu, { attributes: true, attributeFilter: ["class"] });
  if (burger) burger.setAttribute("aria-expanded", "false");
}

function initShare() {
  const url = encodeURIComponent(window.location.origin + "/");
  const text = encodeURIComponent("Designflow: fixed-price design, delivered in days.");
  const map = {
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
    x: `https://x.com/intent/post?url=${url}&text=${text}`,
    whatsapp: `https://wa.me/?text=${text}%20${url}`,
    email: `mailto:?subject=${text}&body=${url}`,
  };
  document.querySelectorAll("[data-share]").forEach((a) => {
    const href = map[a.dataset.share];
    if (href) a.href = href;
  });
}

function initLayoutRefresh() {
  let t;
  const refresh = () => {
    clearTimeout(t);
    t = setTimeout(() => {
      if (window.ScrollTrigger) window.ScrollTrigger.refresh();
      if (lenis) lenis.resize();
    }, 80);
  };
  document.addEventListener("df:layout", refresh);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(refresh);
  window.addEventListener("load", refresh, { once: true });
}

export function initChrome() {
  if (started || !document.body.classList.contains("sf")) return;
  started = true;
  initLenis();
  initProgress();
  initNavIndicator();
  initAnchors();
  initMenuLock();
  initShare();
  initLayoutRefresh();
}
