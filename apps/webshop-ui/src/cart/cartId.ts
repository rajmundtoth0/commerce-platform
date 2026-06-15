const STORAGE_KEY = "webshop_cart_id";

/**
 * Return the persisted anonymous cart id, generating and storing a new one
 * on first load. Falls back to an in-memory id if localStorage is unavailable.
 */
export function getOrCreateCartId(): string {
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) {
      return existing;
    }
    const generated = crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, generated);
    return generated;
  } catch {
    // Private mode / storage disabled: use a session-only id.
    return crypto.randomUUID();
  }
}

export function resetCartId(): string {
  const generated = crypto.randomUUID();
  try {
    window.localStorage.setItem(STORAGE_KEY, generated);
  } catch {
    // Ignore storage failures.
  }
  return generated;
}
