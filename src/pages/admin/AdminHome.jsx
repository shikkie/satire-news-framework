import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  const [q, setQ] = useState("");

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
