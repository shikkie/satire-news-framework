import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { parseBundleText } from "../../lib/articleBundle.js";
import {
  apiJson,
  clearSession,
  fetchMe,
  getSessionId,
  getSessionMeta,
  logout,
} from "../../lib/session.js";

export default function AdminHome() {
  const nav = useNavigate();
  const [me, setMe] = useState(getSessionMeta());
  const [articles, setArticles] = useState([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [q, setQ] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importOverwrite, setImportOverwrite] = useState(false);
  const [importAsDraft, setImportAsDraft] = useState(true);
  const [importBusy, setImportBusy] = useState(false);

  useEffect(() => {
    if (!getSessionId()) {
      nav("/admin/login");
      return;
    }
    let alive = true;
    (async () => {
      try {
        const profile = await fetchMe();
        if (!alive) return;
        setMe(profile);
        const data = await apiJson("/api/articles/admin");
        if (!alive) return;
        setArticles(data.articles || []);
      } catch (err) {
        if (!alive) return;
        if (err.status === 401) {
          clearSession();
          nav("/admin/login");
          return;
        }
        setError(err.message || "Failed to load");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nav]);

  async function onLogout() {
    await logout();
    nav("/admin/login");
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      setImportText(await file.text());
    } catch (err) {
      setError(err.message || "Could not read file");
    }
  }

  async function onImport() {
    setImportBusy(true);
    setError("");
    setMsg("");
    try {
      const bundle = parseBundleText(importText);
      const res = await apiJson("/api/articles/import", {
        method: "POST",
        body: JSON.stringify({
          ...bundle,
          overwrite: importOverwrite,
          as_draft: importAsDraft,
        }),
      });
      const slug = res.article?.slug;
      setMsg(`Imported ${slug}`);
      setImportText("");
      if (slug) {
        nav(`/admin/articles/${encodeURIComponent(slug)}`);
        return;
      }
      const data = await apiJson("/api/articles/admin");
      setArticles(data.articles || []);
    } catch (err) {
      if (err.status === 409) {
        setError(`${err.message || "Slug already exists"}. Check “overwrite” to replace it.`);
      } else {
        setError(err.message || "Import failed");
      }
    } finally {
      setImportBusy(false);
    }
  }

  const filtered = articles.filter((a) => {
    if (!q.trim()) return true;
    const hay = `${a.slug} ${a.title} ${a.status}`.toLowerCase();
    return hay.includes(q.trim().toLowerCase());
  });

  return (
    <div className="panel admin-panel">
      <div className="admin-toolbar">
        <div>
          <h1>Articles</h1>
          <p className="muted">
            Signed in as <strong>{me.username || "…"}</strong>
            {me.role ? ` (${me.role})` : ""}
          </p>
        </div>
        <div className="admin-toolbar-actions">
          <button
            type="button"
            className="admin-btn secondary"
            onClick={() => setImportOpen((open) => !open)}
          >
            Import article
          </button>
          <Link className="admin-btn" to="/admin/articles/new">
            New article
          </Link>
          {me.role === "admin" ? (
            <Link className="admin-btn secondary" to="/admin/sessions">
              Sessions
            </Link>
          ) : null}
          <button type="button" className="admin-btn secondary" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>
      <label className="admin-search">
        Filter
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="slug or title" />
      </label>
      {error ? <p className="admin-error">{error}</p> : null}
      {msg ? <p className="admin-ok">{msg}</p> : null}
      {importOpen ? (
        <section className="admin-bundle-panel">
          <h2>Import article bundle</h2>
          <p className="muted small">
            Upload or paste a JSON export from this admin (article fields plus
            base64-encoded media). Default is a draft so you can review before
            publishing.
          </p>
          <label>
            JSON file
            <input type="file" accept="application/json,.json" onChange={onImportFile} />
          </label>
          <label>
            Or paste JSON
            <textarea
              className="admin-bundle-json"
              rows={10}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{"format":"agentnews.article.v1", ...}'
              spellCheck={false}
            />
          </label>
          <label className="admin-check">
            <input
              type="checkbox"
              checked={importAsDraft}
              onChange={(e) => setImportAsDraft(e.target.checked)}
            />
            Import as draft
          </label>
          <label className="admin-check">
            <input
              type="checkbox"
              checked={importOverwrite}
              onChange={(e) => setImportOverwrite(e.target.checked)}
            />
            Overwrite if this slug already exists
          </label>
          <div className="admin-generate-row">
            <button
              type="button"
              className="admin-btn"
              disabled={importBusy || !importText.trim()}
              onClick={onImport}
            >
              {importBusy ? "Importing…" : "Import"}
            </button>
          </div>
        </section>
      ) : null}
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Section</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.slug}>
                <td>
                  <Link to={`/admin/articles/${encodeURIComponent(a.slug)}`}>{a.title}</Link>
                  <div className="muted small">{a.slug}</div>
                </td>
                <td>
                  <span className={`status-pill status-${a.status}`}>{a.status}</span>
                  {a.status === "scheduled" && a.scheduled_at ? (
                    <div className="muted small">{a.scheduled_at.slice(0, 16).replace("T", " ")} UTC</div>
                  ) : null}
                </td>
                <td>{a.section}</td>
                <td className="muted small">{(a.updated_at || "").slice(0, 19)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <Link to="/">← Front page</Link>
      </p>
    </div>
  );
}
