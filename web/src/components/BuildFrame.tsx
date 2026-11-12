import type { ModList, StoredBuild } from "@/api/client";
import { ModGrid } from "./ModGrid";
import u from "./ui.module.css";

const STATUS = {
  optimal: () => "Every possible build was checked: this is the best.",
  best_found: (n: number) =>
    `Best of ${n.toLocaleString("en")} mod combinations tried; a better one may exist.`,
  what_if: () => "What-if: the first element's mods with this element.",
};

function formaText(stored: StoredBuild): string {
  if (!stored.forma) return "Does not fit, even with forma";
  return stored.forma.forma === 0 ? "No forma needed" : `${stored.forma.forma} forma`;
}

type Props = { title: string; stored: StoredBuild; items: ModList; weaponType: string };

/** The gilt-framed build: title, search status, forma count, mod grid. */
export function BuildFrame({ title, stored, items, weaponType }: Props) {
  return (
    <section className={`${u.gilt} px-3 pt-[22px] pb-6 sm:px-6`} aria-labelledby="bt">
      <span className={`${u.dia} ${u.diaTop}`} aria-hidden="true" />
      <span className={`${u.dia} ${u.diaBottom}`} aria-hidden="true" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="bt" className="m-0 font-display text-[30px] leading-tight font-normal">
            {title}
          </h2>
          <p className="mt-1 mb-0 text-sm text-muted">{STATUS[stored.status](stored.evaluations)}</p>
        </div>
        <strong className="text-[15px] text-gold">{formaText(stored)}</strong>
      </div>
      <ModGrid stored={stored} items={items} weaponType={weaponType} />
      <p className="mx-0 mt-3 mb-0 text-center text-[13px] text-muted">
        Point at a mod, or tab to it, for the full card. Elements combine in slot order, top row
        first.
      </p>
    </section>
  );
}
