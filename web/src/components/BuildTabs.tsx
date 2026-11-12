import { Link } from "@tanstack/react-router";
import { factionSlug } from "@/lib/faction";
import u from "./ui.module.css";

type Props = { slug: string; factions: string[]; faction: string | null; level: number };

/** Recommended / Faction builds as links: every build has its own URL (G88). */
export function BuildTabs({ slug, factions, faction, level }: Props) {
  const first = factions[0];
  const note =
    faction === null
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
            params={{ slug, faction: factionSlug(faction ?? first) }}
            aria-current={faction !== null ? "page" : undefined}
          >
            Faction builds
          </Link>
        )}
      </nav>
      <p className="mx-auto mt-3 mb-0 max-w-[72ch] text-center text-[15px] leading-normal text-soft">
        {note}
      </p>
      {faction !== null && (
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
