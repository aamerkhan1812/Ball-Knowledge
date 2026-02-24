export function MobileBottomNav() {
  return (
    <nav className="mobile-bottom-nav md:hidden" aria-label="Mobile match navigation">
      <a href="#battlefield-top" className="mobile-bottom-nav-item">
        Overview
      </a>
      <a href="#search-zone" className="mobile-bottom-nav-item">
        Search
      </a>
      <a href="#matches-feed" className="mobile-bottom-nav-item">
        Matches
      </a>
    </nav>
  );
}
