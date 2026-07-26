import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiJson, clearSession, getSessionId } from "../../lib/session.js";
import { inlineImageSrc } from "../../lib/articles.js";

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
};

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

  useEffect(() => {
    if (!getSessionId()) {
      nav("/admin/login");
      return;
    }
    if (isNew) return;
    let alive = true;
    (async () => {
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

  async function save(publish = false) {
    setBusy(true);
    setError("");
    setMsg("");
    const payload = {
      slug: form.slug.trim(),
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
      status: publish ? "published" : form.status,
      reason: form.reason || (publish ? "publish" : "edit"),
    };
    try {
      if (isNew) {
        const res = await apiJson("/api/articles", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setMsg("Created");
        nav(`/admin/articles/${encodeURIComponent(res.article.slug)}`);
      } else {
        const res = await apiJson(`/api/articles/${encodeURIComponent(routeSlug)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setMsg(publish ? "Published" : "Saved");
        setVersions(res.article.versions || []);
        setForm((f) => ({
          ...f,
          status: res.article.status,
          markdown: res.article.markdown || res.article.body,
          reason: "",
          media: res.article.media || f.media,
        }));
      }
    } catch (err) {
      setError(err.message || "Save failed");
    } finally {
      setBusy(false);
    }
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
          <button type="button" className="admin-btn secondary" disabled={busy} onClick={() => save(false)}>
            Save
          </button>
          <button type="button" className="admin-btn" disabled={busy} onClick={() => save(true)}>
            Save &amp; publish
          </button>
        </div>
      </div>
      {error ? <p className="admin-error">{error}</p> : null}
      {msg ? <p className="admin-ok">{msg}</p> : null}

      <div className="admin-editor-grid">
        <div className="admin-form">
          {isNew ? (
            <label>
              Slug
              <input
                value={form.slug}
                onChange={(e) => setField("slug", e.target.value)}
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                required
              />
            </label>
          ) : (
            <p className="muted">
              Slug: <code>{form.slug}</code> · status:{" "}
              <span className={`status-pill status-${form.status}`}>{form.status}</span>
            </p>
          )}
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
          <h2>Live preview</h2>
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
