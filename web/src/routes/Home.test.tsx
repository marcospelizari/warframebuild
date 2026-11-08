import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { Home } from "./Home";

afterEach(() => vi.unstubAllGlobals());

test("shows the version from /api/health", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ status: "ok", version: "9.9.9" }))),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Home />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Version 9.9.9")).toBeInTheDocument();
});
