import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchArticle, formatDate, heroSrc } from "../lib/articles.js";

export default function ArticlePage() {
  const { slug } = useParams();
  const [article, setArticle] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const data = await fetchArticle(slug);
        if (!alive) return;
        if (!data) setError("Article not found");
        else setArticle(data);
      } catch (e) {
        if (alive) setError(e.message || "Failed to load article");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [slug]);

  useEffect(() => {
    if (!article) return;
    const prev = document.title;
    document.title = `${article.title} — The Municipal Ledger`;
    return () => {
      document.title = prev;
    };
  }, [article]);

  if (loading) {
    return (
      <div className="panel">
        <p className="muted">Opening story…</p>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="panel">
        <h1>Story unavailable</h1>
        <p>{error || "Not found"}</p>
        <p>
          <Link to="/">← Front page</Link>
        </p>
      </div>
    );
  }

  const hero = heroSrc(article);

  return (
    <article className="story">
      <p className="eyebrow">
        <span className="section-label">{article.section}</span>
        {article.date ? (
          <time dateTime={article.date}>{formatDate(article.date)}</time>
        ) : null}
      </p>
      <h1 className="story-title">{article.title}</h1>
      {article.dek ? <p className="story-dek">{article.dek}</p> : null}
      <p className="byline">
        By <strong>{article.author}</strong>
      </p>
      {article.disclaimer !== false ? (
        <p className="story-disclaimer" role="note">
          Satirical content. Not real news.
        </p>
      ) : null}
      {hero ? (
        <figure className="story-hero">
          <img src={hero} alt="" />
        </figure>
      ) : null}
      <div className="story-body prose">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src = "", alt = "", ...rest }) => {
              let resolved = src;
              if (src && !src.startsWith("http") && !src.startsWith("/")) {
                resolved = `/content/${article.slug}/${src.replace(/^\.\//, "")}`;
              }
              return (
                <figure className="story-inline-figure">
                  <img src={resolved} alt={alt} loading="lazy" {...rest} />
                  {alt ? <figcaption>{alt}</figcaption> : null}
                </figure>
              );
            },
          }}
        >
          {article.body}
        </ReactMarkdown>
      </div>
      <p className="story-back">
        <Link to="/">← Back to top stories</Link>
      </p>
    </article>
  );
}
