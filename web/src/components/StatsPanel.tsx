import type { ReactNode } from "react";
import type { Build, DamageType, Forma } from "@/api/client";
import { compact, trim } from "@/lib/format";
import { damageIcon } from "./art";
import s from "./StatsPanel.module.css";

const PHYSICAL: DamageType[] = ["puncture", "slash", "impact"];
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function Icon({ type, className, alt = "" }: { type: DamageType; className?: string; alt?: string }) {
  const src = damageIcon(type);
  return src ? <img className={className} src={src} alt={alt} /> : null;
}

function Row({ k, v, total = false }: { k: ReactNode; v: string; total?: boolean }) {
  return (
    <div className={total ? `${s.ar} ${s.tot}` : s.ar}>
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}

function DamageName({ type, parts }: { type: DamageType; parts: DamageType[] | undefined }) {
  const [first, second] = parts ?? [];
  return (
    <>
      <Icon type={type} className={s.di} />
      {cap(type)}
      {first && second && (
        <span className={s.mx}>
          (<Icon type={first} className={s.di} alt={cap(first)} />+
          <Icon type={second} className={s.di} alt={cap(second)} />)
        </span>
      )}
    </>
  );
}

function change(build: Build, baseline: Build): string {
  const d = build.dps.direct_burst - baseline.dps.direct_burst;
  return `${d >= 0 ? "+" : "−"}${compact(Math.abs(d))}`;
}

/** The arsenal's stat screen for one build (canvas F-Weapon v46), at max rank. */
type Props = { build: Build; forma: Forma | null; baseline?: Build | null; pending?: boolean };

/** `baseline`: the calculated build an edit is compared with (F6). */
export function StatsPanel({ build, forma, baseline = null, pending = false }: Props) {
  const a = build.arsenal;
  const rank = (t: DamageType) => PHYSICAL.indexOf(t) + 1 || 9;
  const damage = (Object.entries(a.damage) as [DamageType, number][]).sort(
    ([x, vx], [y, vy]) => rank(x) - rank(y) || vy - vx,
  );
  const bonus = build.bonus_element;
  const usedPct = pending ? 0 : forma ? Math.min(100, (forma.used / forma.capacity) * 100) : 100;
  return (
    <aside
      aria-label="Arsenal stats of this build"
      aria-busy={pending}
      className={pending ? `${s.panel} opacity-50` : s.panel}
    >
      {bonus && (
        <>
          <div className={s.pgb}>
            <Icon type={bonus.damage_type} className={s.di} />
            <strong>
              +{Math.round(bonus.share * 100)}% {cap(bonus.damage_type)}
            </strong>
            <span>Progenitor bonus</span>
          </div>
          <p className={s.note}>Every stat and kill time on this page includes this bonus.</p>
        </>
      )}
      <div className={s.cap}>
        <span>CAPACITY</span>
        <span>{pending ? "…" : forma ? `${forma.used}/${forma.capacity}` : "Does not fit"}</span>
      </div>
      <div className={s.bar} aria-hidden="true">
        <div style={{ width: `${usedPct}%`, background: forma ? undefined : "#e0735f" }} />
      </div>
      <div className={s.ars}>
        {build.perks.length > 0 && (
          <>
            <h3>INCARNON EVOLUTIONS</h3>
            <ul className={s.perk}>
              {build.perks.map((p) => (
                <li key={p} className={s.ar}>
                  {p}
                </li>
              ))}
            </ul>
          </>
        )}
        {build.form === "incarnon" && <h3>INCARNON FORM</h3>}
        <dl>
          <Row k="Fire Rate" v={trim(a.fire_rate, 2)} />
          <Row k="Multishot" v={trim(a.multishot, 1)} />
          <Row k="Magazine" v={a.magazine == null ? "none" : String(Math.round(a.magazine))} />
          <Row k="Reload" v={`${trim(a.reload_time, 1)}s`} />
        </dl>
        <h3>DAMAGE</h3>
        <dl>
          <Row k="Critical Chance" v={`${trim(a.critical_chance * 100, 1)}%`} />
          <Row k="Critical Damage" v={`${trim(a.critical_multiplier, 1)}x`} />
          <Row k="Status" v={`${trim(a.status_chance * 100, 1)}%`} />
          {damage.map(([type, value]) => (
            <Row key={type} k={<DamageName type={type} parts={a.combined[type]} />} v={trim(value, 1)} />
          ))}
          <Row k="Total" v={trim(a.total_damage, 1)} total />
        </dl>
        <h3>CALCULATED</h3>
        <dl>
          <Row
            k="Direct burst DPS"
            v={compact(build.dps.direct_burst) + (baseline ? ` (${change(build, baseline)})` : "")}
          />
        </dl>
      </div>
      <p className={s.note}>Same numbers as the arsenal screen once these mods are equipped at max rank.</p>
    </aside>
  );
}
