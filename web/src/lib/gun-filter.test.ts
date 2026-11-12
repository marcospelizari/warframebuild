import { expect, test } from "vitest";
import { weaponList } from "@/test/fixtures";
import { browse, NO_FILTERS, suggest, tagOf, typesIn } from "./gun-filter";

const { weapons, excluded } = weaponList;
const names = (xs: { weapon: { name: string } }[]) => xs.map((x) => x.weapon.name);

test("names that start with the text come first", () => {
  expect(names(suggest(weapons, excluded, "  soma "))).toEqual(["Soma", "Soma Prime", "Kuva Soma"]);
  expect(suggest(weapons, excluded, "   ")).toEqual([]);
});

test("guns we do not build are found too, marked excluded", () => {
  expect(suggest(weapons, excluded, "siro")).toEqual([{ kind: "excluded", weapon: excluded[0] }]);
});

test("filters combine within one tab", () => {
  const f = { tab: "primary" as const, ...NO_FILTERS };
  expect(browse(weapons, f)).toHaveLength(35);
  expect(names(browse(weapons, { ...f, type: "Shotgun" }).map((weapon) => ({ weapon })))).toEqual(["Tigris Prime"]);
  expect(browse(weapons, { ...f, incarnon: true, progenitor: true })).toEqual([]);
  expect(typesIn(weapons, "primary")).toEqual(["Rifle", "Shotgun"]);
});

test("progenitor tag wins over incarnon", () => {
  const [soma] = weapons;
  expect(tagOf(soma!)).toBe("Incarnon");
  expect(tagOf({ ...soma!, progenitor: true })).toBe("Kuva, Tenet or Coda");
});
