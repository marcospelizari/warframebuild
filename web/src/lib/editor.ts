import type { ArcaneItem, Build, CalcRequest, DamageType, ModItem, ModList } from "@/api/client";

/** What the player chose: mods in slot order (no gaps, like /calc), exilus, arcane,
    one perk per Incarnon tier, bonus element. */
export type Choices = {
  mods: string[];
  exilus: string | null;
  arcane: string | null;
  perks: string[];
  element: DamageType | null;
};

export type Target = { kind: "mod"; index: number } | { kind: "exilus" } | { kind: "arcane" };

export const MAX_MODS = 8;

export function fromBuild(build: Build): Choices {
  return {
    mods: build.slots.flatMap((s) => (s.mod ? [s.mod] : [])),
    exilus: build.exilus?.mod ?? null,
    arcane: build.arcane?.unique_name ?? null,
    perks: build.perks,
    element: build.bonus_element?.damage_type ?? null,
  };
}

export function toRequest(weapon: string, c: Choices): CalcRequest {
  return {
    weapon,
    mods: c.mods,
    exilus: c.exilus,
    arcane: c.arcane,
    perks: c.perks,
    bonus_element: c.element,
  };
}

export function sameChoices(a: Choices, b: Choices): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Put `id` (or nothing) at `target`; mods stay packed in slot order. */
export function place(c: Choices, target: Target, id: string | null): Choices {
  if (target.kind === "exilus") return { ...c, exilus: id };
  if (target.kind === "arcane") return { ...c, arcane: id };
  const mods = [...c.mods];
  if (id === null) mods.splice(target.index, 1);
  else if (target.index < mods.length) mods[target.index] = id;
  else mods.push(id);
  return { ...c, mods };
}

// ?b= share code (F1): version, then the choices as base64url JSON with the common
// uniqueName prefixes dropped. The server checks everything again in /calc.
const VERSION = "1";
const MAX_CODE = 2000;
const MOD_PREFIX = "/Lotus/Upgrades/Mods/";
const ARCANE_PREFIX = "/Lotus/Upgrades/CosmeticEnhancers/";

const strip = (id: string, prefix: string) => (id.startsWith(prefix) ? `~${id.slice(prefix.length)}` : id);
const unstrip = (id: string, prefix: string) => (id.startsWith("~") ? prefix + id.slice(1) : id);

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(code: string): string {
  const binary = atob(code.replace(/-/g, "+").replace(/_/g, "/"));
  return new TextDecoder().decode(Uint8Array.from(binary, (ch) => ch.charCodeAt(0)));
}

export function encode(c: Choices): string {
  const body = [
    c.mods.map((m) => strip(m, MOD_PREFIX)),
    c.exilus && strip(c.exilus, MOD_PREFIX),
    c.arcane && strip(c.arcane, ARCANE_PREFIX),
    c.perks,
    c.element,
  ];
  return `${VERSION}.${toBase64Url(JSON.stringify(body))}`;
}

const isText = (x: unknown): x is string => typeof x === "string" && x.length <= 200;
const isTextList = (x: unknown, max: number): x is string[] =>
  Array.isArray(x) && x.length <= max && x.every(isText);

/** null: not a code this version wrote (the page then shows the calculated build). */
export function decode(code: string): Choices | null {
  if (code.length > MAX_CODE || !code.startsWith(`${VERSION}.`)) return null;
  let body: unknown;
  try {
    body = JSON.parse(fromBase64Url(code.slice(VERSION.length + 1)));
  } catch {
    return null;
  }
  if (!Array.isArray(body) || body.length !== 5) return null;
  const [mods, exilus, arcane, perks, element] = body as unknown[];
  if (!isTextList(mods, MAX_MODS) || !isTextList(perks, 4)) return null;
  if ((exilus !== null && !isText(exilus)) || (arcane !== null && !isText(arcane))) return null;
  if (element !== null && !isText(element)) return null;
  return {
    mods: mods.map((m) => unstrip(m, MOD_PREFIX)),
    exilus: exilus === null ? null : unstrip(exilus, MOD_PREFIX),
    arcane: arcane === null ? null : unstrip(arcane, ARCANE_PREFIX),
    perks,
    element: element as DamageType | null,
  };
}

export type Row<T> = { item: T; reason: string | null; current: boolean };

/** Picker rows for a mod slot (F7): usable first, then greyed with why. */
export function modRows(items: ModList, c: Choices, target: Target): Row<ModItem>[] {
  const here = target.kind === "exilus" ? c.exilus : target.kind === "mod" ? c.mods[target.index] : null;
  const others = [...c.mods, c.exilus].filter((m): m is string => !!m && m !== here);
  const byId = new Map(items.mods.map((m) => [m.unique_name, m]));
  const families = new Map<string, string>();
  for (const id of others) {
    const m = byId.get(id);
    if (m?.family) families.set(m.family, m.name);
  }
  const rows = items.mods.map((m) => {
    let reason = m.reason;
    if (!reason && others.includes(m.unique_name)) reason = "Already equipped";
    if (!reason && target.kind === "exilus" && !m.exilus) reason = "Does not fit the exilus slot";
    const clash = m.family ? families.get(m.family) : undefined;
    if (!reason && clash) reason = `Cannot be used with ${clash}`;
    return { item: m, reason, current: m.unique_name === here };
  });
  return rows.sort((a, b) => Number(!!a.reason) - Number(!!b.reason));
}

export function arcaneRows(items: ModList, c: Choices): Row<ArcaneItem>[] {
  return items.arcanes
    .map((a) => ({ item: a, reason: a.reason, current: a.unique_name === c.arcane }))
    .sort((a, b) => Number(!!a.reason) - Number(!!b.reason));
}
