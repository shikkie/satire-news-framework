import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { copyText, downloadJson, stringifyBundle } from "../../lib/articleBundle.js";
import { apiJson, authHeaders, clearSession, getSessionId } from "../../lib/session.js";
import { ARTICLE_PREVIEW_PARAM, inlineImageSrc } from "../../lib/articles.js";

const EMPTY = {
  slug: "",
  title: "",
  dek: "",
  author: "Staff",
  section: "Local",
  tags: "",
  hero: "hero",
  markdown: "",
  status: "draft",
  reason: "",
  creation_prompt: "",
  post_to_x: true,
  scheduled_at: "",
  x_post: null,
  generation: null,
  placeholder: false,
};

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString();
}

function simpleDiff(a, b) {
  const al = (a || "").split("\n");
  const bl = (b || "").split("\n");
  const max = Math.max(al.length, bl.length);
  const rows = [];
  for (let i = 0; i < max; i++) {
    const left = al[i];
    const right = bl[i];
    if (left === right) {
      rows.push({ type: "same", text: left ?? "" });
    } else {
      if (left !== undefined) rows.push({ type: "del", text: left });
      if (right !== undefined) rows.push({ type: "add", text: right });
    }
  }
  return rows;
}

export default function AdminArticleEditor() {
  const { slug: routeSlug } = useParams();
  const isNew = !routeSlug || routeSlug === "new";
  const nav = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [versions, setVersions] = useState([]);
  const [diffFrom, setDiffFrom] = useState(null);
  const [diffTo, setDiffTo] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportText, setExportText] = useState("");
  const [exportMeta, setExportMeta] = useState(null);
  const [settings, setSettings] = useState({
    x_post_enabled: false,
    x_post_configured: false,
    scheduler_enabled: false,
    generate_configured: false,
  });

  useEffect(() => {
    if (!getSessionId()) {
      nav("/admin/login");
      return;
    }
    let alive = true;
    (async () => {
      try {
        const flags = await apiJson("/api/settings");
        if (alive) setSettings(flags);
      } catch {
        /* settings are optional for the form */
      }
      if (isNew) return;
      try {
        const article = await apiJson(`/api/articles/${encodeURIComponent(routeSlug)}`);
        if (!alive) return;
        setForm({
          slug: article.slug,
          title: article.title || "",
          dek: article.dek || "",
          author: article.author || "Staff",
          section: article.section || "Local",
          tags: (article.tags || []).join(", "),
          hero: article.hero?.startsWith("http")
            ? "hero"
            : article.hero || "hero",
          markdown: article.markdown || article.body || "",
          status: article.status || "draft",
          reason: "",
          media: article.media || [],
          creation_prompt: article.creation_prompt || "",
          post_to_x: article.post_to_x !== false,
          scheduled_at: article.scheduled_at || "",
          x_post: article.x_post || null,
          generation: article.generation || null,
          placeholder: Boolean(article.placeholder),
        });
        const v = await apiJson(
          `/api/articles/${encodeURIComponent(routeSlug)}/versions`
        );
        if (!alive) return;
        setVersions(v.versions || []);
        if ((v.versions || []).length >= 2) {
          setDiffFrom(v.versions[v.versions.length - 2].version);
          setDiffTo(v.versions[v.versions.length - 1].version);
        }
      } catch (err) {
        if (err.status === 401) {
          clearSession();
          nav("/admin/login");
          return;
        }
        setError(err.message || "Load failed");
      }
    })();
    return () => {
      alive = false;
    };
  }, [isNew, routeSlug, nav]);

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function applyArticle(article, extra = {}) {
    setForm((f) => ({
      ...f,
      slug: article.slug || f.slug,
      title: article.title || "",
      dek: article.dek || "",
      author: article.author || "Staff",
      section: article.section || "Local",
      tags: (article.tags || []).join(", "),
      hero: article.hero?.startsWith("http") ? f.hero || "hero" : article.hero || "hero",
      markdown: article.markdown || article.body || "",
      status: article.status || "draft",
      media: article.media || [],
      creation_prompt: article.creation_prompt ?? f.creation_prompt,
      post_to_x: article.post_to_x !== false,
      scheduled_at: article.scheduled_at || "",
      x_post: article.x_post || null,
      generation: article.generation || null,
      placeholder: Boolean(article.placeholder),
      ...extra,
    }));
  }

  const generating = form.generation?.status === "running";

  useEffect(() => {
    if (isNew || !generating || !routeSlug) return undefined;
    let alive = true;
    const decoder = new TextDecoder();
    let leftover = "";

    async function consumeStream() {
      try {
        const res = await fetch(
          `/api/articles/${encodeURIComponent(routeSlug)}/generate/stream`,
          { headers: authHeaders(), cache: "no-store" },
        );
        if (!res.ok || !res.body) throw new Error("stream unavailable");
        const reader = res.body.getReader();
        while (alive) {
          const { done, value } = await reader.read();
          if (done) break;
          leftover += decoder.decode(value, { stream: true });
          const lines = leftover.split("\n");
          leftover = lines.pop() || "";
          for (const line of lines) {
            if (!line.trim()) continue;
            let msg;
            try {
              msg = JSON.parse(line);
            } catch {
              continue;
            }
            if (msg.type === "event" && msg.event) {
              setForm((f) => {
                const gen = f.generation || { status: "running", logs: [], events: [] };
                const events = [...(gen.events || []), msg.event];
                const logs = [...(gen.logs || [])];
                const bit = [msg.event.kind, msg.event.name, msg.event.text]
                  .filter(Boolean)
                  .join(" ");
                if (bit) logs.push(bit);
                return { ...f, generation: { ...gen, status: "running", events, logs } };
              });
            }
            if (msg.type === "done") {
              try {
                const article = await apiJson(
                  `/api/articles/${encodeURIComponent(routeSlug)}`,
                );
                if (!alive) return;
                applyArticle(article, { reason: "" });
                const dest = msg.final_slug || article.generation?.final_slug || article.slug;
                if (msg.status === "ok") {
                  setMsg("Generated — review the draft, then save or publish.");
                  if (dest && dest !== routeSlug) {
                    nav(`/admin/articles/${encodeURIComponent(dest)}`);
                  }
                } else {
                  setError(msg.error || "Generate failed");
                }
              } catch {
                /* ignore */
              }
            }
          }
        }
      } catch {
        /* fall back to poll */
        while (alive) {
          try {
            const article = await apiJson(
              `/api/articles/${encodeURIComponent(routeSlug)}`,
            );
            if (!alive) return;
            applyArticle(article, { reason: "" });
            const st = article.generation?.status;
            if (st === "ok") {
              setMsg("Generated — review the draft, then save or publish.");
              const dest = article.generation?.final_slug || article.slug;
              if (dest && dest !== routeSlug) {
                nav(`/admin/articles/${encodeURIComponent(dest)}`);
              }
              return;
            }
            if (st === "error") {
              setError(article.generation.error || "Generate failed");
              return;
            }
          } catch {
            /* keep polling */
          }
          await new Promise((r) => setTimeout(r, 800));
        }
      }
    }

    consumeStream();
    return () => {
      alive = false;
    };
  }, [isNew, routeSlug, generating]);

  async function loadExport() {
    if (isNew || !routeSlug) {
      setError("Save the article before exporting.");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const bundle = await apiJson(`/api/articles/${encodeURIComponent(routeSlug)}/export`);
      const text = stringifyBundle(bundle);
      setExportText(text);
      setExportMeta({
        slug: bundle.article?.slug || routeSlug,
        assets: (bundle.assets || []).length,
        errors: bundle.asset_errors || [],
      });
      setExportOpen(true);
    } catch (err) {
      setError(err.message || "Export failed");
    } finally {
      setBusy(false);
    }
  }

  async function copyExport() {
    if (!exportText) return;
    try {
      const ok = await copyText(exportText);
      if (ok) {
        setMsg("Copied article JSON to clipboard.");
        return;
      }
    } catch {
      /* fall through */
    }
    setError("Clipboard copy failed — select the JSON below and copy it manually.");
  }

  function downloadExport() {
    if (!exportText) return;
    const slug = exportMeta?.slug || routeSlug || "article";
    downloadJson(`${slug}.article.json`, exportText);
    setMsg("Download started.");
  }

  async function generateFromPrompt() {
    if (!form.creation_prompt.trim()) {
      setError("Add an AI creation prompt first.");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const path =
        isNew || !routeSlug
          ? "/api/articles/generate"
          : `/api/articles/${encodeURIComponent(routeSlug)}/generate`;
      const res = await apiJson(path, {
        method: "POST",
        body: JSON.stringify({
          creation_prompt: form.creation_prompt,
          slug: form.slug.trim(),
          title: form.title,
          dek: form.dek,
          author: form.author,
          section: form.section,
          tags: form.tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
          post_to_x: form.post_to_x,
          scheduled_at: form.scheduled_at || null,
        }),
      });
      if (res.article) {
        applyArticle(res.article, { reason: "" });
        if (res.article.slug && res.article.slug !== routeSlug) {
          nav(`/admin/articles/${encodeURIComponent(res.article.slug)}`);
        }
      }
      setMsg("Generating… this can take several minutes (writing + images).");
    } catch (err) {
      setError(err.message || "Generate failed");
    } finally {
      setBusy(false);
    }
  }

  const scheduleIso = form.scheduled_at;
  const scheduleIsFuture = Boolean(
    scheduleIso && !Number.isNaN(new Date(scheduleIso).getTime()) && new Date(scheduleIso) > new Date()
  );

  async function save(publish = false) {
    setBusy(true);
    setError("");
    setMsg("");
    let status = form.status || "draft";
    if (publish) {
      status = scheduleIsFuture ? "scheduled" : "published";
    }
    const payload = {
      slug: form.slug.trim() || undefined,
      title: form.title,
      dek: form.dek,
      author: form.author,
      section: form.section,
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      hero: form.hero,
      markdown: form.markdown,
      status,
      reason: form.reason || (publish ? (status === "scheduled" ? "schedule" : "publish") : "edit"),
      creation_prompt: form.creation_prompt,
      post_to_x: form.post_to_x,
      scheduled_at: scheduleIso || null,
    };
    try {
      if (isNew) {
        const res = await apiJson("/api/articles", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setMsg(statusMessage(status, res.x_post));
        nav(`/admin/articles/${encodeURIComponent(res.article.slug)}`);
      } else {
        const res = await apiJson(`/api/articles/${encodeURIComponent(routeSlug)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setMsg(publish ? statusMessage(res.article.status, res.x_post) : "Saved");
        setVersions(res.article.versions || []);
        setForm((f) => ({
          ...f,
          status: res.article.status,
          markdown: res.article.markdown || res.article.body,
          reason: "",
          media: res.article.media || f.media,
          creation_prompt: res.article.creation_prompt ?? f.creation_prompt,
          post_to_x: res.article.post_to_x !== false,
          scheduled_at: res.article.scheduled_at || "",
          x_post: res.article.x_post || null,
        }));
      }
    } catch (err) {
      setError(err.message || "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function statusMessage(status, xPost) {
    if (status === "scheduled") return "Scheduled";
    if (status !== "published") return "Saved";
    const xs = xPost?.status;
    if (xs === "ok") return "Published and posted to X";
    if (xs === "stub") return "Published (X post stubbed — add API credentials)";
    if (xs === "skipped") return "Published (X post off for this article)";
    if (xs === "disabled") return "Published (X posting is disabled on this site)";
    if (xs === "already_posted") return "Published";
    if (xs === "error") return `Published, but X post failed: ${xPost?.error || "unknown"}`;
    return "Published";
  }

  const previewArticle = useMemo(
    () => ({
      slug: form.slug || "preview",
      media: form.media || [],
      hero: form.hero,
    }),
    [form.slug, form.media, form.hero]
  );

  const diffRows = useMemo(() => {
    if (diffFrom == null || diffTo == null) return [];
    const a = versions.find((v) => v.version === Number(diffFrom));
    const b = versions.find((v) => v.version === Number(diffTo));
    if (!a || !b) return [];
    return simpleDiff(a.markdown, b.markdown);
  }, [versions, diffFrom, diffTo]);

  return (
    <div className="panel admin-panel admin-editor">
      <div className="admin-toolbar">
        <h1>{isNew ? "New article" : `Edit: ${form.title || routeSlug}`}</h1>
        <div className="admin-toolbar-actions">
          <Link className="admin-btn secondary" to="/admin">
            ← List
          </Link>
          {!isNew ? (
            <button
              type="button"
              className="admin-btn secondary"
              disabled={busy}
              onClick={loadExport}
            >
              Export JSON
            </button>
          ) : null}
          <button type="button" className="admin-btn secondary" disabled={busy} onClick={() => save(false)}>
            Save
          </button>
          <button type="button" className="admin-btn" disabled={busy} onClick={() => save(true)}>
            {scheduleIsFuture ? "Schedule" : "Save & publish"}
          </button>
        </div>
      </div>
      {error ? <p className="admin-error">{error}</p> : null}
      {msg ? <p className="admin-ok">{msg}</p> : null}
      {exportOpen ? (
        <section className="admin-bundle-panel">
          <h2>Export article bundle</h2>
          <p className="muted small">
            One JSON file: fields, markdown, creation prompt, and base64-encoded
            media. Download it or copy/paste into another instance’s Import
            article panel.
          </p>
          {exportMeta ? (
            <p className="muted small">
              <code>{exportMeta.slug}</code> · {exportMeta.assets} asset
              {exportMeta.assets === 1 ? "" : "s"}
              {exportMeta.errors?.length
                ? ` · ${exportMeta.errors.length} asset(s) could not be read`
                : ""}
            </p>
          ) : null}
          {exportMeta?.errors?.length ? (
            <p className="admin-error">{exportMeta.errors.join(" · ")}</p>
          ) : null}
          <div className="admin-generate-row">
            <button type="button" className="admin-btn" onClick={downloadExport}>
              Download JSON
            </button>
            <button type="button" className="admin-btn secondary" onClick={copyExport}>
              Copy JSON
            </button>
            <button
              type="button"
              className="admin-btn secondary"
              onClick={() => setExportOpen(false)}
            >
              Close
            </button>
          </div>
          <label>
            JSON (copy/paste)
            <textarea
              className="admin-bundle-json"
              rows={10}
              value={exportText}
              readOnly
              spellCheck={false}
            />
          </label>
        </section>
      ) : null}

      <div className="admin-editor-grid">
        <div className="admin-form">
          {isNew ? (
            <label>
              Slug
              <span className="muted small admin-field-hint">
                Optional. Leave blank and Generate — the AI will choose a kebab-case slug.
              </span>
              <input
                value={form.slug}
                onChange={(e) => setField("slug", e.target.value)}
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                placeholder="leave blank for AI"
              />
            </label>
          ) : (
            <p className="muted">
              Slug:{" "}
              <code>
                {form.placeholder || (form.slug || "").startsWith("draft-")
                  ? "AI will choose on generate"
                  : form.slug}
              </code>{" "}
              · status:{" "}
              <span className={`status-pill status-${form.status}`}>{form.status}</span>
            </p>
          )}
          <label>
            AI creation prompt
            <span className="muted small admin-field-hint">
              Brief for automated generation — the same pitch you would pass to{" "}
              <code>create-article.sh</code> or agentnewsd <code>article_def</code>.
            </span>
            <textarea
              className="admin-prompt"
              rows={isNew ? 10 : 6}
              value={form.creation_prompt}
              onChange={(e) => setField("creation_prompt", e.target.value)}
              placeholder="Six-week-old orange kitten calls 911 because breakfast is late. Interview the kitten and the sergeant."
            />
          </label>
          <div className="admin-generate-row">
            <button
              type="button"
              className="admin-btn"
              disabled={busy || generating || !form.creation_prompt.trim()}
              onClick={generateFromPrompt}
            >
              {generating ? "Generating…" : "Generate from prompt"}
            </button>
            {!settings.generate_configured ? (
              <span className="muted small">
                Grok is not available in the API container (<code>GROK_BIN</code>).
              </span>
            ) : (
              <span className="muted small">
                Launches <code>grok agent stdio</code> (ACP, same as raccoon-herder) and
                streams the turn here. Stays a draft until you publish.
              </span>
            )}
          </div>
          {form.generation?.status ? (
            <div className="admin-studio">
              <div className="admin-studio-head">
                <strong>Grok ACP studio</strong>
                <span className={`status-pill status-${form.generation.status}`}>
                  {form.generation.status}
                </span>
                {generating ? <span className="muted small">live</span> : null}
              </div>
              {form.generation.error ? (
                <p className="admin-error">{form.generation.error}</p>
              ) : null}
              <div className="admin-studio-feed">
                {(form.generation.events || []).length
                  ? (form.generation.events || []).map((ev, i) => (
                      <div key={`${ev.at}-${i}`} className={`studio-line studio-${ev.kind}`}>
                        <span className="studio-kind">
                          {ev.kind === "tool"
                            ? `tool ${ev.name || ""} ${ev.status || ""}`.trim()
                            : ev.kind}
                        </span>
                        {ev.text ? <span className="studio-text">{ev.text}</span> : null}
                      </div>
                    ))
                  : (
                    <pre>{(form.generation.logs || []).join("\n") || "(waiting for ACP events…)"}</pre>
                  )}
              </div>
            </div>
          ) : null}
          <label>
            Title
            <input value={form.title} onChange={(e) => setField("title", e.target.value)} />
          </label>
          <label>
            Dek
            <input value={form.dek} onChange={(e) => setField("dek", e.target.value)} />
          </label>
          <div className="admin-form-row">
            <label>
              Author
              <input value={form.author} onChange={(e) => setField("author", e.target.value)} />
            </label>
            <label>
              Section
              <input value={form.section} onChange={(e) => setField("section", e.target.value)} />
            </label>
          </div>
          <label>
            Tags (comma-separated)
            <input value={form.tags} onChange={(e) => setField("tags", e.target.value)} />
          </label>
          <label>
            Hero media name
            <input value={form.hero} onChange={(e) => setField("hero", e.target.value)} />
          </label>
          <label>
            Publish at
            <span className="muted small admin-field-hint">
              Browser local time. Leave empty to publish immediately. A future time
              turns “Save &amp; publish” into Schedule
              {settings.scheduler_enabled ? " (background worker will go live)." : "."}
            </span>
            <input
              type="datetime-local"
              value={toLocalInput(form.scheduled_at)}
              onChange={(e) => setField("scheduled_at", fromLocalInput(e.target.value))}
            />
          </label>
          <label className="admin-check">
            <input
              type="checkbox"
              checked={form.post_to_x}
              onChange={(e) => setField("post_to_x", e.target.checked)}
            />
            Post to X when this article is published
          </label>
          {!settings.x_post_enabled ? (
            <p className="muted small">
              Site-wide X posting is off (<code>X_POST_ENABLED</code>). The checkbox is
              stored and will apply once the feature is enabled.
            </p>
          ) : !settings.x_post_configured ? (
            <p className="muted small">
              X posting is on, but OAuth credentials are not set — publishes will stub.
            </p>
          ) : null}
          {form.x_post?.status ? (
            <p className="muted small">
              X post: {form.x_post.status}
              {form.x_post.url ? (
                <>
                  {" "}
                  ·{" "}
                  <a href={form.x_post.url} target="_blank" rel="noreferrer">
                    view
                  </a>
                </>
              ) : null}
              {form.x_post.error ? ` — ${form.x_post.error}` : ""}
            </p>
          ) : null}
          <label>
            Edit reason (version history)
            <input value={form.reason} onChange={(e) => setField("reason", e.target.value)} />
          </label>
          <label>
            Markdown body
            <textarea
              rows={18}
              value={form.markdown}
              onChange={(e) => setField("markdown", e.target.value)}
            />
          </label>
        </div>

        <div className="admin-preview">
          <div className="admin-preview-head">
            <h2>Live preview</h2>
            {form.slug ? (
              <a
                className="admin-btn secondary"
                href={`/article/${encodeURIComponent(form.slug)}?${ARTICLE_PREVIEW_PARAM}=1`}
                target="_blank"
                rel="noreferrer"
              >
                View as published
              </a>
            ) : (
              <span className="muted small">Save or generate a slug to open full preview</span>
            )}
          </div>
          <article className="story prose">
            <h1 className="story-title">{form.title || "Untitled"}</h1>
            {form.dek ? <p className="story-dek">{form.dek}</p> : null}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                img: ({ src = "", alt = "" }) => (
                  <figure className="story-inline-figure">
                    <img src={inlineImageSrc(previewArticle, src)} alt={alt} />
                    {alt ? <figcaption>{alt}</figcaption> : null}
                  </figure>
                ),
              }}
            >
              {form.markdown || "*Nothing yet*"}
            </ReactMarkdown>
          </article>
        </div>
      </div>

      {!isNew && versions.length > 0 ? (
        <section className="admin-versions">
          <h2>Version history</h2>
          <ul className="admin-version-list">
            {[...versions].reverse().map((v) => (
              <li key={v.version}>
                <strong>v{v.version}</strong> · {v.edited_by} · {(v.edited_at || "").slice(0, 19)}
                {v.reason ? ` — ${v.reason}` : ""}
              </li>
            ))}
          </ul>
          {versions.length >= 2 ? (
            <>
              <div className="admin-form-row">
                <label>
                  Diff from
                  <select
                    value={diffFrom ?? ""}
                    onChange={(e) => setDiffFrom(Number(e.target.value))}
                  >
                    {versions.map((v) => (
                      <option key={v.version} value={v.version}>
                        v{v.version}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Diff to
                  <select value={diffTo ?? ""} onChange={(e) => setDiffTo(Number(e.target.value))}>
                    {versions.map((v) => (
                      <option key={v.version} value={v.version}>
                        v{v.version}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <pre className="admin-diff">
                {diffRows.map((row, i) => (
                  <div key={i} className={`diff-line diff-${row.type}`}>
                    {row.type === "add" ? "+ " : row.type === "del" ? "- " : "  "}
                    {row.text}
                  </div>
                ))}
              </pre>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
