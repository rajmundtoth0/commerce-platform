import { useState } from "react";
import { Link } from "react-router-dom";
import type { Product, ProductWithPrice } from "../api/types";
import { useCart } from "../cart/useCart";
import { formatMoney } from "../lib/money";
import { ProductImage } from "./ProductImage";

function hasPrice(p: Product | ProductWithPrice): p is ProductWithPrice {
  return "amount_minor" in p;
}

export function ProductCard({ product }: { product: Product | ProductWithPrice }) {
  const { addItem } = useCart();
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const priced = hasPrice(product) ? product : null;

  const handleAdd = async () => {
    setAdding(true);
    setAdded(false);
    try {
      await addItem(product.id, 1);
      setAdded(true);
      window.setTimeout(() => setAdded(false), 1500);
    } catch {
      // Error surfaced via cart context; keep the card usable.
    } finally {
      setAdding(false);
    }
  };

  return (
    <article className="card">
      <Link to={`/product/${product.id}`} className="card__media">
        <ProductImage name={product.name} />
      </Link>
      <div className="card__body">
        <h3 className="card__title">
          <Link to={`/product/${product.id}`}>{product.name}</Link>
        </h3>
        {priced && (
          <p className="card__price">
            {formatMoney(priced.amount_minor, priced.currency)}
          </p>
        )}
        <button
          type="button"
          className="btn btn--primary card__add"
          onClick={handleAdd}
          disabled={adding}
        >
          {adding ? "Adding…" : added ? "Added ✓" : "Add to cart"}
        </button>
      </div>
    </article>
  );
}
