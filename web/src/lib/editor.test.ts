import { expect, test } from "vitest";
import type { ModItem } from "@/api/client";
import { chamber, items, serration } from "@/test/fixtures";
import { type Choices, decode, encode, modRows, place } from "./editor";

const choices: Choices = {
  mods: ["/Lotus/Upgrades/Mods/Rifle/WeaponDamageAmountMod", "/Other/Mod"],
  exilus: null,
  arcane: "/Lotus/Upgrades/CosmeticEnhancers/Offensive/PrimaryDamageOnKill",
  perks: ["Fortress Salvo"],
  element: "viral",
};

test("share code round-trips and stays short", () => {
  const code = encode(choices);
  expect(code.startsWith("1.")).toBe(true);
  expect(code).not.toMatch(/[+/=]/);
  expect(decode(code)).toEqual(choices);
});

test("anything this version did not write is refused", () => {
  expect(decode("2.abc")).toBeNull();
  expect(decode("1.!!!")).toBeNull();
  expect(decode(`1.${btoa(JSON.stringify({ mods: [] }))}`)).toBeNull();
  expect(decode(`1.${btoa(JSON.stringify([Array(9).fill("x"), null, null, [], null]))}`)).toBeNull();
  expect(decode(`1.${"a".repeat(3000)}`)).toBeNull();
});

test("mods stay packed in slot order", () => {
  const c: Choices = { ...choices, mods: ["a", "b", "c"] };
  expect(place(c, { kind: "mod", index: 1 }, null).mods).toEqual(["a", "c"]);
  expect(place(c, { kind: "mod", index: 1 }, "x").mods).toEqual(["a", "x", "c"]);
  expect(place(c, { kind: "mod", index: 3 }, "x").mods).toEqual(["a", "b", "c", "x"]);
  expect(place(c, { kind: "exilus" }, "e").exilus).toBe("e");
});

test("picker greys out what cannot go here, with the reason", () => {
  const split: ModItem = { ...serration, unique_name: "/Split", name: "Split Chamber", family: "multishot" };
  const galv = { ...chamber, family: "multishot" };
  const util: ModItem = { ...serration, unique_name: "/Util", name: "Vigilante Supplies", exilus: true };
  const bad: ModItem = { ...serration, unique_name: "/Bad", name: "Bad", compatible: false, reason: "does not fit Soma Prime" };
  const list = { ...items, mods: [serration, galv, split, util, bad] };
  const c: Choices = { ...choices, mods: ["/Serration", "/GalvanizedChamber"], exilus: null };
  const rows = modRows(list, c, { kind: "mod", index: 2 });
  const why = Object.fromEntries(rows.map((r) => [r.item.name, r.reason]));
  expect(why).toEqual({
    "Vigilante Supplies": null,
    Serration: "Already equipped",
    "Galvanized Chamber": "Already equipped",
    "Split Chamber": "Cannot be used with Galvanized Chamber",
    Bad: "does not fit Soma Prime",
  });
  expect(rows[0]!.item.name).toBe("Vigilante Supplies"); // usable first
  const exilus = modRows(list, c, { kind: "exilus" });
  expect(exilus.find((r) => r.item.name === "Split Chamber")?.reason).toBe("Does not fit the exilus slot");
  const own = modRows(list, c, { kind: "mod", index: 1 }); // the slot's own mod is not a clash
  expect(own.find((r) => r.item.name === "Galvanized Chamber")).toMatchObject({ reason: null, current: true });
});
