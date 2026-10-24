// The page's URLs (issue #184). Every view has a path of its own, so a shared
// link opens straight into it; scripts/serve_dashboard.py answers these paths
// with the page (ROUTE_PATHS / ROUTE_PREFIXES there must list the same).

//: View button id -> path, slugs from the UI's own labels.
const VIEW_PATHS = {
  aggBtn: "/suvestine",
  nominatorBtn: "/iskelejai",
  coverageBtn: "/apreptis",
  moversBtn: "/pokyciai",
};

const PERSON_PREFIX = "/asmuo/";
const COMPARE_PREFIX = "/palyginti/";

//: "Birutė VĖSAITĖ" -> "birute-vesaite". Decoration only: a person resolves
//: by pid, and a wrong or missing slug is rewritten to this one.
function nameSlug(name) {
  return (name || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function personPath(p) {
  const slug = nameSlug(p.n);
  return `${PERSON_PREFIX}${slug ? `${slug}-` : ""}${encodeURIComponent(p.pid)}`;
}

function comparePath(pids) {
  return COMPARE_PREFIX + pids.map(encodeURIComponent).join(",");
}

//: What a path names: { view: "front" | "person" | "compare" | <button id> |
//: "unknown", key }. A trailing slash is tolerated.
function parsePath(pathname) {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (path === "/" || path === "/index.html") return { view: "front" };
  for (const [view, viewPath] of Object.entries(VIEW_PATHS)) {
    if (path === viewPath) return { view };
  }
  const decode = (s) => { try { return decodeURIComponent(s); } catch { return s; } };
  if (path.startsWith(PERSON_PREFIX)) return { view: "person", key: decode(path.slice(PERSON_PREFIX.length)) };
  if (path.startsWith(COMPARE_PREFIX)) {
    return { view: "compare", key: path.slice(COMPARE_PREFIX.length).split(",").filter(Boolean).map(decode) };
  }
  return { view: "unknown", key: decode(path) };
}

//: The person a `/asmuo/` segment names. The pid is its tail after any slug;
//: pids are tried whole first and then after each hyphen, so it works for
//: any pid spelling, and a bare pid or legacy key (name|birth, a merged-away
//: fragment's key) resolves too.
function resolvePersonKey(segment, lookup) {
  let rest = segment;
  for (;;) {
    const hit = lookup(rest);
    if (hit) return hit;
    const cut = rest.indexOf("-");
    if (cut < 0) return null;
    rest = rest.slice(cut + 1);
  }
}

//: A plain left click on a link the router should handle in place.
function isRoutableClick(ev, a) {
  return (
    !ev.defaultPrevented && ev.button === 0 &&
    !ev.metaKey && !ev.ctrlKey && !ev.shiftKey && !ev.altKey &&
    a.origin === location.origin && !a.target && !a.hasAttribute("download") &&
    parsePath(a.pathname).view !== "unknown" &&
    // An in-page anchor (the skip link) is the browser's to follow.
    !(a.pathname === location.pathname && a.hash)
  );
}

export { VIEW_PATHS, nameSlug, personPath, comparePath, parsePath, resolvePersonKey, isRoutableClick };
