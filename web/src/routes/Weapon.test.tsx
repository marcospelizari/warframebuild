import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Build } from "@/api/client";
import { WeaponPage } from "./Weapon";

afterEach(() => vi.unstubAllGlobals());

const build: Build = {
  dataset_hash: "h",
  weapon: { slug: "soma-prime", name: "Soma Prime", category: "primary", weapon_type: "Rifle" },
  form: "incarnon",
  perks: [],
  slots: [{ index: 0, mod: null, name: null, rank: null, polarity: null }],
  bonus_element: null,
  arsenal: {
    damage: { slash: 6 },
    total_damage: 12,
    critical_chance: 0.3,
    critical_multiplier: 3,
    status_chance: 0.1,
    multishot: 1,
    fire_rate: 15,
    magazine: 200,
    reload_time: 3,
    beam_ramp_start: null,
  },
  dps: { direct_burst: 288, direct_sustained: 235.1 },
  assumptions: [{ id: "max_rank", text: "Mods at max rank" }],
};

function renderPage(response: Response) {
  const fetch = vi.fn(async () => response);
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <WeaponPage slug="soma-prime" />
    </QueryClientProvider>,
  );
  return fetch;
}

test("posts the slug to /api/calc and lists the numbers", async () => {
  const fetch = renderPage(new Response(JSON.stringify(build)));
  expect(await screen.findByText("Soma Prime")).toBeInTheDocument();
  expect(screen.getByText("288.00")).toBeInTheDocument();
  expect(screen.getByText("Form: incarnon")).toBeInTheDocument();
  expect(screen.getByText("Mods at max rank")).toBeInTheDocument();
  const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
  expect(JSON.parse(init.body as string)).toEqual({ weapon: "soma-prime", mods: [] });
});

test("shows the API error message", async () => {
  const error = { code: "unknown_weapon", message: "no such weapon", field: "weapon" };
  renderPage(new Response(JSON.stringify(error), { status: 404 }));
  expect(await screen.findByRole("alert")).toHaveTextContent("no such weapon");
});
