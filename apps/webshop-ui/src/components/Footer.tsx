export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <span>© {new Date().getFullYear()} Acme Webshop</span>
        <span className="site-footer__muted">A demo storefront.</span>
      </div>
    </footer>
  );
}
