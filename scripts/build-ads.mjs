/**
 * Snapshot ads/ businesses into public/ads-data.json and copy assets to
 * public/ads-content/<slug>/ for static GitHub Pages builds.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const adsDir = path.join(root, "ads");
const publicDir = path.join(root, "public");
const outJson = path.join(publicDir, "ads-data.json");
const contentOut = path.join(publicDir, "ads-content");

const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/;

function unquote(val) {
  const v = val.trim();
  if (
    (v.startsWith('"') && v.endsWith('"')) ||
    (v.startsWith("'") && v.endsWith("'"))
  ) {
    return v.slice(1, -1);
  }
  return v;
}

function parseSimpleYaml(text) {
  const data = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes(":")) continue;
    const idx = line.indexOf(":");
    const key = line.slice(0, idx).trim();
    let val = line.slice(idx + 1).trim();
    if (!key) continue;
    if (val.startsWith("[") && val.endsWith("]")) {
      const inner = val.slice(1, -1).trim();
      data[key] = inner
        ? inner.split(",").map((p) => unquote(p.trim()))
        : [];
      continue;
    }
    if (val.toLowerCase() === "true" || val.toLowerCase() === "false") {
      data[key] = val.toLowerCase() === "true";
      continue;
    }
    if (/^-?\d+(\.\d+)?$/.test(val)) {
      data[key] = Number(val);
      continue;
    }
    data[key] = unquote(val);
  }
  return data;
}

function parseBusiness(mdPath, slug) {
  const raw = fs.readFileSync(mdPath, "utf8");
  const m = raw.match(FRONTMATTER_RE);
  let meta = {};
  let body = raw.trim();
  if (m) {
    meta = parseSimpleYaml(m[1]);
    body = m[2].trim();
  }
  return {
    slug,
    name: meta.name || slug,
    tagline: meta.tagline || "",
    phone: meta.phone || "",
    email: meta.email || "",
    website: meta.website || "",
    address: meta.address || "",
    hours: meta.hours || "",
    category: meta.category || "Sponsored",
    cta: meta.cta || "Learn more",
    logo: meta.logo || "",
    image: meta.image || meta.hero || "",
    weight: Number(meta.weight) > 0 ? Number(meta.weight) : 1,
    active: meta.active !== false,
    bio: body,
  };
}

function copyDir(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  fs.mkdirSync(publicDir, { recursive: true });
  if (fs.existsSync(contentOut)) {
    fs.rmSync(contentOut, { recursive: true, force: true });
  }
  fs.mkdirSync(contentOut, { recursive: true });

  const ads = [];
  if (fs.existsSync(adsDir)) {
    for (const name of fs.readdirSync(adsDir).sort()) {
      const folder = path.join(adsDir, name);
      if (!fs.statSync(folder).isDirectory() || name.startsWith(".")) continue;
      const md = path.join(folder, "business.md");
      if (!fs.existsSync(md)) continue;
      const biz = parseBusiness(md, name);
      if (!biz.active) continue;
      ads.push(biz);
      const assets = path.join(folder, "assets");
      if (fs.existsSync(assets)) {
        copyDir(assets, path.join(contentOut, name, "assets"));
      }
    }
  }

  ads.sort((a, b) => a.name.localeCompare(b.name));
  fs.writeFileSync(
    outJson,
    JSON.stringify({ generatedAt: new Date().toISOString(), ads }, null, 2)
  );
  console.log(`Wrote ${ads.length} ads → ${path.relative(root, outJson)}`);
}

main();
