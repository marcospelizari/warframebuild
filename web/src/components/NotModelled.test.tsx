import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { stored } from "@/test/fixtures";
import type { BuildsResponse } from "@/api/client";
import { NotModelled } from "./NotModelled";

const entries: BuildsResponse["not_modelled"] = [
  { kind: "perk", name: "Dread Shot", support: "partial", text: ["+20% on headshot kill"] },
  { kind: "mod", name: "Hata-Satya", support: "unsupported", text: ["Each hit +1.2% crit"] },
  { kind: "arcane", name: "Primary Frostbite", support: "unsupported", text: ["On kill"] },
];

test("closed line names two entries and counts the rest; open shows the text", () => {
  render(<NotModelled all={entries} build={stored.build} />);
  expect(screen.getByText("Dread Shot, Hata-Satya")).toBeInTheDocument();
  expect(screen.getByText("(+1 more)")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Dread Shot, Hata-Satya"));
  expect(screen.getByText("Each hit +1.2% crit")).toBeInTheDocument();
  expect(screen.getByText("Incarnon evolution, partly calculated")).toBeInTheDocument();
});

test("nothing left out: no line", () => {
  const { container } = render(<NotModelled all={[]} build={stored.build} />);
  expect(container).toBeEmptyDOMElement();
});

test("an entry already in the build on screen is not listed", () => {
  const build = { ...stored.build, perks: ["Dread Shot"] };
  render(<NotModelled all={entries} build={build} />);
  expect(screen.getByText("Hata-Satya, Primary Frostbite")).toBeInTheDocument();
  expect(screen.queryByText(/Dread Shot/)).toBeNull();
});
