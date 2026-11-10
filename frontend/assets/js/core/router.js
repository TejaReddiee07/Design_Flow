/* Tiny hash router: routes like "/requests/:id". */

export function createRouter({ routes, outlet, notFound, onNavigate }) {
  const compiled = routes.map((r) => {
    const keys = [];
    const pattern = r.path
      .replace(/\/+$/, "")
      .replace(/:([a-zA-Z_]+)/g, (_, k) => {
        keys.push(k);
        return "([^/]+)";
      });
    return { ...r, keys, regex: new RegExp(`^${pattern || "/"}$`) };
  });

  let current = null;
  let cleanup = null;

  function parse() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const [pathPart, queryPart = ""] = raw.split("?");
    const path = pathPart.replace(/\/+$/, "") || "/";
    const query = {};
    new URLSearchParams(queryPart).forEach((v, k) => (query[k] = v));
    return { path, query };
  }

  async function resolve() {
    const { path, query } = parse();
    let match = null;
    let params = {};
    for (const r of compiled) {
      const m = path.match(r.regex);
      if (m) {
        match = r;
        r.keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
        break;
      }
    }
    if (typeof cleanup === "function") {
      try {
        cleanup();
      } catch {}
      cleanup = null;
    }
    current = { path, query, params, route: match };
    if (onNavigate) onNavigate(current);
    outlet.scrollTop = 0;
    window.scrollTo({ top: 0 });
    if (!match) {
      outlet.innerHTML = "";
      if (notFound) await notFound(outlet, current);
      return;
    }
    outlet.innerHTML = "";
    const page = document.createElement("div");
    page.className = "page";
    outlet.appendChild(page);
    try {
      const result = await match.render(page, params, query, current);
      if (typeof result === "function") cleanup = result;
    } catch (err) {
      console.error(err);
      page.innerHTML = `<div class="empty"><h4>Something went wrong</h4><p>${(err && err.message) || err}</p></div>`;
    }
  }

  window.addEventListener("hashchange", resolve);

  return {
    start: resolve,
    navigate(path) {
      if (location.hash.replace(/^#/, "") === path) resolve();
      else location.hash = path;
    },
    get current() {
      return current;
    },
    refresh: resolve,
  };
}

export function link(path, label, cls = "") {
  return `<a href="#${path}" class="${cls}">${label}</a>`;
}
