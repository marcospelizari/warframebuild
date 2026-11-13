import type { Primer } from "@/api/client";
import { trim } from "@/lib/format";
import s from "./ScoreStrip.module.css";

/** What the Primer build's burst does (G49), opening to how it is counted. */
export function PrimerStrip({ primer }: { primer: Primer }) {
  const around = primer.enemies >= 1.5;
  return (
    <details className={s.score}>
      <summary>
        <span className="font-display text-[42px] leading-none text-gold">
          {trim(primer.boost, 1)}×
        </span>
        <span className="flex-[1_1_360px] text-[15px] leading-normal text-soft">
          Follow-up hits do {trim(primer.boost, 1)}× damage on the primed target
          {around
            ? `; about ${Math.round(primer.enemies)} enemies around it take ${trim(primer.area_boost, 1)}×` +
              (primer.radius ? ` (${trim(primer.radius, 1)} m blast)` : "")
            : ""}
          . Keeps {trim(primer.status_types, 1)} status types up.
        </span>
        <span className={`${s.howMore} text-[15px] text-cyan`} />
      </summary>
      <div className="px-1 pt-0.5 pb-5">
        <ul className={s.notes}>
          {primer.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}
