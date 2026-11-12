/** Game number style: at most `digits` decimals, no trailing zeros ("2.5", not "2.50"). */
export function trim(value: number, digits: number): string {
  return String(Number(value.toFixed(digits)));
}

/** Large values as "48.2 k" / "1.25 M". */
export function compact(value: number): string {
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)} M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)} k`;
  return String(Math.round(value));
}
