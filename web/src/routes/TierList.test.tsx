import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { TierList } from "@/api/client";
import { weaponList } from "@/test/fixtures";
import { renderPage } from "@/test/render";
import { TierListPage } from "./TierList";

const tiers = (guns: Record<string, TierList["tiers"][number]["guns"]>): TierList => ({
  release: "r1",
  category: "primary",
  fastest: 0.4,
  level: 120,
  factions: 8,
  tiers: [
    ["S", 2],
    ["A", 4],
    ["B", 8],
    ["C", 16],
    ["D", 32],
    ["E", 64],
    ["F", null],
  ].map(([name, up_to]) => ({
    name: name as string,
    up_to: up_to as number | null,
    guns: guns[name as string] ?? [],
  })),
});

const list = tiers({
  S: [{ slug: "soma-prime", kill_time: 0.4, capped: false, partial: true }],
  B: [{ slug: "tigris-prime", kill_time: 2, capped: false, partial: false }],
  F: [{ slug: "soma", kill_time: 30, capped: true, partial: false }],
});

function serve(body: TierList) {
  const fetch = vi.fn(async (url: string) =>
    new Response(JSON.stringify(url.startsWith("/api/tiers/") ? body : weaponList)),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

test("tiers with guns are shown best first with their ranges, marks and kill times", async () => {
  const fetch = serve(list);
  renderPage(() => <TierListPage category="primary" />);
  const bands = await screen.findAllByRole("region");
  expect(bands.map((b) => within(b).getByRole("heading").textContent)).toEqual([
    "Tier S",
    "Tier B",
    "Tier F",
  ]);
  expect(bands[0]).toHaveTextContent("Up to 2× the fastest kill (0.8 s) · 1 gun");
  expect(bands[1]).toHaveTextContent("4–8× the fastest kill (1.6–3.2 s)");
  expect(bands[2]).toHaveTextContent("Over 64× the fastest kill (25.6 s)");
  const soma = within(bands[0]!).getByRole("link", { name: /Soma Prime/ });
  expect(soma).toHaveAttribute("href", "/w/soma-prime");
  expect(soma).toHaveTextContent("0.4 s average kill");
  expect(soma).toHaveTextContent("May be stronger");
  expect(within(bands[2]!).getByRole("link", { name: /Soma/ })).toHaveTextContent("10 s limit");
  expect(screen.getByText("Soma Prime, 0.4 s average kill")).toBeInTheDocument();
  expect(screen.getByText("level 120 Steel Path, 8 factions")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/tiers/primary");
  expect(document.title).toBe("Primary tier list | warframeBuild");
});

test.each(["melee", "constructor"])(
  "an unknown class (%s) asks for one and calls no API for it",
  async (category) => {
    const fetch = serve(list);
    renderPage(() => <TierListPage category={category} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      `There is no tier list for “${category}”`,
    );
    expect(fetch).not.toHaveBeenCalledWith(`/api/tiers/${category}`);
    expect(document.title).toBe("Tier list | warframeBuild");
  },
);

test("no release yet: says the list could not load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.startsWith("/api/tiers/")
        ? new Response(JSON.stringify({ code: "no_release", message: "no builds yet" }), {
            status: 503,
          })
        : new Response(JSON.stringify(weaponList)),
    ),
  );
  renderPage(() => <TierListPage category="primary" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not load the tier list: no builds yet",
  );
});
