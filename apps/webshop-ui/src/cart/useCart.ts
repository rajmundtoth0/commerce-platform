import { useContext } from "react";
import { CartContext } from "./CartContext";
import type { CartContextValue } from "./CartContext";

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return ctx;
}
