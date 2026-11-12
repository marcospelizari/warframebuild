import type { DamageType } from "@/api/client";

// Wiki card art served by /img/art (known folders and names only, S2).
const art = (folder: string, name: string) => `url(/img/art/${folder}/${name})`;
const card = (name: string) => art("mod-card", name);

export type CardParts = { bg: string; top: string; bottom: string; side: string; tab: string };

const parts = (metal: string): CardParts => ({
  bg: card(`${metal}Background.webp`),
  top: card(`${metal}FrameTop.webp`),
  bottom: card(`${metal}FrameBottom.webp`),
  side: card(`${metal}SideLight.png`),
  tab: card(`${metal}LowerTab.webp`),
});

export const COMMON_PARTS = parts("Bronze");

export const RARITY_PARTS: Record<string, CardParts> = {
  COMMON: COMMON_PARTS,
  UNCOMMON: parts("Silver"),
  RARE: parts("Gold"),
  LEGENDARY: parts("Legendary"),
};

export const GALVANIZED_PARTS: CardParts = {
  ...parts("Legendary"),
  top: card("GalvanizedFrameTop.webp"),
  bottom: card("GalvanizedFrameBottom.webp"),
};

export const AMALGAM_PARTS: CardParts = {
  ...parts("Legendary"),
  top: card("AmalgamFrameTop.png"),
  bottom: card("AmalgamFrameBottom.webp"),
};

export const SLOT_ART = {
  placeholder: art("mod-slot", "warframe_placeholder.png"),
  exilus: art("mod-slot", "icon-exilus.png"),
  arcaneBlank: art("arcane", "ArcaneBlank.png"),
};

const ARCANE_METAL: Record<string, string> = {
  COMMON: "Common",
  UNCOMMON: "Uncommon",
  RARE: "Rare",
  LEGENDARY: "Legendary",
};

export function arcaneFrame(rarity: string | null): string {
  return art("arcane", `ArcaneBackground${ARCANE_METAL[rarity ?? ""] ?? "Rare"}.png`);
}

export function damageIcon(type: DamageType): string | null {
  if (type === "tau") return null; // no saved symbol
  return `/img/art/damage/${type.charAt(0).toUpperCase()}${type.slice(1)}Symbol.png`;
}
