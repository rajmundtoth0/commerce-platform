import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ProductDetail } from "../api/types";
import { ProductImage } from "../components/ProductImage";
import { ErrorMessage, Loading } from "../components/StatusViews";
import { useCart } from "../cart/useCart";
import { useFetch } from "../hooks/useFetch";
import { formatMoney } from "../lib/money";

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addItem } = useCart();

  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const loader = useCallback(
    (signal: AbortSignal): Promise<ProductDetail> => {
      if (!id) {
        return Promise.reject(new Error("Missing product id."));
      }
      return api.getProduct(id, signal);
    },
    [id],
  );

  const { data: product, loading, error } = useFetch(loader, [id]);

  const handleAdd = async () => {
    if (!product) return;
    setAdding(true);
    setAddError(null);
    try {
      await addItem(product.id, quantity);
      navigate("/cart");
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Could not add to cart.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="container pdp">
      <p className="breadcrumb">
        <Link to="/">← Back to shop</Link>
      </p>

      {loading && <Loading label="Loading product…" />}
      {error && !loading && <ErrorMessage message={error} />}

      {product && !loading && (
        <div className="pdp__layout">
          <div className="pdp__media">
            <ProductImage name={product.name} size="detail" />
          </div>
          <div className="pdp__info">
            <h1 className="pdp__title">{product.name}</h1>
            <p className="pdp__sku">SKU: {product.sku}</p>
            <p className="pdp__price">
              {formatMoney(product.amount_minor, product.currency)}
            </p>
            <p className="pdp__description">{product.description}</p>

            <div className="pdp__purchase">
              <label className="qty">
                <span className="qty__label">Quantity</span>
                <input
                  type="number"
                  className="qty__input"
                  min={1}
                  max={99}
                  value={quantity}
                  onChange={(e) => {
                    const next = Number.parseInt(e.target.value, 10);
                    setQuantity(Number.isNaN(next) ? 1 : Math.min(99, Math.max(1, next)));
                  }}
                />
              </label>
              <button
                type="button"
                className="btn btn--primary"
                onClick={handleAdd}
                disabled={adding || !product.active}
              >
                {!product.active
                  ? "Unavailable"
                  : adding
                    ? "Adding…"
                    : "Add to cart"}
              </button>
            </div>

            {addError && <ErrorMessage message={addError} />}
          </div>
        </div>
      )}
    </div>
  );
}
