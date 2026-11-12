import type {
  Build,
  BuildsResponse,
  ModItem,
  ModList,
  StoredBuild,
  WeaponItem,
  WeaponList,
} from "@/api/client";

const empty = (index: number) => ({ index, mod: null, name: null, rank: null, polarity: null });

export const serration: ModItem = {
  unique_name: "/Serration",
  name: "Serration",
  polarity: "madurai",
  rarity: "UNCOMMON",
  rank: 10,
  drain: 14,
  exilus: false,
  family: null,
  mod_set: null,
  support: "full",
  stats: ["+165% Damage"],
  description: "",
  image: "/img/mods/0123456789abcdef.jpg",
  compatible: true,
  reason: null,
};

export const chamber: ModItem = {
  ...serration,
  unique_name: "/GalvanizedChamber",
  name: "Galvanized Chamber",
  rarity: "RARE",
  stats: ["+80% Multishot", "On Kill:\n+30% Multishot for 20s."],
  image: null,
};

export const build: Build = {
  dataset_hash: "h",
  weapon: { slug: "soma-prime", name: "Soma Prime", category: "primary", weapon_type: "Rifle" },
  form: "incarnon",
  perks: ["Fortress Salvo"],
  slots: [
    { index: 0, mod: "/Serration", name: "Serration", rank: 10, polarity: "madurai" },
    { index: 1, mod: "/GalvanizedChamber", name: "Galvanized Chamber", rank: 10, polarity: "madurai" },
    ...[2, 3, 4, 5, 6, 7].map(empty),
  ],
  exilus: empty(8),
  arcane: { unique_name: "/Merciless", name: "Primary Merciless" },
  bonus_element: { damage_type: "viral", share: 0.6 },
  arsenal: {
    damage: { impact: 2, slash: 6, puncture: 3, viral: 9 },
    total_damage: 20,
    critical_chance: 0.305,
    critical_multiplier: 3,
    status_chance: 0.1,
    multishot: 1,
    fire_rate: 15,
    magazine: 200,
    reload_time: 3,
    beam_ramp_start: null,
  },
  dps: { direct_burst: 48210, direct_sustained: 40000, max_score: 300 },
  headshot: null,
  combat: {
    level: 120,
    cap_s: 10,
    enemies: [
      { name: "Lancer", unique_name: "/Lancer", faction: "Grineer", target: "Body", ttk: 0.5, removed: 1, cost: 0.5 },
      { name: "Bombard", unique_name: "/Bombard", faction: "Grineer", target: "Body", ttk: null, removed: 0.4, cost: 25 },
      { name: "Crewman", unique_name: "/Crewman", faction: "Corpus", target: "Body", ttk: 0.25, removed: 1, cost: 0.25 },
    ],
    factions: [
      { faction: "Grineer", score: 3.54 },
      { faction: "Corpus", score: 0.25 },
    ],
    score: 0.94,
  },
  assumptions: [{ id: "max_rank", text: "Mods at max rank, Orokin Catalyst installed" }],
};

export const stored: StoredBuild = {
  status: "best_found",
  search_scope: [],
  evaluations: 100,
  score: 1,
  forma: {
    capacity: 60,
    used: 58,
    forma: 1,
    exilus: { drain: 0, forma: false, polarity: null },
    regular: [
      { drain: 7, forma: true, polarity: "madurai" },
      { drain: 21, forma: false, polarity: "naramon" },
      ...Array.from({ length: 6 }, () => ({ drain: 0, forma: false, polarity: null })),
    ],
  },
  build,
};

export const items: ModList = {
  dataset_hash: "h",
  weapon: build.weapon,
  mods: [serration, chamber],
  arcanes: [
    {
      unique_name: "/Merciless",
      name: "Primary Merciless",
      rarity: "RARE",
      support: "full",
      stats: [],
      image: "/img/arcanes/fedcba9876543210.png",
      compatible: true,
      reason: null,
    },
  ],
  perks: [],
};

export const builds: BuildsResponse = {
  release: "r",
  dataset_hash: "h",
  weapon: build.weapon,
  elements: [],
  variants: [
    {
      element: null,
      max: stored,
      recommended: stored,
      factions: { Grineer: stored, "The Murmur": stored },
      denominators: {},
    },
  ],
};

const gun = (slug: string, name: string, extra: Partial<WeaponItem> = {}): WeaponItem => ({
  slug,
  name,
  category: "primary",
  weapon_type: "Rifle",
  incarnon: false,
  progenitor: false,
  mastery: 8,
  image: null,
  ...extra,
});

export const weaponList: WeaponList = {
  dataset_hash: "h",
  weapons: [
    gun("soma-prime", "Soma Prime", { incarnon: true, image: "/img/weapons/soma-prime.png" }),
    gun("soma", "Soma"),
    gun("kuva-soma", "Kuva Soma", { progenitor: true }),
    gun("tigris-prime", "Tigris Prime", { weapon_type: "Shotgun" }),
    gun("lex-prime", "Lex Prime", { category: "secondary", weapon_type: "Pistol" }),
    ...Array.from({ length: 31 }, (_, i) => gun(`braton-${i}`, `Braton ${i}`)),
  ],
  excluded: [{ name: "Sirocco", reason: "a Drifter weapon" }],
};
