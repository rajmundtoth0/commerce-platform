import { Link } from "react-router-dom";
import { useCart } from "../cart/useCart";

export function Header() {
  const { itemCount } = useCart();

  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <Link to="/" className="brand" aria-label="Acme Webshop home">
          <span className="brand__mark" aria-hidden="true">
            ◆
          </span>
          <span className="brand__name">Acme</span>
        </Link>
        <nav className="site-nav" aria-label="Primary">
          <Link to="/" className="site-nav__link">
            Shop
          </Link>
          <Link to="/cart" className="site-nav__link cart-link" aria-label={`Cart, ${itemCount} item${itemCount === 1 ? "" : "s"}`}>
            <span aria-hidden="true">Cart</span>
            {itemCount > 0 && (
              <span className="cart-badge" aria-hidden="true">
                {itemCount}
              </span>
            )}
          </Link>
        </nav>
      </div>
    </header>
  );
}
