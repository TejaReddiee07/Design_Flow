/* Format mockups: every service is shown the way it is actually used - a reel cover on a phone,
   a thumbnail in a video player, a banner in a browser, a deck as slides, a flyer as paper...
   Pure markup + CSS (prism.css, "format mockups"); sized in container units so one design fits
   the catalogue cards and the larger service-page hero.
   The same markup is produced for the static pages by backend/scripts/generate_service_pages.py
   (mockup()) - keep the two in step. */

const I = "/assets/img/showcase/";
const V = "?v=2"; // bump when the showcase images are re-rendered
// exact pixel widths of the "main" renders (each one is already in the service's native format)
export const MAIN_W = {
  "ad-creative-design": 960, "brochure-design": 1200, "business-card-design": 1200, "company-profile-design": 855,
  "custom-design-requests": 1200, "ecommerce-creative-design": 1200, "flyer-design": 856, "infographic-design": 600,
  "instagram-post-design": 960, "linkedin-carousel-design": 960, "logo-design": 1200, "pitch-deck-design": 1200,
  "poster-design": 675, "presentation-design": 1200, "product-advertisement-design": 960, "reels-cover-design": 675,
  "social-media-design": 960, "website-banner-design": 1200, "youtube-thumbnail-design": 1200,
};

export const FORMAT = {
  "logo-design": "artboard",
  "social-media-design": "trio",
  "instagram-post-design": "post",
  "linkedin-carousel-design": "carousel",
  "youtube-thumbnail-design": "video",
  "ad-creative-design": "ad",
  "website-banner-design": "browser",
  "pitch-deck-design": "deck",
  "presentation-design": "monitor",
  "brochure-design": "trifold",
  "flyer-design": "paper",
  "poster-design": "poster",
  "infographic-design": "scroll",
  "reels-cover-design": "reel",
  "ecommerce-creative-design": "shop",
  "product-advertisement-design": "story",
  "business-card-design": "proof",
  "company-profile-design": "booklet",
  "custom-design-requests": "select",
};

function img(slug, kind, sizes, alt = "") {
  let src;
  let set;
  if (kind === "tall") {
    src = `${I}${slug}-tall.webp${V}`;
    set = `${I}${slug}-tall-sm.webp${V} 480w, ${src} 960w`;
  } else if (kind === "thumb") {
    src = `${I}${slug}-thumb.webp${V}`;
    set = `${I}${slug}-thumb-sm.webp${V} 240w, ${src} 480w`;
  } else {
    const w = MAIN_W[slug] || 1200;
    src = `${I}${slug}.webp${V}`;
    set = w > 600 ? `${I}${slug}-sm.webp${V} 600w, ${src} ${w}w` : `${src} ${w}w`;
  }
  return `<img src="${src}" srcset="${set}" sizes="${sizes}" alt="${alt}" loading="lazy" decoding="async">`;
}
const ic = (n) => `<svg class="mk-ic" aria-hidden="true"><use href="/assets/img/icons.svg#${n}"></use></svg>`;
const line = (w) => `<i class="mk-line" style="--w:${w}%"></i>`;
const head = (sponsored) =>
  `<span class="mk-head"><i class="mk-avatar"></i><span class="mk-lines"><b>designflow</b>${sponsored ? "<small>Sponsored</small>" : line(46)}</span>${ic("more")}</span>`;
const actions = `<span class="mk-actions">${ic("heart")}${ic("message")}${ic("send")}</span>`;

/* `size` is the rendered width of the whole mockup area (a CSS length for the sizes attribute). */
export function mockup(slug, { size = "max(18rem, 15vw)", alt = "" } = {}) {
  const type = FORMAT[slug] || "artboard";
  const m = (s = size) => img(slug, "main", s, alt);
  let html;
  switch (type) {
    case "post":
      html = `<span class="mk mk-post">${head(false)}<span class="mk-media r45">${m()}</span>${actions}${line(72)}</span>`;
      break;
    case "ad":
      html = `<span class="mk mk-post is-ad">${head(true)}<span class="mk-media r45">${m()}</span><span class="mk-cta">Learn more ${ic("chevron-right")}</span>${actions}</span>`;
      break;
    case "trio":
      html = `<span class="mk mk-trio"><span class="mk-tile t-story">${img(slug, "tall", size, alt)}<small>Story</small></span><span class="mk-tile t-post">${m()}<small>Post</small></span><span class="mk-tile t-square">${img(slug, "thumb", size)}<small>Square</small></span></span>`;
      break;
    case "reel":
      html = `<span class="mk mk-phone"><span class="mk-screen">${m()}<span class="mk-bars"><i></i><i></i><i></i></span><span class="mk-side">${ic("heart")}${ic("message")}${ic("send")}</span><span class="mk-cap">${line(58)}${line(36)}</span></span></span>`;
      break;
    case "story":
      html = `<span class="mk mk-phone"><span class="mk-screen">${img(slug, "tall", size, alt)}<span class="mk-bars"><i></i><i></i></span><span class="mk-chip">Sponsored</span><span class="mk-shop-now">Shop now</span></span></span>`;
      break;
    case "carousel":
      html = `<span class="mk mk-carousel"><span class="mk-slide is-next">${m()}</span><span class="mk-slide">${m()}</span><span class="mk-arrow">${ic("chevron-right")}</span><span class="mk-dots"><i class="on"></i><i></i><i></i><i></i></span></span>`;
      break;
    case "video":
      html = `<span class="mk mk-video"><span class="mk-player">${m()}<span class="mk-play">${ic("play")}</span><span class="mk-progress"><i></i></span></span><span class="mk-vmeta"><i class="mk-avatar"></i><span class="mk-lines">${line(92)}${line(56)}</span></span></span>`;
      break;
    case "browser":
      html = `<span class="mk mk-browser"><span class="mk-chrome"><i></i><i></i><i></i><b></b></span><span class="mk-page"><span class="mk-banner">${m()}</span><span class="mk-blocks"><i></i><i></i><i></i></span>${line(82)}${line(60)}</span></span>`;
      break;
    case "deck":
      html = `<span class="mk mk-deck"><span class="mk-sheet b2"></span><span class="mk-sheet b1"></span><span class="mk-sheet front">${m()}</span><span class="mk-dots"><i class="on"></i><i></i><i></i><i></i></span></span>`;
      break;
    case "monitor":
      html = `<span class="mk mk-monitor"><span class="mk-display">${m()}</span><i class="mk-neck"></i><i class="mk-base"></i></span>`;
      break;
    case "trifold":
      html = `<span class="mk mk-trifold"><span class="mk-panel l">${m()}</span><span class="mk-panel c">${m()}</span><span class="mk-panel r">${m()}</span></span>`;
      break;
    case "paper":
      html = `<span class="mk mk-paper"><span class="mk-sheet back"></span><span class="mk-sheet front">${m()}</span></span>`;
      break;
    case "poster":
      html = `<span class="mk mk-poster">${m()}<i class="mk-tape l"></i><i class="mk-tape r"></i></span>`;
      break;
    case "scroll":
      html = `<span class="mk mk-scroll"><span class="mk-view">${m()}</span><i class="mk-track"><i></i></i></span>`;
      break;
    case "shop":
      html = `<span class="mk mk-shop"><span class="mk-media r11">${m()}</span><span class="mk-lines">${line(84)}${line(48)}</span><span class="mk-buy">Add to cart</span></span>`;
      break;
    case "proof":
      html = `<span class="mk mk-proof"><span class="mk-art">${m()}</span><i class="mk-cm tl"></i><i class="mk-cm tr"></i><i class="mk-cm bl"></i><i class="mk-cm br"></i><span class="mk-note">Print-ready PDF</span></span>`;
      break;
    case "booklet":
      html = `<span class="mk mk-booklet"><i class="mk-pg p3"></i><i class="mk-pg p2"></i><span class="mk-pg front">${m()}</span></span>`;
      break;
    case "select":
      html = `<span class="mk mk-select"><span class="mk-board">${m()}<i class="mk-sel"></i><i class="mk-h tl"></i><i class="mk-h tr"></i><i class="mk-h bl"></i><i class="mk-h br"></i><span class="mk-size">1200 × 675</span></span><svg class="mk-cursor" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3l14 8-6.2 1.6L10 19z"/></svg></span>`;
      break;
    default: // artboard
      html = `<span class="mk mk-artboard"><span class="mk-label">Logo directions</span><span class="mk-board">${m()}</span></span>`;
  }
  return { type, html };
}
