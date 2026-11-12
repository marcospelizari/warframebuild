import type { ReactNode } from "react";
import type { Forma } from "@/api/client";
import u from "./ui.module.css";

export function formaText(forma: Forma | null): string {
  if (!forma) return "Does not fit, even with forma";
  return forma.forma === 0 ? "No forma needed" : `${forma.forma} forma`;
}

type Props = { title: string; note: string; forma: Forma | null; children: ReactNode };

/** The gilt-framed build: title, note (search status or edit state), forma count, grid. */
export function BuildFrame({ title, note, forma, children }: Props) {
  return (
    <section className={`${u.gilt} px-3 pt-[22px] pb-6 sm:px-6`} aria-labelledby="bt">
      <span className={`${u.dia} ${u.diaTop}`} aria-hidden="true" />
      <span className={`${u.dia} ${u.diaBottom}`} aria-hidden="true" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="bt" className="m-0 font-display text-[30px] leading-tight font-normal">
            {title}
          </h2>
          <p className="mt-1 mb-0 text-sm text-muted">{note}</p>
        </div>
        <strong className={`text-[15px] ${forma ? "text-gold" : "text-[#e0735f]"}`}>
          {formaText(forma)}
        </strong>
      </div>
      {children}
      <p className="mx-0 mt-3 mb-0 text-center text-[13px] text-muted">
        Point at a mod, or tab to it, for the full card. Elements combine in slot order, top row
        first.
      </p>
    </section>
  );
}
