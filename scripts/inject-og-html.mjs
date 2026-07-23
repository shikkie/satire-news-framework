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

function socialHead({
  title,
  description,
  url,
  image,
  type = "website",
  section,
  imageWidth,
  imageHeight,
  imageAlt,
}) {
  const t = esc(title);
  const d = esc(description || title);
  const u = esc(url);
  const img = esc(image);
  const alt = esc(imageAlt || title);
  const lines = [
    `<title>${t}</title>`,
    `<meta name="description" content="${d}" />`,
    `<link rel="canonical" href="${u}" />`,
    `<meta property="og:locale" content="en_US" />`,
    `<meta property="og:type" content="${esc(type)}" />`,
    `<meta property="og:site_name" content="Agent News" />`,
    `<meta property="og:title" content="${t}" />`,
    `<meta property="og:description" content="${d}" />`,
    `<meta property="og:url" content="${u}" />`,
    `<meta property="og:image" content="${img}" />`,
    `<meta property="og:image:secure_url" content="${img}" />`,
    `<meta property="og:image:type" content="image/jpeg" />`,
    `<meta property="og:image:alt" content="${alt}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${t}" />`,
    `<meta name="twitter:description" content="${d}" />`,
    `<meta name="twitter:image" content="${img}" />`,
    `<meta name="twitter:image:alt" content="${alt}" />`,
  ];
  if (imageWidth) {
    lines.push(`<meta property="og:image:width" content="${esc(String(imageWidth))}" />`);
  }
  if (imageHeight) {
    lines.push(
      `<meta property="og:image:height" content="${esc(String(imageHeight))}" />`
    );
  }
  if (type === "article" && section) {
    lines.push(`<meta property="article:section" content="${esc(section)}" />`);
  }
  return lines.join("\n    ");
}

const HOME_TITLE = "Agent News — Satirical News & Fake Headlines";
const HOME_DESCRIPTION =
  "Agent News (agentnews.site) publishes deadpan satirical reporting: invented scandals, municipal absurdity, tech farce, and local nonsense with the layout of a real paper. Not a real news organization.";


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

  // Prefer dedicated share card; fall back to newest article hero with image
  const ogDefault = path.join(docsDir, "og-default.jpg");
  let homeImage = `${SITE}/og-default.jpg`;
  let homeImageW = 1280;
  let homeImageH = 720;
  if (!fs.existsSync(ogDefault)) {
    const withHero = articles.find((a) => a.hero);
    if (withHero) {
      homeImage = heroAbsUrl(withHero);
    } else {
      homeImage = `${SITE}/favicon.svg`;
      homeImageW = undefined;
      homeImageH = undefined;
    }
  }

  const topHeadlines = articles
    .slice(0, 3)
    .map((a) => a.title)
    .filter(Boolean);
  const homeDesc =
    topHeadlines.length > 0
      ? `${HOME_DESCRIPTION} Latest: ${topHeadlines.join(" · ")}`.slice(0, 300)
      : HOME_DESCRIPTION;

  const homeMeta = socialHead({
    title: HOME_TITLE,
    description: homeDesc,
    url: `${SITE}/`,
    image: homeImage,
    type: "website",
    imageWidth: homeImageW,
    imageHeight: homeImageH,
    imageAlt: "Agent News masthead — satirical newspaper",
  });
  fs.writeFileSync(indexPath, injectHead(shell, homeMeta));
  console.log(`OG home → ${path.relative(root, indexPath)} image=${homeImage}`);

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
