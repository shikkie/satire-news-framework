/**
 * Snapshot articles/ into public/articles-data.json for static GitHub Pages builds.
 * Also copies article assets into public/content/<slug>/.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const articlesDir = path.join(root, "articles");
const publicDir = path.join(root, "public");
const outJson = path.join(publicDir, "articles-data.json");
const contentOut = path.join(publicDir, "content");

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
    data[key] = unquote(val);
  }
  return data;
}

function parseArticle(mdPath, slug) {
  const raw = fs.readFileSync(mdPath, "utf8");
  const m = raw.match(FRONTMATTER_RE);
  let meta = {};
  let body = raw.trim();
  if (m) {
    meta = parseSimpleYaml(m[1]);
    body = m[2].trim();
  } else if (!meta.title) {
    const first = body.split("\n")[0]?.replace(/^#\s*/, "").trim();
    meta.title = first || slug;
  }
  return {
    slug,
    title: meta.title || slug,
    dek: meta.dek || "",
    author: meta.author || "Staff",
    date: meta.date || "",
    section: meta.section || "News",
    hero: meta.hero || "",
    tags: meta.tags || [],
    disclaimer: meta.disclaimer !== false,
    body,
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

  const articles = [];
  if (fs.existsSync(articlesDir)) {
    for (const name of fs.readdirSync(articlesDir).sort()) {
      const folder = path.join(articlesDir, name);
      if (!fs.statSync(folder).isDirectory() || name.startsWith(".")) continue;
      const md = path.join(folder, "article.md");
      if (!fs.existsSync(md)) continue;
      articles.push(parseArticle(md, name));
      const assets = path.join(folder, "assets");
      if (fs.existsSync(assets)) {
        copyDir(assets, path.join(contentOut, name, "assets"));
      }
    }
  }

  articles.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  fs.writeFileSync(
    outJson,
    JSON.stringify({ generatedAt: new Date().toISOString(), articles }, null, 2)
  );
  console.log(`Wrote ${articles.length} articles → ${path.relative(root, outJson)}`);
}

main();
