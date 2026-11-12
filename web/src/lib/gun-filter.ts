import type { Category, ExcludedWeapon, WeaponItem } from "@/api/client";

export type Filters = { tab: Category; type: string; incarnon: boolean; progenitor: boolean };

export const NO_FILTERS = { type: "all", incarnon: false, progenitor: false };

/** The type chips of one tab, sorted by name. */
export function typesIn(weapons: WeaponItem[], tab: Category): string[] {
  return [...new Set(weapons.filter((w) => w.category === tab).map((w) => w.weapon_type))].sort();
}

export function browse(weapons: WeaponItem[], f: Filters): WeaponItem[] {
  return weapons.filter(
    (w) =>
      w.category === f.tab &&
      (f.type === "all" || w.weapon_type === f.type) &&
      (!f.incarnon || w.incarnon) &&
      (!f.progenitor || w.progenitor),
  );
}

export type Suggestion =
  | { kind: "gun"; weapon: WeaponItem }
  | { kind: "excluded"; weapon: ExcludedWeapon };

/** Name search: names starting with the text first, then other matches, both by name. */
export function suggest(
  weapons: WeaponItem[],
  excluded: ExcludedWeapon[],
  text: string,
  limit = 7,
): Suggestion[] {
  const q = text.trim().toLocaleLowerCase();
  if (!q) return [];
  const all: Suggestion[] = [
    ...weapons.map((weapon) => ({ kind: "gun" as const, weapon })),
    ...excluded.map((weapon) => ({ kind: "excluded" as const, weapon })),
  ];
  const name = (x: Suggestion) => x.weapon.name.toLocaleLowerCase();
  const starts = (x: Suggestion) => (name(x).startsWith(q) ? 0 : 1);
  return all
    .filter((x) => name(x).includes(q))
    .sort((a, b) => starts(a) - starts(b) || a.weapon.name.localeCompare(b.weapon.name))
    .slice(0, limit);
}

/** "Kuva, Tenet or Coda" wins over "Incarnon" when a gun is both. */
export function tagOf(w: WeaponItem): string | null {
  if (w.progenitor) return "Kuva, Tenet or Coda";
  return w.incarnon ? "Incarnon" : null;
}
