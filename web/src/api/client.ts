import type { components } from "./types";

export type Health = components["schemas"]["Health"];

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) throw new Error(`GET /api/health: ${response.status}`);
  return (await response.json()) as Health;
}
