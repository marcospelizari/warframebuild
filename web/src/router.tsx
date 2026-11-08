import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import { Home } from "./routes/Home";

const rootRoute = createRootRoute({ component: Outlet });
const homeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Home });

export const router = createRouter({ routeTree: rootRoute.addChildren([homeRoute]) });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
