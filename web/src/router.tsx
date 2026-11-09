import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import { Home } from "./routes/Home";
import { WeaponPage } from "./routes/Weapon";

const rootRoute = createRootRoute({ component: Outlet });
const homeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Home });
const weaponRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/w/$slug",
  component: function Weapon() {
    const { slug } = weaponRoute.useParams();
    return <WeaponPage slug={slug} />;
  },
});

export const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute, weaponRoute]) });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
