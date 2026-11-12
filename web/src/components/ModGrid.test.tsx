import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { items, stored } from "@/test/fixtures";
import { ModGrid } from "./ModGrid";

test("exilus first, mods in slot order, arcane last", () => {
  render(<ModGrid build={stored.build} forma={stored.forma} items={items} weaponType="Rifle" />);
  const labels = [...screen.getAllByRole("img"), ...screen.getAllByRole("button")].map((e) =>
    e.getAttribute("aria-label"),
  );
  expect(labels[0]).toBe("Empty exilus slot");
  expect(labels).toContain("Arcane: Primary Merciless");
  const cards = screen.getAllByRole("button").map((b) => b.getAttribute("aria-label"));
  expect(cards[0]).toMatch(/^Serration: /);
  expect(cards[1]).toMatch(/^Galvanized Chamber: /);
});

test("drain and polarity come from the forma layout", () => {
  render(<ModGrid build={stored.build} forma={stored.forma} items={items} weaponType="Rifle" />);
  expect(screen.getByRole("button", { name: /^Serration/ })).toHaveAccessibleName(
    "Serration: +165% Damage. Madurai slot, forma, drain 7 (half: polarity matches).",
  );
  expect(screen.getByRole("button", { name: /^Galvanized/ })).toHaveAccessibleName(
    /Naramon slot, drain 21 \(polarity does not match\)\.$/,
  );
  expect(screen.getAllByText("Forma")).toHaveLength(1);
  expect(screen.getAllByText("RIFLE")).toHaveLength(2);
});

test("mod picture and arcane icon use the API URLs", () => {
  const { container } = render(<ModGrid build={stored.build} forma={stored.forma} items={items} weaponType="Rifle" />);
  const srcs = [...container.querySelectorAll("img")].map((i) => i.getAttribute("src"));
  expect(srcs).toEqual(["/img/mods/0123456789abcdef.jpg", "/img/arcanes/fedcba9876543210.png"]);
});

test("a build with no forma layout still shows the mods with their own drain", () => {
  render(<ModGrid build={stored.build} forma={null} items={items} weaponType="Rifle" />);
  expect(screen.getByRole("button", { name: /^Serration/ })).toHaveAccessibleName(
    /No slot polarity, drain 14\.$/,
  );
});
