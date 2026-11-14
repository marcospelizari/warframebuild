import type { components } from "./types";

type Schemas = components["schemas"];
export type Build = Schemas["Build"];
export type CalcRequest = Schemas["CalcRequest"];
export type ApiError = Schemas["ApiError"];
export type BuildsResponse = Schemas["BuildsResponse"];
export type StoredBuild = Schemas["StoredBuild"];
export type Primer = Schemas["Primer"];
export type Forma = Schemas["Forma"];
export type FormaSlot = Schemas["FormaSlot"];
export type ModList = Schemas["ModList"];
export type ModItem = Schemas["ModItem"];
export type ArcaneItem = Schemas["ArcaneItem"];
export type Polarity = Schemas["Polarity"];
export type DamageType = Schemas["DamageType"];
export type PerkTier = Schemas["PerkTier"];
export type Category = Schemas["Category"];
export type WeaponItem = Schemas["WeaponItem"];
export type WeaponRef = Schemas["WeaponRef"];
export type WeaponList = Schemas["WeaponList"];
export type ExcludedWeapon = Schemas["ExcludedWeapon"];
export type DataInfo = Schemas["DataInfo"];
export type UpdatesResponse = Schemas["UpdatesResponse"];
export type Update = Schemas["Update"];
export type EntryChange = Schemas["EntryChange"];
export type GunChange = Schemas["GunChange"];
export type BuildChange = Schemas["BuildChange"];
export type TierList = Schemas["TierList"];
export type Tier = Schemas["Tier"];
export type TierGun = Schemas["TierGun"];
export type Source = Schemas["Source"];

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

/** Server-side waits worth trying again; every other failure (bad gun, rate limit, release
 * missing or changed, internal error) is shown at once. */
const TRANSIENT = new Set(["busy", "restarted", "timeout"]);

/** For the query client: network errors and transient codes, at most twice. */
export function shouldRetry(failures: number, error: unknown): boolean {
  if (failures >= 2) return false;
  if (!(error instanceof ApiFailure)) return true;
  return error.code !== null && TRANSIENT.has(error.code);
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

/** The game data every page names in its footer (U4). */
export function getData(): Promise<DataInfo> {
  return getJson("/api/data");
}

export function getUpdates(): Promise<UpdatesResponse> {
  return getJson("/api/updates");
}

export function getTiers(category: Category): Promise<TierList> {
  return getJson(`/api/tiers/${category}`);
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
