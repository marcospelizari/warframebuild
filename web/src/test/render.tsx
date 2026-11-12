import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import type { JSX } from "react";

/** Renders `Page` at "/" inside a memory router (so links work) and a fresh query client. */
export function renderPage(Page: () => JSX.Element) {
  const root = createRootRoute();
  const home = createRoute({ getParentRoute: () => root, path: "/", component: Page });
  const weapon = createRoute({
    getParentRoute: () => root,
    path: "/w/$slug",
    component: () => <p>weapon page</p>,
  });
  const router = createRouter({
    routeTree: root.addChildren([home, weapon]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}
