/**
 * Sponsored satirical business ads.
 * Dev: /api/ads · Prod: /ads-data.json + /ads-content/<slug>/...
 */

const cache = { list: null };

function resolveAdAsset(slug, rel) {
  if (!rel) return "";
  if (/^https?:\/\//i.test(rel)) return rel;
  let clean = String(rel).replace(/^\.\//, "").replace(/^\/+/, "");
  if (!clean.includes("/")) clean = `assets/${clean}`;
  return `/ads-content/${slug}/${clean}`;
}

export function adImageSrc(ad) {
  if (!ad) return "";
  return resolveAdAsset(ad.slug, ad.image || ad.logo);
}

export function adLogoSrc(ad) {
  if (!ad) return "";
  return resolveAdAsset(ad.slug, ad.logo || ad.image);
}

async function loadStaticAds() {
  try {
    const res = await fetch("/ads-data.json", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.ads || [];
  } catch {
    return null;
  }
}

export async function fetchAds() {
  if (cache.list) return cache.list;

  try {
    const res = await fetch("/api/ads", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      cache.list = (data.ads || []).filter((a) => a.active !== false);
      return cache.list;
    }
  } catch {
    /* fall through */
  }

  const staticList = await loadStaticAds();
  cache.list = (staticList || []).filter((a) => a.active !== false);
  return cache.list;
}

/** Weighted pick for rotation (weight defaults to 1). */
export function pickWeightedAd(ads, excludeSlug = null) {
  const pool = (ads || []).filter(
    (a) => a && a.active !== false && a.slug !== excludeSlug
  );
  if (!pool.length) {
    const all = (ads || []).filter((a) => a && a.active !== false);
    if (!all.length) return null;
    return all[Math.floor(Math.random() * all.length)];
  }
  const total = pool.reduce((s, a) => s + (Number(a.weight) > 0 ? Number(a.weight) : 1), 0);
  let r = Math.random() * total;
  for (const a of pool) {
    r -= Number(a.weight) > 0 ? Number(a.weight) : 1;
    if (r <= 0) return a;
  }
  return pool[pool.length - 1];
}

export function clearAdsCache() {
  cache.list = null;
}
