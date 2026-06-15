// Domain types mirrored from the webshop-api (BFF) responses.

export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string;
  active: boolean;
  featured: boolean;
}

export type ProductWithPrice = Product & {
  currency: string | null;
  amount_minor: number | null;
};

export type ProductDetail = ProductWithPrice;

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface CartLine {
  product_id: string;
  name: string;
  quantity: number;
  currency?: string;
  unit_amount_minor?: number;
  line_amount_minor?: number;
}

export interface Cart {
  cart_id: string;
  user_id?: string;
  currency: string;
  items: CartLine[];
  total_amount_minor: number;
  has_unpriced_items: boolean;
}

export interface OrderItem {
  product_id: string;
  name: string;
  quantity: number;
  unit_amount_minor: number;
  line_amount_minor: number;
}

export interface Order {
  id: string;
  status: string;
  currency: string;
  total_amount_minor: number;
  items: OrderItem[];
}
