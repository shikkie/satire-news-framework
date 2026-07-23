/**
 * Article data access.
 * Dev: fetch from Python preview API (/api/...).
 * Prod / offline: fall back to static public/articles-data.json snapshot.
 */

const cache = {
  list: null,
  bySlug: new Map(),
};

/**
 * Resolve any article-relative or content path to a browser-fetchable URL.
 *
 * Accepted inputs:
 *   assets/hero.jpg
 *   ./assets/hero.jpg
 *   /content/<slug>/assets/hero.jpg
 *   content/<slug>/assets/hero.jpg
 *   https://...
 *
 * Output always targets the preview proxy / static content tree:
 *   /content/<slug>/assets/hero.jpg  (absolute from site root — works with Vite proxy)
 */
export function resolveContentUrl(slug, path) {
  if (!path) return "";
  const raw = String(path).trim();
  if (!raw) return "";

  if (/^https?:\/\//i.test(raw) || raw.startsWith("data:")) {
    return raw;
  }

  // Already a /content/... or content/... URL — normalize + fix wrong slug if needed
  const contentMatch = raw.match(/^(?:\/)?content\/([^/]+)\/(.+)$/);
  if (contentMatch) {
    const filePart = contentMatch[2].replace(/^\/+/, "");
    // Prefer the article's real slug (agents sometimes typo the path)
    return `/content/${slug}/${filePart}`;
  }

  // Strip leading ./ and /
  let rel = raw.replace(/^\.\//, "").replace(/^\/+/, "");

  // If someone wrote articles/<slug>/assets/... strip the prefix
  const articlesPrefix = rel.match(/^articles\/[^/]+\/(.+)$/);
  if (articlesPrefix) {
    rel = articlesPrefix[1];
  }

  // Bare filename → assume assets/
  if (!rel.includes("/")) {
    rel = `assets/${rel}`;
  }

  return `/content/${slug}/${rel}`;
}

export function heroSrc(article) {
  if (!article?.hero) return "";
  return resolveContentUrl(article.slug, article.hero);
}

export function inlineImageSrc(article, src) {
  return resolveContentUrl(article.slug, src);
}

const VIDEO_EXT = /\.(mp4|webm|ogg|mov)(\?.*)?$/i;

/** True if path/URL looks like a video asset */
export function isVideoSrc(src) {
  if (!src) return false;
  return VIDEO_EXT.test(String(src).trim());
}

async function loadStaticBundle() {
  try {
    // Absolute path — article URLs live under /article/<slug>/
    const res = await fetch("/articles-data.json", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.articles || [];
  } catch {
    return null;
  }
}

export async function fetchArticles() {
  if (cache.list) return cache.list;

  try {
    const res = await fetch("/api/articles", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      cache.list = data.articles || [];
      return cache.list;
    }
  } catch {
    /* fall through */
  }

  const staticList = await loadStaticBundle();
  cache.list = staticList || [];
  return cache.list;
}

export async function fetchArticle(slug) {
  if (cache.bySlug.has(slug)) return cache.bySlug.get(slug);

  try {
    const res = await fetch(`/api/articles/${encodeURIComponent(slug)}`, {
      cache: "no-store",
    });
    if (res.ok) {
      const article = await res.json();
      cache.bySlug.set(slug, article);
      return article;
    }
  } catch {
    /* fall through */
  }

  const list = await loadStaticBundle();
  const found = (list || []).find((a) => a.slug === slug) || null;
  if (found) cache.bySlug.set(slug, found);
  return found;
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** Bust SPA list cache after new articles appear (dev convenience). */
export function clearArticleCache() {
  cache.list = null;
  cache.bySlug.clear();
}
