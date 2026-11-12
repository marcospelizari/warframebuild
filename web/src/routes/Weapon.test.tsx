import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { builds, items } from "@/test/fixtures";
import { WeaponPage } from "./Weapon";

afterEach(() => vi.unstubAllGlobals());

function renderPage(answer: (url: string) => Response) {
  const fetch = vi.fn(async (url: string) => answer(url));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <WeaponPage slug="soma-prime" />
    </QueryClientProvider>,
  );
  return fetch;
}

const ok = (url: string) =>
  new Response(JSON.stringify(url.startsWith("/api/mods") ? items : builds));

test("shows the Recommended build from the stored builds and the mod list", async () => {
  const fetch = renderPage(ok);
  expect(await screen.findByRole("heading", { name: "Soma Prime" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Serration/ })).toBeInTheDocument();
  expect(screen.getByText("58/60")).toBeInTheDocument();
  const urls = fetch.mock.calls.map(([url]) => url).sort();
  expect(urls).toEqual(["/api/mods?weapon=soma-prime", "/api/weapons/soma-prime/builds"]);
});

test("shows the API error message", async () => {
  const error = { code: "no_release", message: "no builds yet", field: null };
  renderPage((url) =>
    url.startsWith("/api/mods") ? ok(url) : new Response(JSON.stringify(error), { status: 503 }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("no builds yet");
});
