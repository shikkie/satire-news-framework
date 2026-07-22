import { Link } from "react-router-dom";
import { formatDate, heroSrc } from "../lib/articles.js";

export default function ArticleCard({ article, featured = false }) {
  const hero = heroSrc(article);
  return (
    <article className={`card ${featured ? "card-featured" : ""}`}>
      {hero ? (
        <Link to={`/article/${article.slug}`} className="card-media">
          <img src={hero} alt="" loading="lazy" />
        </Link>
      ) : null}
      <div className="card-body">
        <p className="eyebrow">
          <span className="section-label">{article.section}</span>
          {article.date ? <time dateTime={article.date}>{formatDate(article.date)}</time> : null}
        </p>
        <h2 className="card-title">
          <Link to={`/article/${article.slug}`}>{article.title}</Link>
        </h2>
        {article.dek ? <p className="card-dek">{article.dek}</p> : null}
        <p className="byline">By {article.author}</p>
      </div>
    </article>
  );
}
