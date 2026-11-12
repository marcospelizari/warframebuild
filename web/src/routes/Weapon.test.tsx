import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { build, builds, items, weaponList } from "@/test/fixtures";
import { decode, encode, fromBuild } from "@/lib/editor";
import { WeaponPage } from "./Weapon";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string, answer: (url: string, init?: RequestInit) => Response = ok) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => answer(url, init));
  vi.stubGlobal("fetch", fetch);
  const root = createRootRoute();
  const search = (raw: Record<string, unknown>) => (typeof raw.b === "string" ? { b: raw.b } : {});
  const weapon = createRoute({
    getParentRoute: () => root,
    path: "/w/$slug",
    validateSearch: search,
    component: function W() {
      return <WeaponPage slug={weapon.useParams().slug} faction={null} code={weapon.useSearch().b} />;
    },
  });
  const faction = createRoute({
    getParentRoute: () => root,
    path: "/w/$slug/$faction",
    component: function F() {
      const p = faction.useParams();
      return <WeaponPage slug={p.slug} faction={p.faction} />;
    },
  });
  const home = createRoute({ getParentRoute: () => root, path: "/", component: () => <p>home</p> });
  const router = createRouter({
    routeTree: root.addChildren([home, weapon, faction]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, fetch };
}

const edited = {
  ...build,
  slots: [{ ...build.slots[1]!, index: 0 }, ...build.slots.slice(2), { ...build.slots[0]!, mod: null, name: null, index: 7 }],
  combat: { ...build.combat, score: 1.2 },
  dps: { ...build.dps, direct_burst: 40000 },
};

function ok(url: string) {
  if (url === "/api/calc") return new Response(JSON.stringify(edited));
  if (url.startsWith("/api/mods")) return new Response(JSON.stringify(items));
  if (url === "/api/weapons") return new Response(JSON.stringify(weaponList));
  return new Response(JSON.stringify(builds));
}

test("Recommended: header, score over all enemies, grid and stats", async () => {
  renderAt("/w/soma-prime");
  expect(await screen.findByRole("heading", { level: 1, name: "Soma Prime" })).toBeInTheDocument();
  expect(await screen.findByText("Primary rifle, mastery rank 8, Incarnon")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Recommended" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("0.94 s")).toBeInTheDocument();
  expect(screen.getByText(/Average time to kill 3 level 120 Steel Path enemies, body shots/)).toBeInTheDocument();
  expect(screen.getByText("not killed in 10 s (40%)")).toBeInTheDocument();
  expect(screen.getByText("Mods at max rank, Orokin Catalyst installed")).toBeInTheDocument();
  expect(screen.getByText("Best of 100 mod combinations tried; a better one may exist.")).toBeInTheDocument();
  expect(screen.getByText("1 forma")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Serration/ })).toBeInTheDocument();
  expect(document.title).toBe("Soma Prime build: mods, forma, arcane | warframeBuild");
});

test("a faction URL shows that faction's build and kills only", async () => {
  renderAt("/w/soma-prime/grineer");
  expect(await screen.findByRole("heading", { name: "Against Grineer" })).toBeInTheDocument();
  expect(screen.getByText("3.54 s")).toBeInTheDocument();
  expect(screen.queryByText("Crewman")).toBeNull();
  expect(screen.getByRole("link", { name: "Grineer" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Recommended" })).not.toHaveAttribute("aria-current");
  expect(screen.getByRole("link", { name: "Faction builds" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "The Murmur" })).toHaveAttribute("href", "/w/soma-prime/the-murmur");
  expect(document.title).toBe("Soma Prime build against Grineer | warframeBuild");
});

test("the Faction builds tab opens the first faction", async () => {
  const { router } = renderAt("/w/soma-prime");
  fireEvent.click(await screen.findByRole("link", { name: "Faction builds" }));
  expect(await screen.findByRole("heading", { name: "Against Grineer" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/w/soma-prime/grineer");
});

test("an unknown faction says so", async () => {
  renderAt("/w/soma-prime/nope");
  expect(await screen.findByRole("alert")).toHaveTextContent("There is no such faction build");
});

test("an unknown gun says so and links back", async () => {
  const error = { code: "unknown_weapon", message: "no such weapon", field: "slug" };
  renderAt("/w/nope", () => new Response(JSON.stringify(error), { status: 404 }));
  expect(await screen.findByRole("alert")).toHaveTextContent("There is no gun at this address.");
  expect(screen.getByRole("link", { name: "Browse all guns" })).toBeInTheDocument();
});

test("builds not ready: a player-facing message, not the admin one", async () => {
  const error = { code: "no_release", message: "no builds yet: run `uv run wfb build-all`", field: null };
  renderAt("/w/soma-prime", (url) =>
    url.includes("/builds") ? new Response(JSON.stringify(error), { status: 503 }) : ok(url),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Builds are being updated.");
});


test("Why this mod: the opened card says how much slower the kill gets without it", async () => {
  renderAt("/w/soma-prime");
  expect(await screen.findByText("Without it: average kill +0.25 s")).toBeInTheDocument();
});

test("editing: pick a slot, change it, see the difference to the calculated build", async () => {
  const { router, fetch } = renderAt("/w/soma-prime");
  fireEvent.click(await screen.findByRole("button", { name: "Edit build" }));
  await waitFor(() => expect(router.state.location.search).toHaveProperty("b"));
  expect(screen.getByRole("heading", { name: "Your build" })).toBeInTheDocument();
  expect(screen.queryByText(/Without it/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /^Serration.*Change mod\.$/ }));
  const dialog = await screen.findByRole("dialog", { name: "Choose a mod for slot 1" });
  expect(within(dialog).getByRole("button", { name: /Galvanized Chamber/ })).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(within(dialog).getByRole("button", { name: "Leave empty" }));
  expect(await screen.findByText("0.26 s slower than the calculated build", {}, { timeout: 2000 })).toBeInTheDocument();
  expect(screen.getByText("40.0 k (−8.2 k)")).toBeInTheDocument();
  const calls = fetch.mock.calls.filter(([url]) => url === "/api/calc");
  expect(calls).toHaveLength(1); // debounced: one request for the settled edit
  expect(JSON.parse(String(calls[0]![1]!.body)).mods).toEqual(["/GalvanizedChamber"]);
  const code = router.state.location.search as { b?: string };
  expect(decode(code.b!)?.mods).toEqual(["/GalvanizedChamber"]);
  fireEvent.click(screen.getByRole("button", { name: "Back to the calculated build" }));
  expect(await screen.findByRole("heading", { name: "Recommended" })).toBeInTheDocument();
});

test("a shared ?b= link opens the edited build", async () => {
  const code = encode({ ...fromBuild(build), mods: ["/GalvanizedChamber"] });
  renderAt(`/w/soma-prime?b=${code}`);
  expect(await screen.findByRole("heading", { name: "Your build" })).toBeInTheDocument();
  expect(await screen.findByText(/slower than the calculated build/, {}, { timeout: 2000 })).toBeInTheDocument();
});

test("a broken ?b= link falls back to the calculated build with a message", async () => {
  renderAt("/w/soma-prime?b=9.nope");
  expect(await screen.findByText(/This build link could not be opened/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Recommended" })).toBeInTheDocument();
});
