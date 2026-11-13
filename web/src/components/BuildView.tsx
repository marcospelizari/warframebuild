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
  showChoices,
  type Target,
  toRequest,
} from "@/lib/editor";
import { PRIMER } from "@/lib/faction";
import { trim } from "@/lib/format";
import { useDebounced } from "@/lib/useDebounced";
import { BuildFrame } from "./BuildFrame";
import { BuildTabs } from "./BuildTabs";
import { EditBar } from "./EditBar";
import { ElementSwitch } from "./ElementSwitch";
import { ModGrid } from "./ModGrid";
import { NotModelled } from "./NotModelled";
import { Picker } from "./Picker";
import { PrimerStrip } from "./PrimerStrip";
import { ScoreStrip } from "./ScoreStrip";
import { StatsPanel } from "./StatsPanel";
import { WeaponHeader } from "./WeaponHeader";

const STATUS = {
  optimal: () => "Every possible build was checked: this is the best.",
  best_found: (n: number) =>
    `Best of ${n.toLocaleString("en")} mod combinations tried; a better one may exist.`,
  what_if: () => "What-if: the first element's mods with this element.",
};

/** F8 for the Primer build: its score is the extra follow-up damage it gives. */
function primerWhy(stored: StoredBuild, id: string): string | null {
  const without = stored.without[id];
  if (without === undefined || stored.score <= 0) return null;
  const lost = 1 - without / stored.score;
  if (Math.abs(lost) < 0.005) return "Without it: about the same priming";
  return `Without it: priming ${lost > 0 ? "−" : "+"}${Math.round(Math.abs(lost) * 100)}%`;
}

/** F8: how much slower the average kill gets without `id` (stored builds only). */
function whyText(stored: StoredBuild, id: string): string | null {
  const without = stored.without[id];
  // Scores are 1 / combat cost, so both are above 0.
  if (without === undefined || without <= 0 || stored.score <= 0) return null;
  const slower = 1 / without - 1 / stored.score;
  if (Math.abs(slower) < 0.005) return "Without it: about the same kill time";
  return `Without it: average kill ${slower > 0 ? "+" : "−"}${trim(Math.abs(slower), 2)} s`;
}

type Props = {
  slug: string;
  data: BuildsResponse;
  items: ModList;
  item: WeaponItem | undefined;
  faction: string | null; // faction name, PRIMER, or null = Recommended
  code: string | undefined; // ?b= edited build
};

export function BuildView({ slug, data, items, item, faction, code }: Props) {
  const navigate = useNavigate();
  const [picked, setPicked] = useState(0); // variant shown while not editing
  const [target, setTarget] = useState<Target | null>(null);
  // The Primer tab is not editable (/calc scores kill times, not priming): ?b= is ignored.
  const choices = code && faction !== PRIMER ? decode(code) : null;
  const elements = data.variants.flatMap((v) => (v.element ? [v.element] : []));
  const index = choices
    ? Math.max(0, data.variants.findIndex((v) => v.element === choices.element))
    : picked;
  const variant = data.variants[index] ?? data.variants[0]!;
  const primer = faction === PRIMER ? (variant.primer ?? null) : null;
  const versus = faction === PRIMER ? null : faction; // a faction build's faction
  const base = primer
    ? primer.build
    : ((versus ? variant.factions[versus] : variant.recommended) ?? variant.recommended);
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
  // Numbers and layout count only when /calc answered for the picks on screen.
  const unchanged = !choices || sameChoices(choices, fromBuild(base.build));
  const fresh =
    changed && settledCode === code && calc.data && !calc.isPlaceholderData ? calc.data : null;
  const result = unchanged ? base.build : fresh;
  const pending = !result;
  const numbers = result ?? calc.data ?? base.build; // last known while waiting, dimmed
  const forma = result === base.build ? base.forma : (fresh?.forma ?? null);
  const build = choices ? showChoices(numbers, choices, items) : base.build;
  const live = fresh && !unchanged ? fresh : null; // compared with the calculated build
  // An error counts only for the picks on screen: a newer edit is not sent yet.
  const failed = pending && settledCode === code ? calc.error : null;
  const weapon = data.weapon;

  return (
    <main className="mx-auto max-w-[1376px] px-4 pt-5 pb-16 sm:px-8">
      <WeaponHeader
        weapon={weapon}
        item={item}
        good={!!data.good_primer}
        onEdit={editing || primer ? undefined : () => edit(fromBuild(base.build))}
      />
      {code && !choices && faction !== PRIMER && (
        <p role="alert" className="mt-4 text-center text-soft">
          This build link could not be opened. Showing the calculated build.
        </p>
      )}
      <BuildTabs
        slug={slug}
        factions={factions}
        faction={primer ? PRIMER : versus}
        level={build.combat.level}
        primer={!!data.variants[0]?.primer}
      />
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
          busy={pending && !failed}
          error={failed ? `Could not calculate this edit: ${failed.message}` : null}
          onReset={() => edit(null)}
        />
      )}
      {primer ? (
        <PrimerStrip primer={primer} />
      ) : (
        <div className={pending ? "opacity-50" : undefined} aria-busy={pending}>
          <ScoreStrip build={build} faction={versus} baseline={live ? base.build : null} />
        </div>
      )}
      <div className="mt-7 flex flex-wrap items-start gap-9">
        <div className="min-w-0 flex-[999_1_760px]">
          <BuildFrame
            title={
              editing ? "Your build" : primer ? "Primer" : versus ? `Against ${versus}` : "Recommended"
            }
            note={
              editing
                ? "Your edit, calculated with the same rules as the builds on this site."
                : STATUS[base.status](base.evaluations)
            }
            forma={forma}
            pending={pending}
          >
            <ModGrid
              build={build}
              forma={forma}
              items={items}
              weaponType={weapon.weapon_type}
              why={
                editing ? undefined : (id) => (primer ? primerWhy(base, id) : whyText(base, id))
              }
              onPick={choices ? setTarget : undefined}
            />
            <NotModelled all={data.not_modelled} build={build} />
          </BuildFrame>
        </div>
        <StatsPanel
          build={build}
          forma={forma}
          baseline={live ? base.build : null}
          pending={pending}
          tiers={items.perks}
        />
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
