import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { SiteLayout } from "./components/SiteLayout";
import { Home } from "./routes/Home";
import { WeaponPage } from "./routes/Weapon";

const rootRoute = createRootRoute({ component: SiteLayout });
const homeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Home });
const weaponRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/w/$slug",
  component: function Weapon() {
    const { slug } = weaponRoute.useParams();
    return <WeaponPage slug={slug} faction={null} />;
  },
});
// Faction builds have their own URL (G88), e.g. /w/soma-prime/the-murmur.
const factionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/w/$slug/$faction",
  component: function Faction() {
    const { slug, faction } = factionRoute.useParams();
    return <WeaponPage slug={slug} faction={faction} />;
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
