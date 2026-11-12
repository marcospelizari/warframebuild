import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { builds, items, weaponList } from "@/test/fixtures";
import { WeaponPage } from "./Weapon";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string, answer: (url: string) => Response = ok) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => answer(url)));
  const root = createRootRoute();
  const weapon = createRoute({
    getParentRoute: () => root,
    path: "/w/$slug",
    component: function W() {
      return <WeaponPage slug={weapon.useParams().slug} faction={null} />;
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
  return router;
}

function ok(url: string) {
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
  const router = renderAt("/w/soma-prime");
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
