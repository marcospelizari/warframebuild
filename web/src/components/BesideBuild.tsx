import { useState } from "react";
import type { StoredBuild } from "@/api/client";
import { trim } from "@/lib/format";
import s from "./BesideBuild.module.css";
import u from "./ui.module.css";

type Advice = NonNullable<StoredBuild["shards"]>;
type Shard = Advice["normal"][number]["shard"];

const NAME: Record<Shard, string> = {
  crimson: "Crimson",
  amber: "Amber",
  azure: "Azure",
  emerald: "Emerald",
  topaz: "Topaz",
  violet: "Violet",
};

/** A score gain as a share of the build's own score, as "+6.1%"; under 0.05%: "no gain". */
function pct(gained: number, base: number): string {
  const share = (gained / base) * 100;
  return share < 0.05 ? "no gain" : `+${trim(share, 1)}%`;
}

type Props = {
  stored: StoredBuild;
  metric: string; // what the percentages measure, e.g. "kill speed"
};

/** G91: suggestions that are not part of the build (shards, aura), under the build. */
export function BesideBuild({ stored, metric }: Props) {
  const [tauforged, setTauforged] = useState(false);
  const advice = stored.shards;
  const auras = stored.auras;
  const base = stored.score;
  // Releases made before G91; a score of 0 (Primer) gives no percentages.
  if ((!advice && !auras?.length) || base <= 0) return null;
  const steps = advice ? (tauforged ? advice.tauforged : advice.normal) : [];
  const last = steps.at(-1);

  return (
    <section className="mt-12" aria-labelledby="beside">
      <div className="flex items-center gap-4">
        <span className={u.orn} aria-hidden="true" />
        <h2 id="beside" className="m-0 font-display text-[26px] leading-tight font-normal">
          Beside the build
        </h2>
        <span className={`${u.orn} ${u.ornLeft} flex-1`} aria-hidden="true" />
      </div>
      <p className="mt-1 mb-0 text-sm text-muted">
        Not part of the build above, which stays the same. Percentages: {metric} gained over the
        build alone.
      </p>
      <div className={s.cards}>
        {advice && (
          <div className={s.card}>
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h3 className="m-0 font-display text-xl font-normal">Archon Shards</h3>
              <div className="flex gap-2" role="group" aria-label="Shard kind">
                <button
                  type="button"
                  className={u.chip}
                  aria-pressed={!tauforged}
                  onClick={() => setTauforged(false)}
                >
                  Normal
                </button>
                <button
                  type="button"
                  className={u.chip}
                  aria-pressed={tauforged}
                  onClick={() => setTauforged(true)}
                >
                  Tauforged
                </button>
              </div>
            </div>
            <p className={s.note}>
              On your Warframe, slot by slot: each next slot takes the shard that adds the most.
            </p>
            {steps.length ? (
              <ol className={s.rows}>
                {steps.map((step, i) => (
                  <li key={i} className={s.row}>
                    <span className="w-5 text-muted">{i + 1}</span>
                    <span className={`${s.gem} ${s[step.shard]}`} aria-hidden="true" />
                    <span className="flex-1 text-cream">{NAME[step.shard]}</span>
                    <span className="text-cyan">
                      {pct(step.score - (steps[i - 1]?.score ?? base), base)}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className={s.empty}>No shard helps this build.</p>
            )}
            {last && (
              <p className={s.total}>
                {steps.length} {steps.length === 1 ? "shard" : "shards"}:{" "}
                <strong className="text-gold">{pct(last.score - base, base)}</strong>
                {steps.length < 5 && <span className="text-muted"> (more shards add nothing)</span>}
              </p>
            )}
            {advice.conditions.length > 0 && (
              <ul className={s.conditions}>
                {advice.conditions.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {!!auras?.length && (
          <div className={s.card}>
            <h3 className="m-0 font-display text-xl font-normal">Aura</h3>
            <p className={s.note}>Your Warframe's aura slot, or a squadmate's.</p>
            <ol className={s.rows}>
              {auras.map((a, i) => (
                <li key={a.unique_name} className={s.row}>
                  <span className="flex-1 text-cream">{a.name}</span>
                  {i === 0 && <span className={u.tag}>Best</span>}
                  <span className="text-cyan">{pct(a.score - base, base)}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
}
