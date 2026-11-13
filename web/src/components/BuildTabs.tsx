import { Link } from "@tanstack/react-router";
import { factionSlug, PRIMER } from "@/lib/faction";
import u from "./ui.module.css";

type Props = {
  slug: string;
  factions: string[];
  faction: string | null; // a faction name, PRIMER, or null = Recommended
  level: number;
  primer: boolean; // the gun has a Primer build
};

/** Recommended / Faction builds / Primer as links: every build has its own URL (G88). */
export function BuildTabs({ slug, factions, faction, level, primer }: Props) {
  const first = factions[0];
  const isPrimer = faction === PRIMER;
  const note = isPrimer
    ? "Fire it for a moment to spread statuses, then switch to your main weapon: its hits do more damage on the primed enemies."
    : faction === null
      ? `One build to keep equipped: the fastest average kill against level ${level} Steel Path enemies of all ${factions.length} factions.`
      : `The fastest kills against level ${level} Steel Path ${faction} enemies. Swap to it for missions against that faction.`;
  return (
    <>
      <nav
        aria-label="Build type"
        className="mt-[22px] flex flex-wrap justify-center border-y border-line"
      >
        <Link
          resetScroll={false}
          className={u.tab}
          to="/w/$slug"
          params={{ slug }}
          activeOptions={{ exact: true }}
          aria-current={faction === null ? "page" : undefined}
        >
          Recommended
        </Link>
        {first && (
          <Link
            resetScroll={false}
            className={u.tab}
            to="/w/$slug/$faction"
            params={{ slug, faction: factionSlug(faction && !isPrimer ? faction : first) }}
            aria-current={faction !== null && !isPrimer ? "page" : undefined}
          >
            Faction builds
          </Link>
        )}
        {primer && (
          <Link
            resetScroll={false}
            className={u.tab}
            to="/w/$slug/$faction"
            params={{ slug, faction: PRIMER }}
            aria-current={isPrimer ? "page" : undefined}
          >
            Primer
          </Link>
        )}
      </nav>
      <p className="mx-auto mt-3 mb-0 max-w-[72ch] text-center text-[15px] leading-normal text-soft">
        {note}
      </p>
      {faction !== null && !isPrimer && (
        <nav aria-label="Faction" className="mt-3 flex flex-wrap justify-center gap-1.5">
          {factions.map((f) => (
            <Link
              resetScroll={false}
              key={f}
              className={`${u.chip} inline-flex items-center no-underline`}
              to="/w/$slug/$faction"
              params={{ slug, faction: factionSlug(f) }}
              aria-current={f === faction ? "page" : undefined}
            >
              {f}
            </Link>
          ))}
        </nav>
      )}
    </>
  );
}
