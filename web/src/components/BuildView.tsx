import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import type { BuildsResponse, DamageType, ModList, StoredBuild, WeaponItem } from "@/api/client";
import { postCalc } from "@/api/client";
import {
  arcaneRows,
  type Choices,
  decode,
  encode,
  fromBuild,
  modRows,
  place,
  sameChoices,
  type Target,
  toRequest,
} from "@/lib/editor";
import { trim } from "@/lib/format";
import { useDebounced } from "@/lib/useDebounced";
import { BuildFrame } from "./BuildFrame";
import { BuildTabs } from "./BuildTabs";
import { EditBar } from "./EditBar";
import { ElementSwitch } from "./ElementSwitch";
import { ModGrid } from "./ModGrid";
import { Picker } from "./Picker";
import { ScoreStrip } from "./ScoreStrip";
import { StatsPanel } from "./StatsPanel";
import { WeaponHeader } from "./WeaponHeader";

const STATUS = {
  optimal: () => "Every possible build was checked: this is the best.",
  best_found: (n: number) =>
    `Best of ${n.toLocaleString("en")} mod combinations tried; a better one may exist.`,
  what_if: () => "What-if: the first element's mods with this element.",
};

/** F8: how much slower the average kill gets without `id` (stored builds only). */
function whyText(stored: StoredBuild, id: string): string | null {
  const without = stored.without[id];
  if (without === undefined || stored.score <= 0) return null;
  if (without <= 0) return "Without it: enemies survive the 10 s";
  const slower = 1 / without - 1 / stored.score;
  if (Math.abs(slower) < 0.005) return "Without it: about the same kill time";
  return `Without it: average kill ${slower > 0 ? "+" : "−"}${trim(Math.abs(slower), 2)} s`;
}

type Props = {
  slug: string;
  data: BuildsResponse;
  items: ModList;
  item: WeaponItem | undefined;
  faction: string | null; // faction name; null = Recommended
  code: string | undefined; // ?b= edited build
};

export function BuildView({ slug, data, items, item, faction, code }: Props) {
  const navigate = useNavigate();
  const [picked, setPicked] = useState(0); // variant shown while not editing
  const [target, setTarget] = useState<Target | null>(null);
  const choices = code ? decode(code) : null;
  const elements = data.variants.flatMap((v) => (v.element ? [v.element] : []));
  const index = choices
    ? Math.max(0, data.variants.findIndex((v) => v.element === choices.element))
    : picked;
  const variant = data.variants[index] ?? data.variants[0]!;
  const base = (faction ? variant.factions[faction] : variant.recommended) ?? variant.recommended;
  const factions = Object.keys(variant.factions);

  const edit = (next: Choices | null) =>
    void navigate({
      to: ".",
      search: { b: next ? encode(next) : undefined },
      replace: true,
      resetScroll: false,
    });

  const settledCode = useDebounced(code);
  const settled = settledCode && choices ? decode(settledCode) : null;
  const changed = !!settled && !sameChoices(settled, fromBuild(base.build));
  const calc = useQuery({
    queryKey: ["calc", slug, settledCode],
    queryFn: ({ signal }) => postCalc(toRequest(slug, settled!), signal),
    enabled: changed,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const editing = !!choices;
  const live = editing && changed && calc.data ? calc.data : null;
  const build = live ?? base.build;
  const forma = live ? live.forma : base.forma;
  const weapon = data.weapon;

  return (
    <main className="mx-auto max-w-[1376px] px-4 pt-5 pb-16 sm:px-8">
      <WeaponHeader
        weapon={weapon}
        item={item}
        onEdit={editing ? undefined : () => edit(fromBuild(base.build))}
      />
      {code && !choices && (
        <p role="alert" className="mt-4 text-center text-soft">
          This build link could not be opened. Showing the calculated build.
        </p>
      )}
      <BuildTabs slug={slug} factions={factions} faction={faction} level={build.combat.level} />
      <div className="mt-3">
        <ElementSwitch
          elements={elements}
          value={variant.element}
          onChange={(e: DamageType) =>
            choices ? edit({ ...choices, element: e }) : setPicked(elements.indexOf(e))
          }
        />
      </div>
      {choices && (
        <EditBar
          tiers={items.perks}
          perks={choices.perks}
          onPerks={(perks) => edit({ ...choices, perks })}
          busy={calc.isFetching || settledCode !== code}
          error={changed && calc.error ? calc.error.message : null}
          onReset={() => edit(null)}
        />
      )}
      <ScoreStrip build={build} faction={faction} baseline={live ? base.build : null} />
      <div className="mt-7 flex flex-wrap items-start gap-9">
        <div className="min-w-0 flex-[999_1_760px]">
          <BuildFrame
            title={editing ? "Your build" : faction ? `Against ${faction}` : "Recommended"}
            note={
              editing
                ? "Your edit, calculated with the same rules as the builds on this site."
                : STATUS[base.status](base.evaluations)
            }
            forma={forma}
          >
            <ModGrid
              build={build}
              forma={forma}
              items={items}
              weaponType={weapon.weapon_type}
              why={editing ? undefined : (id) => whyText(base, id)}
              onPick={choices ? setTarget : undefined}
            />
          </BuildFrame>
        </div>
        <StatsPanel build={build} forma={forma} baseline={live ? base.build : null} />
      </div>
      {choices && target && target.kind === "arcane" && (
        <Picker
          title="Choose an arcane"
          rows={arcaneRows(items, choices)}
          onPick={(id) => {
            edit(place(choices, target, id));
            setTarget(null);
          }}
          onClose={() => setTarget(null)}
        />
      )}
      {choices && target && target.kind !== "arcane" && (
        <Picker
          title={target.kind === "exilus" ? "Choose the exilus mod" : `Choose a mod for slot ${target.index + 1}`}
          rows={modRows(items, choices, target)}
          drain={(m) => m.drain}
          onPick={(id) => {
            edit(place(choices, target, id));
            setTarget(null);
          }}
          onClose={() => setTarget(null)}
        />
      )}
    </main>
  );
}
