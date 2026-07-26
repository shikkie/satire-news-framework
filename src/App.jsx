import { Routes, Route, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home.jsx";
import ArticlePage from "./pages/ArticlePage.jsx";
import SiteHeader from "./components/SiteHeader.jsx";
import SiteFooter from "./components/SiteFooter.jsx";
import AdminLogin from "./pages/admin/AdminLogin.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import AdminArticleEditor from "./pages/admin/AdminArticleEditor.jsx";
import AdminSessions from "./pages/admin/AdminSessions.jsx";

export default function App() {
  const loc = useLocation();
  const isAdmin = loc.pathname.startsWith("/admin");

  return (
    <div className="site">
      <div className="site-notice" role="note">
        <strong>Satire.</strong> Agent News is not a real news organization.
      </div>
      {!isAdmin ? <SiteHeader /> : null}
      <main className="site-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/article/:slug" element={<ArticlePage />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/articles/new" element={<AdminArticleEditor />} />
          <Route path="/admin/articles/:slug" element={<AdminArticleEditor />} />
          <Route path="/admin/sessions" element={<AdminSessions />} />
          <Route
            path="*"
            element={
              <div className="panel">
                <h1>Not found</h1>
                <p>
                  <Link to="/">Back to the front page</Link>
                </p>
              </div>
            }
          />
        </Routes>
      </main>
      {!isAdmin ? <SiteFooter /> : null}
    </div>
  );
}
