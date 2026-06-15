/**
 * Format an integer minor-unit amount into a localized currency string.
 * e.g. formatMoney(1999, "USD") -> "$19.99"
 *
 * Returns a placeholder when the amount or currency is unavailable.
 */
export function formatMoney(
  amountMinor: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (amountMinor == null || currency == null) {
    return "—";
  }

  try {
    const formatter = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    });
    // Intl uses the locale's default fraction digits for the currency.
    const fractionDigits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
    const major = amountMinor / 10 ** fractionDigits;
    return formatter.format(major);
  } catch {
    // Unknown currency code: fall back to a plain two-decimal representation.
    return `${(amountMinor / 100).toFixed(2)} ${currency}`;
  }
}
