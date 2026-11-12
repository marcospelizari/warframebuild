import type { components } from "./types";

type Schemas = components["schemas"];
export type Build = Schemas["Build"];
export type CalcRequest = Schemas["CalcRequest"];
export type ApiError = Schemas["ApiError"];
export type BuildsResponse = Schemas["BuildsResponse"];
export type StoredBuild = Schemas["StoredBuild"];
export type Forma = Schemas["Forma"];
export type FormaSlot = Schemas["FormaSlot"];
export type ModList = Schemas["ModList"];
export type ModItem = Schemas["ModItem"];
export type ArcaneItem = Schemas["ArcaneItem"];
export type Polarity = Schemas["Polarity"];
export type DamageType = Schemas["DamageType"];
export type ElementChoice = Schemas["ElementChoice"];
export type PerkTier = Schemas["PerkTier"];
export type VariantBuilds = Schemas["VariantBuilds"];
export type Category = Schemas["Category"];
export type WeaponItem = Schemas["WeaponItem"];
export type WeaponRef = Schemas["WeaponRef"];
export type WeaponList = Schemas["WeaponList"];
export type ExcludedWeapon = Schemas["ExcludedWeapon"];

/** A failed API call: HTTP status plus the API's error code when it sent one. */
export class ApiFailure extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
  ) {
    super(message);
  }
}

async function failure(response: Response, what: string): Promise<ApiFailure> {
  const error = (await response.json().catch(() => null)) as ApiError | null;
  return new ApiFailure(
    error?.message ?? `${what}: ${response.status}`,
    response.status,
    error?.code ?? null,
  );
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw await failure(response, `GET ${url}`);
  return (await response.json()) as T;
}

export function getWeapons(): Promise<WeaponList> {
  return getJson("/api/weapons");
}

export function getBuilds(slug: string): Promise<BuildsResponse> {
  return getJson(`/api/weapons/${encodeURIComponent(slug)}/builds`);
}

export function getMods(slug: string): Promise<ModList> {
  return getJson(`/api/mods?weapon=${encodeURIComponent(slug)}`);
}

/** `signal` cancels a request a newer edit made stale (F7). */
export async function postCalc(body: CalcRequest, signal?: AbortSignal): Promise<Build> {
  const response = await fetch("/api/calc", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure(response, "POST /api/calc");
  return (await response.json()) as Build;
}
