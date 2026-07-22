import { Link, NavLink } from "react-router-dom";

const SECTIONS = ["Local", "Politics", "Business", "Tech", "Culture", "Opinion"];

export default function SiteHeader() {
  return (
    <header className="masthead">
      <div className="masthead-top">
        <p className="masthead-kicker">Independent · Satirical · Municipal</p>
        <Link to="/" className="masthead-title">
          The Municipal Ledger
        </Link>
        <p className="masthead-tagline">
          All the news that&apos;s fit to invent
        </p>
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
