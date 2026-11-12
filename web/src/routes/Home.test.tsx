import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { weaponList } from "@/test/fixtures";
import { renderPage } from "@/test/render";
import { Home } from "./Home";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(weaponList))));
});
afterEach(() => vi.unstubAllGlobals());

const search = () => screen.findByRole("searchbox", { name: "Gun name" });

test("suggests guns as you type, with links to their pages", async () => {
  renderPage(Home);
  fireEvent.change(await search(), { target: { value: "soma" } });
  const list = await screen.findByRole("list", { name: "Matching guns" });
  const links = within(list).getAllByRole("link");
  expect(links.map((l) => l.textContent)).toEqual([
    expect.stringContaining("Soma"),
    expect.stringContaining("Soma Prime"),
    expect.stringContaining("Kuva Soma"),
  ]);
  expect(links[0]).toHaveAttribute("href", "/w/soma");
});

test("an excluded gun shows why it has no builds, without a link", async () => {
  renderPage(Home);
  fireEvent.change(await search(), { target: { value: "sirocco" } });
  const list = await screen.findByRole("list", { name: "Matching guns" });
  expect(within(list).getByText("No builds: a Drifter weapon")).toBeInTheDocument();
  expect(within(list).queryByRole("link")).toBeNull();
});

test("no match tells the player what to do; clear empties the box", async () => {
  renderPage(Home);
  const box = await search();
  fireEvent.change(box, { target: { value: "zzz" } });
  expect(await screen.findByText(/No gun by that name/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(box).toHaveValue("");
});

test("Enter opens the first matching gun", async () => {
  const router = renderPage(Home);
  const box = await search();
  fireEvent.change(box, { target: { value: "tigris" } });
  await screen.findByRole("list", { name: "Matching guns" });
  fireEvent.submit(box.closest("form") as HTMLFormElement);
  expect(await screen.findByText("weapon page")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/w/tigris-prime");
});

test("tiles: 30 first, filters, show all, empty result", async () => {
  renderPage(Home);
  expect(await screen.findByText("35 of 35 primaries")).toBeInTheDocument();
  const grid = () => screen.getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/w/"));
  expect(grid()).toHaveLength(30);
  fireEvent.click(screen.getByRole("button", { name: "Show all 35 guns" }));
  expect(grid()).toHaveLength(35);
  fireEvent.click(screen.getByRole("button", { name: "Shotgun" }));
  expect(grid().map((l) => l.textContent)).toEqual([expect.stringContaining("Tigris Prime")]);
  fireEvent.click(screen.getByRole("button", { name: "Incarnon" }));
  expect(screen.getByText("No gun matches these filters.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByText("35 of 35 primaries")).toBeInTheDocument();
});

test("secondary tab and tile text", async () => {
  renderPage(Home);
  await screen.findByText("35 of 35 primaries");
  fireEvent.click(screen.getByRole("button", { name: /^Secondary/ }));
  expect(screen.getByText("1 of 1 secondaries")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Lex Prime/ })).toHaveTextContent("Pistol, MR 8");
});
