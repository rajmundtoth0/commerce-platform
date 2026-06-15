import { useRef } from "react";
import { Link } from "react-router-dom";
import type { Product } from "../api/types";
import { ProductImage } from "./ProductImage";

export function FeaturedSlider({ products }: { products: Product[] }) {
  const trackRef = useRef<HTMLDivElement>(null);

  if (products.length === 0) {
    return null;
  }

  const scrollBy = (direction: 1 | -1) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: direction * track.clientWidth * 0.8, behavior: "smooth" });
  };

  return (
    <section className="featured" aria-label="Featured products">
      <div className="featured__head">
        <h2>Featured</h2>
        <div className="featured__controls">
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => scrollBy(-1)}
            aria-label="Scroll featured products left"
          >
            ‹
          </button>
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => scrollBy(1)}
            aria-label="Scroll featured products right"
          >
            ›
          </button>
        </div>
      </div>
      <div className="featured__track" ref={trackRef}>
        {products.map((product) => (
          <Link
            key={product.id}
            to={`/product/${product.id}`}
            className="featured__item"
          >
            <ProductImage name={product.name} />
            <span className="featured__name">{product.name}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
