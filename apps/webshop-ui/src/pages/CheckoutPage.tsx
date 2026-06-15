import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Order } from "../api/types";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusViews";
import { useCart } from "../cart/useCart";
import { formatMoney } from "../lib/money";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function CheckoutPage() {
  const { cart, cartId, loading, error, reset } = useCart();

  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [order, setOrder] = useState<Order | null>(null);

  // Order confirmation view (cart already cleared).
  if (order) {
    return (
      <div className="container checkout">
        <div className="confirmation" role="status">
          <h1>Thank you for your order!</h1>
          <p className="confirmation__id">
            Order <strong>#{order.id}</strong>
          </p>
          <p>
            Status: <span className="badge">{order.status}</span>
          </p>
          <p className="confirmation__total">
            Total: {formatMoney(order.total_amount_minor, order.currency)}
          </p>
          <Link to="/" className="btn btn--primary">
            Continue shopping
          </Link>
        </div>
      </div>
    );
  }

  if (loading && !cart) {
    return (
      <div className="container">
        <Loading label="Loading checkout…" />
      </div>
    );
  }

  if (error && !cart) {
    return (
      <div className="container">
        <ErrorMessage message={error} />
      </div>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="container checkout">
        <h1>Checkout</h1>
        <EmptyState>
          <p>Your cart is empty, so there's nothing to check out.</p>
          <Link to="/" className="btn btn--primary">
            Browse products
          </Link>
        </EmptyState>
      </div>
    );
  }

  const emailValid = EMAIL_RE.test(email.trim());
  const canPlace = emailValid && !cart.has_unpriced_items && !submitting;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canPlace) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const placed = await api.checkout(cartId, email.trim());
      setOrder(placed);
      reset(); // Clear the local cart / rotate the cart id.
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Could not place order.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container checkout">
      <h1>Checkout</h1>

      <section className="checkout__summary" aria-label="Order summary">
        <h2>Order summary</h2>
        <ul className="summary-list">
          {cart.items.map((line) => (
            <li key={line.product_id} className="summary-list__item">
              <span>
                {line.name} × {line.quantity}
              </span>
              <span>{formatMoney(line.line_amount_minor, line.currency)}</span>
            </li>
          ))}
        </ul>
        <div className="summary-list__total">
          <span>Total</span>
          <span>{formatMoney(cart.total_amount_minor, cart.currency)}</span>
        </div>
      </section>

      {cart.has_unpriced_items && (
        <div className="notice" role="alert">
          Some items don't have a price yet, so this order can't be placed.
          Please remove the unpriced items before checking out.
        </div>
      )}

      <form className="checkout__form" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="field__label">Email address</span>
          <input
            type="email"
            className="field__input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
          {email.length > 0 && !emailValid && (
            <span className="field__hint">Please enter a valid email address.</span>
          )}
        </label>

        {submitError && <ErrorMessage message={submitError} />}

        <button type="submit" className="btn btn--primary btn--lg" disabled={!canPlace}>
          {submitting ? "Placing order…" : "Place order"}
        </button>
      </form>
    </div>
  );
}
