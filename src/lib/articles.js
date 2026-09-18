/**
 * Article data access.
 * App stack: Flask /api (Mongo).
 * Legacy preview: Python folder API or static public/articles-data.json.
 */

import { heroMediaUrl, resolveMediaUrl } from "./media.js";

const cache = {
  list: null,
  bySlug: new Map(),
};

/**
 * Resolve any article-relative or content path to a browser-fetchable URL.
 *
 * Preferred (app stack): article.media[] name → full CDN/Spaces URL
 * Fallback (legacy): /content/<slug>/assets/...
 */
export function resolveContentUrl(slug, path, article = null) {
  if (!path) return "";
  const raw = String(path).trim();
  if (!raw) return "";

  if (/^https?:\/\//i.test(raw) || raw.startsWith("data:")) {
    return raw;
  }

  const ctx = article && article.slug === slug ? article : article || { slug, media: [] };
  if (ctx?.media?.length) {
    const viaMedia = resolveMediaUrl(ctx, raw);
    if (viaMedia && (/^https?:\/\//i.test(viaMedia) || viaMedia !== raw)) {
      return viaMedia;
    }
  }

  // Already a /content/... or content/... URL — normalize + fix wrong slug if needed
  const contentMatch = raw.match(/^(?:\/)?content\/([^/]+)\/(.+)$/);
  if (contentMatch) {
    const filePart = contentMatch[2].replace(/^\/+/, "");
    return `/content/${slug}/${filePart}`;
  }

  let rel = raw.replace(/^\.\//, "").replace(/^\/+/, "");

  const articlesPrefix = rel.match(/^articles\/[^/]+\/(.+)$/);
  if (articlesPrefix) {
    rel = articlesPrefix[1];
  }

  if (!rel.includes("/")) {
    rel = `assets/${rel}`;
  }

  return `/content/${slug}/${rel}`;
}

export function heroSrc(article) {
  if (!article) return "";
  const fromMedia = heroMediaUrl(article);
  if (fromMedia) return fromMedia;
  if (!article.hero) return "";
  return resolveContentUrl(article.slug, article.hero, article);
}

export function inlineImageSrc(article, src) {
  return resolveContentUrl(article.slug, src, article);
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

/** Query flag that unlocks unpublished stories for anyone who has the URL. */
export const ARTICLE_PREVIEW_PARAM = "_agentnewspreview";

export function isArticlePreviewSearch(search) {
  const q = new URLSearchParams(search || (typeof window !== "undefined" ? window.location.search : ""));
  return q.get(ARTICLE_PREVIEW_PARAM) === "1";
}

export async function fetchArticle(slug, { preview = false } = {}) {
  if (!preview && cache.bySlug.has(slug)) return cache.bySlug.get(slug);

  try {
    const qs = preview ? `?${ARTICLE_PREVIEW_PARAM}=1` : "";
    const res = await fetch(`/api/articles/${encodeURIComponent(slug)}${qs}`, {
      cache: "no-store",
    });
    if (res.ok) {
      const article = await res.json();
      if (!preview) cache.bySlug.set(slug, article);
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
