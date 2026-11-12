import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { SiteLayout } from "./components/SiteLayout";
import { Home } from "./routes/Home";
import { WeaponPage } from "./routes/Weapon";

const rootRoute = createRootRoute({ component: SiteLayout });
const homeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Home });
// ?b= carries an edited build (F1); anything else in the query is dropped.
const search = (raw: Record<string, unknown>): { b?: string } =>
  typeof raw.b === "string" ? { b: raw.b } : {};

const weaponRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/w/$slug",
  validateSearch: search,
  component: function Weapon() {
    const { slug } = weaponRoute.useParams();
    const { b } = weaponRoute.useSearch();
    return <WeaponPage slug={slug} faction={null} code={b} />;
  },
});
// Faction builds have their own URL (G88), e.g. /w/soma-prime/the-murmur.
const factionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/w/$slug/$faction",
  validateSearch: search,
  component: function Faction() {
    const { slug, faction } = factionRoute.useParams();
    const { b } = factionRoute.useSearch();
    return <WeaponPage slug={slug} faction={faction} code={b} />;
  },
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([homeRoute, weaponRoute, factionRoute]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
