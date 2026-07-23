/**
 * After Vite build: inject Open Graph / Twitter Card meta into docs/index.html
 * and write docs/article/<slug>/index.html shells so Discord/Facebook/Slack
 * crawlers see title, dek, and hero without running JavaScript.
 *
 * Hash URLs (#/article/...) never work for social previews — crawlers strip the hash.
 * Share: https://agentnews.site/article/<slug>
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const docsDir = path.join(root, "docs");
const SITE = (process.env.SITE_ORIGIN || "https://agentnews.site").replace(
  /\/$/,
  ""
);

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function heroAbsUrl(article) {
  if (!article?.hero) return `${SITE}/favicon.svg`;
  if (/^https?:\/\//i.test(article.hero)) return article.hero;
  let rel = article.hero.replace(/^\.\//, "").replace(/^\/+/, "");
  if (!rel.startsWith("assets/") && !rel.includes("/")) {
    rel = `assets/${rel}`;
  }
  if (rel.startsWith("content/")) {
    return `${SITE}/${rel}`;
  }
  return `${SITE}/content/${article.slug}/${rel}`;
}

function stripSocialMeta(html) {
  return html
    .replace(/<title>[^<]*<\/title>/i, "")
    .replace(/<meta\s+name="description"[^>]*>\s*/gi, "")
    .replace(/<meta\s+property="og:[^"]*"[^>]*>\s*/gi, "")
    .replace(/<meta\s+name="twitter:[^"]*"[^>]*>\s*/gi, "")
    .replace(/<link\s+rel="canonical"[^>]*>\s*/gi, "");
}

function socialHead({ title, description, url, image, type = "website", section }) {
  const t = esc(title);
  const d = esc(description || title);
  const u = esc(url);
  const img = esc(image);
  const lines = [
    `<title>${t}</title>`,
    `<meta name="description" content="${d}" />`,
    `<link rel="canonical" href="${u}" />`,
    `<meta property="og:type" content="${esc(type)}" />`,
    `<meta property="og:site_name" content="Agent News" />`,
    `<meta property="og:title" content="${t}" />`,
    `<meta property="og:description" content="${d}" />`,
    `<meta property="og:url" content="${u}" />`,
    `<meta property="og:image" content="${img}" />`,
    `<meta property="og:image:secure_url" content="${img}" />`,
    `<meta property="og:image:alt" content="${t}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${t}" />`,
    `<meta name="twitter:description" content="${d}" />`,
    `<meta name="twitter:image" content="${img}" />`,
  ];
  if (type === "article" && section) {
    lines.push(`<meta property="article:section" content="${esc(section)}" />`);
  }
  return lines.join("\n    ");
}

/** Absolute asset paths so /article/slug/ pages load JS/CSS from site root */
function absolutizeAssetHrefs(html) {
  return html
    .replace(/(href|src)="\.\/assets\//g, '$1="/assets/')
    .replace(/(href|src)="assets\//g, '$1="/assets/')
    .replace(/(href|src)="\.\/favicon/g, '$1="/favicon')
    .replace(/(href|src)="favicon/g, '$1="/favicon');
}

function injectHead(html, headBlock) {
  let out = stripSocialMeta(html);
  out = absolutizeAssetHrefs(out);
  if (out.includes("</head>")) {
    return out.replace("</head>", `    ${headBlock}\n  </head>`);
  }
  return out;
}

function main() {
  const indexPath = path.join(docsDir, "index.html");
  const dataPath = path.join(docsDir, "articles-data.json");
  if (!fs.existsSync(indexPath)) {
    console.error("docs/index.html missing — run vite build first");
    process.exit(1);
  }
  if (!fs.existsSync(dataPath)) {
    console.error("docs/articles-data.json missing — run articles:build first");
    process.exit(1);
  }

  const shell = fs.readFileSync(indexPath, "utf8");
  const { articles = [] } = JSON.parse(fs.readFileSync(dataPath, "utf8"));

  const homeMeta = socialHead({
    title: "Agent News",
    description:
      "Agent News — satirical reporting from agentnews.site. Headlines, investigations, and invented urgency.",
    url: `${SITE}/`,
    image: `${SITE}/favicon.svg`,
    type: "website",
  });
  fs.writeFileSync(indexPath, injectHead(shell, homeMeta));
  console.log(`OG home → ${path.relative(root, indexPath)}`);

  // SPA fallback for unknown paths (GitHub Pages)
  fs.writeFileSync(path.join(docsDir, "404.html"), injectHead(shell, homeMeta));
  console.log("Wrote docs/404.html (SPA fallback)");

  let n = 0;
  for (const article of articles) {
    const slug = article.slug;
    if (!slug) continue;
    const url = `${SITE}/article/${slug}`;
    const image = heroAbsUrl(article);
    const desc =
      article.dek ||
      (article.body || "").replace(/[#>*`\[\]]/g, "").slice(0, 200).trim() ||
      article.title;
    const head = socialHead({
      title: `${article.title} — Agent News`,
      description: desc,
      url,
      image,
      type: "article",
      section: article.section,
    });
    const outDir = path.join(docsDir, "article", slug);
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = path.join(outDir, "index.html");
    fs.writeFileSync(outFile, injectHead(shell, head));
    n += 1;
    console.log(`  OG article/${slug}/  image=${image.startsWith(SITE) ? "ok" : image}`);
  }
  console.log(`Injected social meta for ${n} articles (origin ${SITE})`);
}

main();
