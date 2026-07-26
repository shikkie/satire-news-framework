import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiJson, clearSession, getSessionId } from "../../lib/session.js";

export default function AdminSessions() {
  const nav = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getSessionId()) {
      nav("/admin/login");
      return;
    }
    let alive = true;
    (async () => {
      try {
        const data = await apiJson("/api/auth/sessions");
        if (alive) setSessions(data.sessions || []);
      } catch (err) {
        if (err.status === 401) {
          clearSession();
          nav("/admin/login");
          return;
        }
        if (alive) setError(err.message || "Failed");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nav]);

  return (
    <div className="panel admin-panel">
      <h1>Active sessions</h1>
      <p className="muted">Admin only. Idle TTL is 15 minutes (resets on each API use).</p>
      {error ? <p className="admin-error">{error}</p> : null}
      <table className="admin-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Session</th>
            <th>Last seen</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s, i) => (
            <tr key={i}>
              <td>{s.username}</td>
              <td>{s.role}</td>
              <td>
                <code>{s.session_id_prefix}</code>
              </td>
              <td className="muted small">{(s.last_seen_at || "").slice(0, 19)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <Link to="/admin">← Articles</Link>
      </p>
    </div>
  );
}
