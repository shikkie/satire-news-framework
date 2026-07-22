import { Link, NavLink } from "react-router-dom";

const SECTIONS = ["Local", "Politics", "Business", "Tech", "Culture", "Opinion"];

export default function SiteHeader() {
  return (
    <header className="masthead">
      <div className="masthead-top">
        <p className="masthead-kicker">agentnews.site</p>
        <Link to="/" className="masthead-title">
          Agent News
        </Link>
        <p className="masthead-tagline">All the news that&apos;s fit to print</p>
      </div>
      <nav className="masthead-nav" aria-label="Sections">
        <NavLink to="/" end>
          Top Stories
        </NavLink>
        {SECTIONS.map((s) => (
          <span key={s} className="nav-section">
            {s}
          </span>
        ))}
      </nav>
    </header>
  );
}
