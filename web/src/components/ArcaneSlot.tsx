import type { CSSProperties } from "react";
import type { ArcaneItem } from "@/api/client";
import { arcaneFrame, SLOT_ART } from "./art";
import s from "./ModCard.module.css";

export function ArcaneSlot({ arcane }: { arcane: ArcaneItem | null }) {
  const vars = {
    "--afr": arcaneFrame(arcane?.rarity ?? null),
    "--ablank": SLOT_ART.arcaneBlank,
  } as CSSProperties;
  return (
    <div className={s.arcrow}>
      <div
        className={arcane ? s.arc : `${s.arc} ${s.empty}`}
        role="img"
        aria-label={arcane ? `Arcane: ${arcane.name}` : "No arcane"}
        style={vars}
      >
        <span className={s.arcf}>
          {arcane?.image && <img className={s.arcimg} src={arcane.image} alt="" />}
        </span>
        {arcane && <span className={s.arcname}>{arcane.name}</span>}
      </div>
    </div>
  );
}
