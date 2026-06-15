import type {
  Cart,
  Order,
  Product,
  ProductDetail,
  ProductListResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiError(0, "Network error: could not reach the server.");
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data: unknown = await response.json();
      if (
        data &&
        typeof data === "object" &&
        "detail" in data &&
        typeof (data as { detail: unknown }).detail === "string"
      ) {
        detail = (data as { detail: string }).detail;
      }
    } catch {
      // Ignore JSON parse failures; keep the default detail.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  getFeatured(signal?: AbortSignal): Promise<Product[]> {
    return request<Product[]>("/catalog/featured", { signal });
  },

  getProducts(
    params: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<ProductListResponse> {
    const search = new URLSearchParams();
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.offset !== undefined) search.set("offset", String(params.offset));
    const qs = search.toString();
    return request<ProductListResponse>(
      `/catalog/products${qs ? `?${qs}` : ""}`,
      { signal },
    );
  },

  getProduct(id: string, signal?: AbortSignal): Promise<ProductDetail> {
    return request<ProductDetail>(`/catalog/products/${encodeURIComponent(id)}`, {
      signal,
    });
  },

  getCart(cartId: string, signal?: AbortSignal): Promise<Cart> {
    return request<Cart>(`/cart/${encodeURIComponent(cartId)}`, { signal });
  },

  addCartItem(
    cartId: string,
    productId: string,
    quantity: number,
  ): Promise<Cart> {
    return request<Cart>(`/cart/${encodeURIComponent(cartId)}/items`, {
      method: "POST",
      body: { product_id: productId, quantity },
    });
  },

  removeCartItem(cartId: string, productId: string): Promise<Cart> {
    return request<Cart>(
      `/cart/${encodeURIComponent(cartId)}/items/${encodeURIComponent(productId)}`,
      { method: "DELETE" },
    );
  },

  checkout(cartId: string, email: string): Promise<Order> {
    return request<Order>(`/checkout/${encodeURIComponent(cartId)}`, {
      method: "POST",
      body: { email },
    });
  },
};
