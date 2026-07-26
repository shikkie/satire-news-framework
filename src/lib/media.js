/**
 * Resolve markdown / hero media references using article.media[].
 *
 * Markdown may use:
 *   assets/hero.jpg
 *   hero.jpg
 *   hero          (media name)
 *   https://...
 *
 * DB stores media: [{ type, name, url, key }]
 */

export function resolveMediaUrl(article, ref) {
  if (!ref) return "";
  const raw = String(ref).trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("data:")) return raw;

  const media = article?.media || [];
  let clean = raw.replace(/^\.\//, "").replace(/^\/+/, "");
  if (clean.startsWith("assets/")) clean = clean.slice("assets/".length);
  const base = clean.includes("/") ? clean.split("/").pop() : clean;
  const stem = base.includes(".") ? base.replace(/\.[^.]+$/, "") : base;

  for (const m of media) {
    const name = m.name || "";
    const key = m.key || "";
    const url = m.url || "";
    const filename = m.filename || "";
    if (
      name === clean ||
      name === stem ||
      name === base ||
      filename === base ||
      filename === clean ||
      key.endsWith(`/${base}`) ||
      key.endsWith(`/${stem}`) ||
      (url && url.endsWith(`/${base}`))
    ) {
      return url || raw;
    }
  }

  // Legacy filesystem preview paths
  if (article?.slug) {
    if (!clean.includes("/")) clean = `assets/${clean}`;
    return `/content/${article.slug}/${clean}`;
  }
  return raw;
}

export function heroMediaUrl(article) {
  if (!article) return "";
  const hero = article.hero || "";
  if (/^https?:\/\//i.test(hero)) return hero;
  if (hero) return resolveMediaUrl(article, hero);
  // first image in media
  const img = (article.media || []).find((m) => m.type === "image" && m.url);
  return img?.url || "";
}
