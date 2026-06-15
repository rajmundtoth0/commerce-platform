import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { Cart } from "../api/types";
import { getOrCreateCartId, resetCartId } from "./cartId";
import { CartContext } from "./CartContext";
import type { CartContextValue } from "./CartContext";

export function CartProvider({ children }: { children: ReactNode }) {
  const [cartId, setCartId] = useState<string>(() => getOrCreateCartId());
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef<boolean>(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.getCart(cartId);
      if (mounted.current) setCart(next);
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof Error ? err.message : "Could not load cart.");
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [cartId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addItem = useCallback(
    async (productId: string, quantity: number) => {
      setError(null);
      try {
        const next = await api.addCartItem(cartId, productId, quantity);
        if (mounted.current) setCart(next);
      } catch (err) {
        if (mounted.current) {
          setError(err instanceof Error ? err.message : "Could not add item.");
        }
        throw err;
      }
    },
    [cartId],
  );

  const removeItem = useCallback(
    async (productId: string) => {
      setError(null);
      try {
        const next = await api.removeCartItem(cartId, productId);
        if (mounted.current) setCart(next);
      } catch (err) {
        if (mounted.current) {
          setError(err instanceof Error ? err.message : "Could not remove item.");
        }
        throw err;
      }
    },
    [cartId],
  );

  const reset = useCallback(() => {
    const nextId = resetCartId();
    setCart(null);
    setCartId(nextId);
  }, []);

  const itemCount = useMemo(
    () => (cart?.items ?? []).reduce((sum, line) => sum + line.quantity, 0),
    [cart],
  );

  const value: CartContextValue = {
    cartId,
    cart,
    loading,
    error,
    itemCount,
    refresh,
    addItem,
    removeItem,
    reset,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
