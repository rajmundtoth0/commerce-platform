import { useState } from "react";
import { Link } from "react-router-dom";
import type { CartLine } from "../api/types";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusViews";
import { useCart } from "../cart/useCart";
import { formatMoney } from "../lib/money";

function CartRow({ line }: { line: CartLine }) {
  const { removeItem } = useCart();
  const [removing, setRemoving] = useState(false);

  const handleRemove = async () => {
    setRemoving(true);
    try {
      await removeItem(line.product_id);
    } catch {
      setRemoving(false);
    }
  };

  return (
    <tr>
      <td>
        <Link to={`/product/${line.product_id}`} className="cart__name">
          {line.name}
        </Link>
      </td>
      <td className="num">{line.quantity}</td>
      <td className="num">
        {formatMoney(line.unit_amount_minor, line.currency)}
      </td>
      <td className="num">
        {formatMoney(line.line_amount_minor, line.currency)}
      </td>
      <td className="num">
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={handleRemove}
          disabled={removing}
          aria-label={`Remove ${line.name} from cart`}
        >
          {removing ? "Removing…" : "Remove"}
        </button>
      </td>
    </tr>
  );
}

export function CartPage() {
  const { cart, loading, error, refresh } = useCart();

  if (loading && !cart) {
    return (
      <div className="container">
        <Loading label="Loading cart…" />
      </div>
    );
  }

  if (error && !cart) {
    return (
      <div className="container">
        <ErrorMessage message={error} onRetry={() => void refresh()} />
      </div>
    );
  }

  const isEmpty = !cart || cart.items.length === 0;

  return (
    <div className="container cart">
      <h1>Your cart</h1>

      {error && cart && <ErrorMessage message={error} />}

      {isEmpty ? (
        <EmptyState>
          <p>Your cart is empty.</p>
          <Link to="/" className="btn btn--primary">
            Browse products
          </Link>
        </EmptyState>
      ) : (
        <>
          {cart.has_unpriced_items && (
            <div className="notice" role="status">
              Some items in your cart don't have a price yet. The total below
              may be incomplete, and checkout may be unavailable until pricing
              is resolved.
            </div>
          )}

          <table className="cart__table">
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col" className="num">Qty</th>
                <th scope="col" className="num">Unit</th>
                <th scope="col" className="num">Line total</th>
                <th scope="col" className="num">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {cart.items.map((line) => (
                <CartRow key={line.product_id} line={line} />
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={3}>
                  Total
                </th>
                <td className="num cart__total">
                  {formatMoney(cart.total_amount_minor, cart.currency)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>

          <div className="cart__actions">
            <Link to="/" className="btn btn--ghost">
              Continue shopping
            </Link>
            <Link to="/checkout" className="btn btn--primary">
              Proceed to checkout
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
