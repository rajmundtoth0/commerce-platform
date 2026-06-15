import { createContext } from "react";
import type { Cart } from "../api/types";

export interface CartContextValue {
  cartId: string;
  cart: Cart | null;
  loading: boolean;
  error: string | null;
  itemCount: number;
  /** Reload the cart from the API. */
  refresh: () => Promise<void>;
  addItem: (productId: string, quantity: number) => Promise<void>;
  removeItem: (productId: string) => Promise<void>;
  /** Clear the local cart and start a fresh cart id (used after checkout). */
  reset: () => void;
}

export const CartContext = createContext<CartContextValue | null>(null);
