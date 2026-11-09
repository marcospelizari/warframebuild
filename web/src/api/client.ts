import type { components } from "./types";

type Schemas = components["schemas"];
export type Health = Schemas["Health"];
export type Build = Schemas["Build"];
export type CalcRequest = Schemas["CalcRequest"];
export type ApiError = Schemas["ApiError"];

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) throw new Error(`GET /api/health: ${response.status}`);
  return (await response.json()) as Health;
}

export async function postCalc(body: CalcRequest): Promise<Build> {
  const response = await fetch("/api/calc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as ApiError | null;
    throw new Error(error?.message ?? `POST /api/calc: ${response.status}`);
  }
  return (await response.json()) as Build;
}
