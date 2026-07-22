import { useEffect, useState } from "react";
import ArticleCard from "../components/ArticleCard.jsx";
import { fetchArticles } from "../lib/articles.js";

export default function Home() {
  const [articles, setArticles] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await fetchArticles();
        if (alive) setArticles(list);
      } catch (e) {
        if (alive) setError(e.message || "Failed to load articles");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="panel">
        <p className="muted">Loading the newsroom…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <h1>Could not load articles</h1>
        <p>{error}</p>
        <p className="muted">
          Is the preview API running? Try <code>./dev.sh status</code>
        </p>
      </div>
    );
  }

  if (!articles.length) {
    return (
      <div className="panel">
        <h1>No articles yet</h1>
        <p>
          Add a folder under <code>articles/&lt;slug&gt;/article.md</code> and
          refresh.
        </p>
      </div>
    );
  }

  const [lead, ...rest] = articles;

  return (
    <div className="home">
      <section className="lead-grid">
        <ArticleCard article={lead} featured />
        <div className="lead-rail">
          {rest.slice(0, 3).map((a) => (
            <ArticleCard key={a.slug} article={a} />
          ))}
        </div>
      </section>
      {rest.length > 3 ? (
        <section className="more-grid">
          <h2 className="section-heading">More headlines</h2>
          <div className="card-grid">
            {rest.slice(3).map((a) => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
