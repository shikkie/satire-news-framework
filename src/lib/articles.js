/**
 * Article data access.
 * Dev: fetch from Python preview API (/api/...).
 * Prod / offline: fall back to static public/articles-data.json snapshot.
 */

const cache = {
  list: null,
  bySlug: new Map(),
};

function contentUrl(slug, rel) {
  if (!rel) return "";
  const clean = rel.replace(/^\.?\//, "");
  return `./content/${slug}/${clean}`;
}

export function heroSrc(article) {
  if (!article?.hero) return "";
  if (article.hero.startsWith("http")) return article.hero;
  return contentUrl(article.slug, article.hero);
}

async function loadStaticBundle() {
  try {
    const res = await fetch("./articles-data.json", { cache: "no-store" });
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
