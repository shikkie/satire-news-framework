export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <p>
        <strong>Agent News</strong>
        {" · "}
        <a href="https://agentnews.site">agentnews.site</a>
      </p>
      <p className="muted">© {new Date().getFullYear()} Agent News</p>
    </footer>
  );
}
