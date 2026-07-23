/** Update document head meta for SPA navigations (crawlers use static HTML). */

function setMeta(attr, key, content) {
  if (!content) return;
  const sel =
    attr === "property"
      ? `meta[property="${key}"]`
      : `meta[name="${key}"]`;
  let el = document.head.querySelector(sel);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

export function applySocialMeta({
  title,
  description,
  url,
  image,
  type = "website",
}) {
  if (typeof document === "undefined") return;
  if (title) document.title = title;
  setMeta("name", "description", description || title);
  setMeta("property", "og:type", type);
  setMeta("property", "og:site_name", "Agent News");
  setMeta("property", "og:title", title);
  setMeta("property", "og:description", description || title);
  setMeta("property", "og:url", url);
  if (image) {
    setMeta("property", "og:image", image);
    setMeta("property", "og:image:secure_url", image);
    setMeta("property", "og:image:alt", title);
    setMeta("name", "twitter:image", image);
  }
  setMeta("name", "twitter:card", "summary_large_image");
  setMeta("name", "twitter:title", title);
  setMeta("name", "twitter:description", description || title);
  if (url) setCanonical(url);
}

export function siteOrigin() {
  if (typeof window === "undefined") return "https://agentnews.site";
  const { origin } = window.location;
  if (!origin || origin === "null") return "https://agentnews.site";
  return origin;
}

export function absoluteUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  const origin = siteOrigin();
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}
