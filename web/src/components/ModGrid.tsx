import type { ModList, StoredBuild } from "@/api/client";
import { ArcaneSlot } from "./ArcaneSlot";
import { ModCard } from "./ModCard";
import s from "./ModCard.module.css";

type Props = { stored: StoredBuild; items: ModList; weaponType: string };

/** Arsenal layout: exilus on top, 4 × 2 mods in slot order, arcane below (F3). */
export function ModGrid({ stored, items, weaponType }: Props) {
  const mods = new Map(items.mods.map((m) => [m.unique_name, m]));
  const arcanes = new Map(items.arcanes.map((a) => [a.unique_name, a]));
  const { build, forma } = stored;
  const find = (id: string | null | undefined) => (id ? (mods.get(id) ?? null) : null);
  return (
    <div className={s.wrap}>
      <div className={s.exrow}>
        <ModCard mod={find(build.exilus?.mod)} slot={forma?.exilus ?? null} label="Exilus" exilus />
      </div>
      <div className={s.deck}>
        {build.slots.map((slot, i) => (
          <ModCard key={slot.index} mod={find(slot.mod)} slot={forma?.regular[i] ?? null} label={weaponType} />
        ))}
      </div>
      <ArcaneSlot arcane={build.arcane ? (arcanes.get(build.arcane.unique_name) ?? null) : null} />
    </div>
  );
}
