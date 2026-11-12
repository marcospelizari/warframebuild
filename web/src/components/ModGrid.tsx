import type { Build, Forma, ModList } from "@/api/client";
import type { Target } from "@/lib/editor";
import { ArcaneSlot } from "./ArcaneSlot";
import { ModCard } from "./ModCard";
import s from "./ModCard.module.css";

type Props = {
  build: Build;
  forma: Forma | null;
  items: ModList;
  weaponType: string;
  why?: (id: string) => string | null; // F8 line per mod / arcane
  onPick?: (target: Target) => void; // editor
};

/** Arsenal layout: exilus on top, 4 × 2 mods in slot order, arcane below (F3). */
export function ModGrid({ build, forma, items, weaponType, why, onPick }: Props) {
  const mods = new Map(items.mods.map((m) => [m.unique_name, m]));
  const arcanes = new Map(items.arcanes.map((a) => [a.unique_name, a]));
  const find = (id: string | null | undefined) => (id ? (mods.get(id) ?? null) : null);
  const whyOf = (id: string | null | undefined) => (id && why ? why(id) : null);
  const filled = build.slots.filter((x) => x.mod).length;
  return (
    <div className={s.wrap}>
      <div className={s.exrow}>
        <ModCard
          mod={find(build.exilus?.mod)}
          slot={forma?.exilus ?? null}
          label="Exilus"
          exilus
          why={whyOf(build.exilus?.mod)}
          onPick={onPick && (() => onPick({ kind: "exilus" }))}
        />
      </div>
      <div className={s.deck}>
        {build.slots.map((slot, i) => (
          <ModCard
            key={slot.index}
            mod={find(slot.mod)}
            slot={forma?.regular[i] ?? null}
            label={weaponType}
            why={whyOf(slot.mod)}
            // mods stay packed: an empty slot adds after the last mod
            onPick={onPick && (() => onPick({ kind: "mod", index: Math.min(i, filled) }))}
          />
        ))}
      </div>
      <ArcaneSlot
        arcane={build.arcane ? (arcanes.get(build.arcane.unique_name) ?? null) : null}
        why={whyOf(build.arcane?.unique_name)}
        onPick={onPick && (() => onPick({ kind: "arcane" }))}
      />
    </div>
  );
}
