import type { Build } from "@/api/client";
import { trim } from "@/lib/format";
import s from "./ScoreStrip.module.css";

/** Average kill time (the score this build was chosen by), opening to every kill and
    the assumptions behind them. `faction` narrows both to that faction. */
type Props = { build: Build; faction: string | null; baseline?: Build | null };

/** Average kill time in seconds: over every enemy, or `faction`'s. */
export function killTime(build: Build, faction: string | null): number {
  const { combat } = build;
  if (!faction) return combat.score;
  return combat.factions.find((f) => f.faction === faction)?.score ?? combat.score;
}

/** `baseline`: the calculated build an edit is compared with (F6). */
export function ScoreStrip({ build, faction, baseline = null }: Props) {
  const { combat } = build;
  const enemies = faction ? combat.enemies.filter((e) => e.faction === faction) : combat.enemies;
  const score = killTime(build, faction);
  const delta = baseline ? score - killTime(baseline, faction) : 0;
  const shots = build.headshot ? "headshots" : "body shots";
  return (
    <details className={s.score}>
      <summary>
        <span className="font-display text-[42px] leading-none text-gold">{trim(score, 2)} s</span>
        {baseline && (
          <span className={`text-[15px] ${delta > 0.005 ? "text-[#ff9a7a]" : "text-[#7fe0a8]"}`}>
            {Math.abs(delta) < 0.005
              ? "Same as the calculated build"
              : `${trim(Math.abs(delta), 2)} s ${delta > 0 ? "slower" : "faster"} than the calculated build`}
          </span>
        )}
        <span className="flex-[1_1_360px] text-[15px] leading-normal text-soft">
          Average time to kill {enemies.length} level {combat.level} Steel Path enemies, {shots},
          within {combat.cap_s} s.
        </span>
        <span className={`${s.more} text-[15px] text-cyan`} />
      </summary>
      <div className="px-1 pt-0.5 pb-5">
        <dl className={s.kills}>
          {enemies.map((e) => (
            <div key={e.unique_name} className={s.led}>
              <dt>
                <span className="text-cream">{e.name}</span>
                {!faction && <span className="text-xs">{e.faction}</span>}
              </dt>
              <dd>
                {e.ttk == null
                  ? `not killed in ${combat.cap_s} s (${Math.round(e.removed * 100)}%)`
                  : `${trim(e.ttk, 2)} s`}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 flex flex-wrap items-start gap-x-12 gap-y-2">
          <ul className={s.notes}>
            {build.headshot && <li>Headshots: {build.headshot.reason}</li>}
            {build.assumptions.map((a) => (
              <li key={a.id}>{a.text}</li>
            ))}
            <li>{build.form === "incarnon" ? "Incarnon form" : "Normal form"}</li>
          </ul>
        </div>
      </div>
    </details>
  );
}
