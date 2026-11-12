import type { CSSProperties } from "react";
import type { FormaSlot, ModItem } from "@/api/client";
import { AMALGAM_PARTS, COMMON_PARTS, GALVANIZED_PARTS, RARITY_PARTS, SLOT_ART } from "./art";
import s from "./ModCard.module.css";
import { hasGlyph, PolarityGlyph } from "./Polarity";

const INK: Record<string, string> = {
  COMMON: "#c79989",
  UNCOMMON: "#bec0c2",
  RARE: "#fbecc4",
  LEGENDARY: "#dfdfdf",
};
const RARITY_CLASS: Record<string, string | undefined> = {
  COMMON: s.com,
  UNCOMMON: s.unc,
  LEGENDARY: s.leg,
};
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

type Props = {
  mod: ModItem | null;
  slot: FormaSlot | null; // null: no forma layout fits (Q6)
  label: string; // lower tab: the gun category, or "Exilus"
  exilus?: boolean;
  why?: string | null; // F8 line in the opened card
  onPick?: () => void; // editor: choose what goes here
};

function frame(mod: ModItem) {
  if (mod.name.startsWith("Galvanized ")) return { parts: GALVANIZED_PARTS, cls: [s.gal] };
  if (mod.name.startsWith("Amalgam ")) return { parts: AMALGAM_PARTS, cls: [s.gal, s.ama] };
  return {
    parts: RARITY_PARTS[mod.rarity] ?? COMMON_PARTS,
    cls: [RARITY_CLASS[mod.rarity]],
  };
}

/** Where the mod sits, for the drain colour and the screen-reader label. */
function slotFit(mod: ModItem, slot: FormaSlot | null) {
  const polarity = slot?.polarity ?? null;
  const match = !!polarity && (polarity === "any" || polarity === mod.polarity);
  const drain = slot?.drain ?? mod.drain;
  const place = polarity ? `${cap(polarity)} slot` : "No slot polarity";
  const note = match ? " (half: polarity matches)" : polarity ? " (polarity does not match)" : "";
  return {
    match,
    tone: match ? s.ok : polarity ? s.bad : s.plain,
    drain,
    where: `${place}${slot?.forma ? ", forma" : ""}, drain ${drain}${note}`,
  };
}

function SlotMark({ slot, match }: { slot: FormaSlot | null; match: boolean }) {
  // Only a forma'd slot shows its polarity above the card (F3).
  if (!slot?.forma || !slot.polarity || !hasGlyph(slot.polarity)) return null;
  return (
    <span className={s.mark} style={{ color: match ? "#7fe0a8" : "#ff9a7a" }}>
      <PolarityGlyph polarity={slot.polarity} className={s.pgv} />
    </span>
  );
}

export function ModCard({ mod, slot, label, exilus = false, why = null, onPick }: Props) {
  if (!mod) {
    const vars = { "--ph": SLOT_ART.placeholder, "--exi": SLOT_ART.exilus } as CSSProperties;
    return (
      <div className={s.cell} style={vars}>
        {onPick ? (
          <button
            className={`${s.pick} ${[s.blank, exilus && s.exi].filter(Boolean).join(" ")}`}
            type="button"
            onClick={onPick}
            aria-label={exilus ? "Empty exilus slot: choose a mod" : "Empty slot: choose a mod"}
          />
        ) : (
          <span
            className={[s.blank, exilus && s.exi].filter(Boolean).join(" ")}
            role="img"
            aria-label={exilus ? "Empty exilus slot" : "Empty slot"}
          />
        )}
      </div>
    );
  }
  const { parts, cls } = frame(mod);
  const fit = slotFit(mod, slot);
  const ink = INK[mod.rarity] ?? "#c79989";
  const vars = {
    "--ink": ink,
    "--edge": cls.includes(s.gal) ? "#68ce5f" : ink,
    "--top": parts.top,
    "--bot": parts.bottom,
    "--side": parts.side,
    "--tab": parts.tab,
  } as CSSProperties;
  const stats = mod.stats.join("\n");
  return (
    <div className={[s.cell, ...cls].filter(Boolean).join(" ")} style={vars}>
      <button
        className={s.mod}
        type="button"
        onClick={onPick}
        aria-label={`${mod.name}: ${stats}. ${fit.where}.${why ? ` ${why}.` : ""}${onPick ? " Change mod." : ""}`}
      >
        <span className={s.content} style={{ "--bg": parts.bg } as CSSProperties}>
          <span className={s.image}>{mod.image && <img src={mod.image} alt="" />}</span>
          <span className={s.desc}>
            <span className={s.name}>{mod.name}</span>
            <span className={s.eff}>{stats}</span>
            {why && <span className={s.why}>{why}</span>}
          </span>
        </span>
        <span className={s.border} />
        <span className={`${s.drain} ${fit.tone}`}>
          {fit.drain}
          {hasGlyph(mod.polarity) && <PolarityGlyph polarity={mod.polarity} className={s.pgv} />}
        </span>
        {slot?.forma && <span className={s.forma}>Forma</span>}
        <span className={s.compat}>
          <b>{label.toUpperCase()}</b>
        </span>
        <span className={s.fusion}>
          {Array.from({ length: Math.min(mod.rank, 10) }, (_, i) => (
            <i key={i}>★</i>
          ))}
        </span>
      </button>
      <SlotMark slot={slot} match={fit.match} />
    </div>
  );
}
