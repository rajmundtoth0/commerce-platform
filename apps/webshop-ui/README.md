# webshop-ui

Customer-facing storefront for the commerce platform. React 18 + TypeScript +
Vite. It talks **only** to the `webshop-api` (a BFF); it never calls the other
backend services directly.

## Pages

- `/` — hero, featured product slider, and the full product grid.
- `/product/:id` — product detail with quantity selector and add-to-cart.
- `/cart` — line items, totals, remove, and a checkout link.
- `/checkout` — order summary, email entry, and order confirmation.

## Development

```bash
npm install
npm run dev      # Vite dev server on http://localhost:5173
```

In dev, requests to `/api/*` are proxied to `http://localhost:8000`
(the `webshop-api`) — see `vite.config.ts`. Run the BFF locally on port 8000.

## Build & lint

```bash
npm run build    # tsc type-check + vite production build -> dist/
npm run lint     # eslint (typescript-eslint), zero warnings allowed
npm run preview  # serve the production build locally
```

## Configuration

| Variable            | Default | Purpose                                              |
| ------------------- | ------- | ---------------------------------------------------- |
| `VITE_API_BASE_URL` | `/api`  | Base URL for all `webshop-api` requests.             |

In local dev leave it as the default `/api` so the Vite proxy handles routing.
In production the bundle is served by nginx (`nginx.conf`), which serves the
static files and proxies `/api/` to the `webshop-api` service.

## Cart identity

The storefront is anonymous. A `cartId` (`crypto.randomUUID()`) is generated and
persisted in `localStorage` on first load and sent to the cart endpoints. An
email is collected only at checkout. After a successful order the local cart id
is rotated.

## Money

Prices are integer minor units. Use `formatMoney(amount_minor, currency)` from
`src/lib/money.ts` to render them (e.g. `formatMoney(1999, "USD")` -> `"$19.99"`).
