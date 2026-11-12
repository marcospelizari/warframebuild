import type { CSSProperties } from "react";
import type { ArcaneItem } from "@/api/client";
import { arcaneFrame, SLOT_ART } from "./art";
import s from "./ModCard.module.css";

type Props = { arcane: ArcaneItem | null; why?: string | null; onPick?: () => void };

export function ArcaneSlot({ arcane, why = null, onPick }: Props) {
  const vars = {
    "--afr": arcaneFrame(arcane?.rarity ?? null),
    "--ablank": SLOT_ART.arcaneBlank,
  } as CSSProperties;
  const label = (arcane ? `Arcane: ${arcane.name}` : "No arcane") + (why ? `. ${why}` : "");
  const inner = (
    <>
      <span className={s.arcf}>
        {arcane?.image && <img className={s.arcimg} src={arcane.image} alt="" />}
      </span>
      {arcane && <span className={s.arcname}>{arcane.name}</span>}
    </>
  );
  const cls = arcane ? s.arc : `${s.arc} ${s.empty}`;
  return (
    <div className={s.arcrow}>
      {onPick ? (
        <button
          className={`${cls} ${s.pick}`}
          type="button"
          onClick={onPick}
          aria-label={`${label}. Change arcane.`}
          title={why ?? undefined}
          style={vars}
        >
          {inner}
        </button>
      ) : (
        <div className={cls} role="img" aria-label={label} title={why ?? undefined} style={vars}>
          {inner}
        </div>
      )}
    </div>
  );
}
