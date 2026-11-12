import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { stored } from "@/test/fixtures";
import { StatsPanel } from "./StatsPanel";

test("progenitor bonus, capacity and incarnon perks", () => {
  render(<StatsPanel stored={stored} />);
  expect(screen.getByText("+60% Viral")).toBeInTheDocument();
  expect(screen.getByText("58/60")).toBeInTheDocument();
  expect(screen.getByText("Fortress Salvo")).toBeInTheDocument();
  expect(screen.getByText("INCARNON FORM")).toBeInTheDocument();
});

test("game number style and damage order: physical first, then by size", () => {
  render(<StatsPanel stored={stored} />);
  expect(screen.getByText("30.5%")).toBeInTheDocument();
  expect(screen.getByText("3x")).toBeInTheDocument();
  expect(screen.getByText("48.2 k")).toBeInTheDocument();
  const damage = within(screen.getByText("DAMAGE").nextElementSibling as HTMLElement);
  const names = damage.getAllByRole("term").map((t) => t.textContent);
  expect(names.slice(3)).toEqual(["Puncture", "Slash", "Impact", "Viral(+)", "Total"]);
  expect(damage.getByAltText("Cold")).toBeInTheDocument();
  expect(damage.getByAltText("Toxin")).toBeInTheDocument();
});

test("no bonus, no perks, no layout", () => {
  const build = { ...stored.build, bonus_element: null, perks: [], form: "normal" as const };
  render(<StatsPanel stored={{ ...stored, build, forma: null }} />);
  expect(screen.queryByText(/Progenitor/)).toBeNull();
  expect(screen.queryByText("INCARNON EVOLUTIONS")).toBeNull();
  expect(screen.getByText("Does not fit")).toBeInTheDocument();
});
