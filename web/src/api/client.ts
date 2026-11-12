import type { components } from "./types";

type Schemas = components["schemas"];
export type Health = Schemas["Health"];
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

async function failure(response: Response, what: string): Promise<Error> {
  const error = (await response.json().catch(() => null)) as ApiError | null;
  return new Error(error?.message ?? `${what}: ${response.status}`);
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw await failure(response, `GET ${url}`);
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return getJson("/api/health");
}

export function getBuilds(slug: string): Promise<BuildsResponse> {
  return getJson(`/api/weapons/${encodeURIComponent(slug)}/builds`);
}

export function getMods(slug: string): Promise<ModList> {
  return getJson(`/api/mods?weapon=${encodeURIComponent(slug)}`);
}

export async function postCalc(body: CalcRequest): Promise<Build> {
  const response = await fetch("/api/calc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure(response, "POST /api/calc");
  return (await response.json()) as Build;
}
