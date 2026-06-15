/**
 * Placeholder product image. Derives a stable hue from the product name so
 * each product gets a consistent, distinct tile without real imagery.
 */
export function ProductImage({
  name,
  size = "card",
}: {
  name: string;
  size?: "card" | "detail";
}) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) % 360;
  }
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join("");

  return (
    <div
      className={`product-image product-image--${size}`}
      style={{
        background: `linear-gradient(135deg, hsl(${hash} 60% 88%), hsl(${(hash + 40) % 360} 55% 78%))`,
      }}
      role="img"
      aria-label={`${name} image placeholder`}
    >
      <span aria-hidden="true">{initials || "?"}</span>
    </div>
  );
}
