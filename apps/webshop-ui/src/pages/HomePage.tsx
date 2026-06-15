import { useCallback } from "react";
import { api } from "../api/client";
import type { Product, ProductListResponse } from "../api/types";
import { FeaturedSlider } from "../components/FeaturedSlider";
import { ProductCard } from "../components/ProductCard";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusViews";
import { useFetch } from "../hooks/useFetch";

interface HomeData {
  featured: Product[];
  products: ProductListResponse;
}

export function HomePage() {
  const loader = useCallback(async (signal: AbortSignal): Promise<HomeData> => {
    const [featured, products] = await Promise.all([
      api.getFeatured(signal),
      api.getProducts({ limit: 50, offset: 0 }, signal),
    ]);
    return { featured, products };
  }, []);

  const { data, loading, error } = useFetch(loader, []);

  return (
    <div className="home">
      <section className="hero">
        <div className="container hero__inner">
          <h1 className="hero__title">Thoughtfully made goods.</h1>
          <p className="hero__subtitle">
            A small, honest catalog. Browse below and add your favorites to the cart.
          </p>
        </div>
      </section>

      <div className="container">
        {loading && <Loading label="Loading catalog…" />}
        {error && !loading && <ErrorMessage message={error} />}

        {data && !loading && (
          <>
            <FeaturedSlider products={data.featured} />

            <section className="catalog" aria-label="All products">
              <h2>All products</h2>
              {data.products.items.length === 0 ? (
                <EmptyState>No products are available right now.</EmptyState>
              ) : (
                <div className="product-grid">
                  {data.products.items.map((product) => (
                    <ProductCard key={product.id} product={product} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
