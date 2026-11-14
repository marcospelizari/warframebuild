import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect } from "react";
import type { Category, Tier, TierList, WeaponItem } from "@/api/client";
import { getTiers, getWeapons } from "@/api/client";
import { GunTile } from "@/components/GunTile";
import u from "@/components/ui.module.css";
import { trim } from "@/lib/format";
import s from "./TierList.module.css";

const CLASSES: Record<Category, { label: string; plural: string }> = {
  primary: { label: "Primary", plural: "primaries" },
  secondary: { label: "Secondary", plural: "secondaries" },
};

function seconds(value: number): string {
  return `${trim(value, 2)} s`;
}

/** What the tier covers, e.g. "1.25–1.6× the fastest kill (0.05–0.06 s)". */
function range(tier: Tier, before: number | null, fastest: number): string {
  const from = before ?? 1;
  if (tier.up_to === null) return `Over ${trim(from, 2)}× the fastest kill (${seconds(from * fastest)})`;
  if (before === null) return `Up to ${trim(tier.up_to, 2)}× the fastest kill (${seconds(tier.up_to * fastest)})`;
  return `${trim(from, 2)}–${trim(tier.up_to, 2)}× the fastest kill (${trim(from * fastest, 2)}–${seconds(tier.up_to * fastest)})`;
}

function Bands({ list, guns }: { list: TierList; guns: Map<string, WeaponItem> }) {
  const bands = list.tiers.map((tier, i) => {
    const from = list.tiers[i - 1]?.up_to ?? null; // the tier above's limit
    const shown = tier.guns.filter((g) => guns.has(g.slug));
    if (!shown.length) return null;
    return (
      <section key={tier.name} className={`${s.band} ${s[`t${tier.name}`]}`} aria-labelledby={`tier-${tier.name}`}>
        <h2 id={`tier-${tier.name}`} className={s.letter}>
          <span className={u.srOnly}>Tier </span>
          {tier.name}
        </h2>
        <div className={s.body}>
          <p className={s.range}>
            {range(tier, from, list.fastest)} · {shown.length} {shown.length === 1 ? "gun" : "guns"}
          </p>
          <ul className={s.grid}>
            {shown.map((g) => (
              <li key={g.slug}>
                <GunTile gun={guns.get(g.slug)!}>
                  <span className="text-[13px] text-cyan">{seconds(g.kill_time)} average kill</span>
                  {g.capped && <span className={s.mark}>10 s limit</span>}
                  {g.partial && <span className={s.mark}>May be stronger</span>}
                </GunTile>
              </li>
            ))}
          </ul>
        </div>
      </section>
    );
  });
  return <div className="mt-8 grid gap-4">{bands}</div>;
}

/** G92: one weapon class ranked S to F by its Recommended builds' kill times. */
export function TierListPage({ category }: { category: string }) {
  const known = Object.hasOwn(CLASSES, category) ? (category as Category) : null;
  const tiers = useQuery({
    queryKey: ["tiers", known],
    queryFn: () => getTiers(known!),
    enabled: known !== null,
  });
  const weapons = useQuery({ queryKey: ["weapons"], queryFn: getWeapons });
  useEffect(() => {
    document.title = known
      ? `${CLASSES[known].label} tier list | warframeBuild`
      : "Tier list | warframeBuild";
  }, [known]);
  const guns = new Map((weapons.data?.weapons ?? []).map((w) => [w.slug, w]));
  const error = tiers.error ?? weapons.error;
  const fastest = tiers.data?.tiers.flatMap((t) => t.guns)[0];

  return (
    <main className="mx-auto max-w-[1376px] px-4 pt-11 pb-16 sm:px-8">
      <div className="flex items-center justify-center gap-6">
        <span className={`${u.orn} ${u.ornLeft}`} aria-hidden="true" />
        <h1 className="m-0 font-display text-4xl leading-tight font-normal">Tier list</h1>
        <span className={u.orn} aria-hidden="true" />
      </div>
      <p className="mx-auto mt-3 mb-6 max-w-[64ch] text-center text-base leading-relaxed text-soft">
        Every gun ranked by how fast its Recommended build kills Steel Path enemies, against the
        fastest gun of its class. Calculated, not voted.
      </p>
      <nav aria-label="Weapon class" className="flex justify-center border-b border-line">
        {(Object.keys(CLASSES) as Category[]).map((c) => (
          <Link
            key={c}
            className={u.tab}
            to="/tier-list/$category"
            params={{ category: c }}
            aria-current={c === known ? "page" : undefined}
          >
            {CLASSES[c].label}
          </Link>
        ))}
      </nav>
      {!known ? (
        <p role="alert" className="mt-8 text-center text-soft">
          There is no tier list for “{category}”. Pick a class above.
        </p>
      ) : error ? (
        <p role="alert" className="mt-8 text-center text-soft">
          Could not load the tier list: {error.message}
        </p>
      ) : !tiers.data || !weapons.data ? (
        <p className="mt-8 text-center text-muted" aria-live="polite">
          Loading the tier list…
        </p>
      ) : (
        <>
          <dl className={s.legend}>
            <div>
              <dt>Enemies</dt>
              <dd>
                level {tiers.data.level} Steel Path, {tiers.data.factions} factions
              </dd>
            </div>
            {fastest && guns.has(fastest.slug) && (
              <div>
                <dt>Fastest</dt>
                <dd>
                  {guns.get(fastest.slug)!.name}, {seconds(fastest.kill_time)} average kill
                </dd>
              </div>
            )}
            <div>
              <dt className={s.mark}>10 s limit</dt>
              <dd>an enemy outlived the 10 s fight: the rank is less certain</dd>
            </div>
            <div>
              <dt className={s.mark}>May be stronger</dt>
              <dd>an Incarnon evolution is not fully calculated</dd>
            </div>
          </dl>
          <Bands list={tiers.data} guns={guns} />
        </>
      )}
    </main>
  );
}
