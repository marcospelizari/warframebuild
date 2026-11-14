import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { stored } from "@/test/fixtures";
import { BesideBuild } from "./BesideBuild";

const advised = {
  ...stored,
  score: 1,
  shards: {
    normal: [
      { shard: "crimson" as const, score: 1.1 },
      { shard: "violet" as const, score: 1.15 },
    ],
    tauforged: [{ shard: "crimson" as const, score: 1.2 }],
    conditions: ["Topaz: counted at its cap"],
  },
  auras: [
    { unique_name: "/CP", name: "Corrosive Projection", score: 1.18 },
    { unique_name: "/RA", name: "Rifle Amp", score: 1.05 },
    { unique_name: "/WC", name: "Worthy Comradery", score: 1 },
  ],
};

test("shard steps show each slot's gain and the total; Tauforged switches the chain", () => {
  render(<BesideBuild stored={advised} metric="kill speed" />);
  const shards = screen.getByRole("heading", { name: "Archon Shards" }).parentElement!.parentElement!;
  const rows = within(shards).getAllByRole("listitem");
  expect(rows[0]).toHaveTextContent("Crimson+10%");
  expect(rows[1]).toHaveTextContent("Violet+5%");
  expect(shards).toHaveTextContent("2 shards: +15% (more shards add nothing)");
  expect(shards).toHaveTextContent("Topaz: counted at its cap");
  fireEvent.click(screen.getByRole("button", { name: "Tauforged" }));
  expect(screen.getByRole("button", { name: "Tauforged" })).toHaveAttribute("aria-pressed", "true");
  expect(shards).toHaveTextContent("1 shard: +20%");
});

test("auras best first, the best one tagged", () => {
  render(<BesideBuild stored={advised} metric="kill speed" />);
  const aura = screen.getByRole("heading", { name: "Aura" }).parentElement!;
  const rows = within(aura).getAllByRole("listitem");
  expect(rows[0]).toHaveTextContent("Corrosive ProjectionBest+18%");
  expect(rows[1]).toHaveTextContent("Rifle Amp+5%");
  expect(rows[2]).toHaveTextContent("Worthy Comraderyno gain");
});

test("Primer: shards without an aura card", () => {
  render(<BesideBuild stored={{ ...advised, auras: [] }} metric="priming" />);
  expect(screen.getByRole("heading", { name: "Archon Shards" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Aura" })).toBeNull();
});

test("no shard gains: says so", () => {
  const none = { ...advised, shards: { normal: [], tauforged: [], conditions: [] } };
  render(<BesideBuild stored={none} metric="kill speed" />);
  expect(screen.getByText("No shard helps this build.")).toBeInTheDocument();
});

test("release made before the advice: no section", () => {
  const { container } = render(<BesideBuild stored={stored} metric="kill speed" />);
  expect(container).toBeEmptyDOMElement();
});

test("a build scoring 0 (Primer): no percentages, no section", () => {
  const { container } = render(<BesideBuild stored={{ ...advised, score: 0 }} metric="priming" />);
  expect(container).toBeEmptyDOMElement();
});
