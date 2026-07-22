import { Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home.jsx";
import ArticlePage from "./pages/ArticlePage.jsx";
import SiteHeader from "./components/SiteHeader.jsx";
import SiteFooter from "./components/SiteFooter.jsx";

export default function App() {
  return (
    <div className="site">
      <div className="satire-banner" role="note">
        <strong>Satire site</strong> — Agent News (agentnews.site) is fictional
        satire, not a real news organization.{" "}
        <Link to="/">Home</Link>
      </div>
      <SiteHeader />
      <main className="site-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/article/:slug" element={<ArticlePage />} />
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
      <SiteFooter />
    </div>
  );
}
