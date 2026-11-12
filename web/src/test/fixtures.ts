import type { Build, BuildsResponse, ModItem, ModList, StoredBuild } from "@/api/client";

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
  combat: { level: 120, cap_s: 10, enemies: [], factions: [], score: 1 },
  assumptions: [],
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
  variants: [{ element: null, max: stored, recommended: stored, factions: {}, denominators: {} }],
};
