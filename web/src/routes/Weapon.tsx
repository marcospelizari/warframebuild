import { useQuery } from "@tanstack/react-query";
import { postCalc } from "@/api/client";

// Step 4.6 walking skeleton: fixed (empty) mod list, numbers only, no styling.
const MODS: string[] = [];

const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(2));

export function WeaponPage({ slug }: { slug: string }) {
  const build = useQuery({
    queryKey: ["calc", slug, MODS],
    queryFn: () => postCalc({ weapon: slug, mods: MODS }),
  });
  if (build.isPending) return <p>Loading…</p>;
  if (build.isError) return <p role="alert">{build.error.message}</p>;
  const { weapon, form, arsenal, dps, slots, assumptions } = build.data;
  return (
    <main className="p-6">
      <h1>{weapon.name}</h1>
      <p>Form: {form}</p>
      <h2>DPS</h2>
      <dl>
        <dt>Direct burst</dt>
        <dd>{fmt(dps.direct_burst)}</dd>
        <dt>Direct sustained</dt>
        <dd>{fmt(dps.direct_sustained)}</dd>
        {dps.head && (
          <>
            <dt>Burst on {dps.head.head}, 0 stacks</dt>
            <dd>{fmt(dps.head.zero_stacks)}</dd>
            <dt>Burst on {dps.head.head}, max hit stacks</dt>
            <dd>{fmt(dps.head.max_stacks)}</dd>
          </>
        )}
      </dl>
      <h2>Arsenal</h2>
      <dl>
        {Object.entries(arsenal.damage).map(([type, value]) => (
          <div key={type}>
            <dt>{type}</dt>
            <dd>{fmt(value)}</dd>
          </div>
        ))}
        <dt>Total damage</dt>
        <dd>{fmt(arsenal.total_damage)}</dd>
        <dt>Critical chance</dt>
        <dd>{fmt(arsenal.critical_chance)}</dd>
        <dt>Critical multiplier</dt>
        <dd>{fmt(arsenal.critical_multiplier)}</dd>
        <dt>Status chance</dt>
        <dd>{fmt(arsenal.status_chance)}</dd>
        <dt>Multishot</dt>
        <dd>{fmt(arsenal.multishot)}</dd>
        <dt>Fire rate</dt>
        <dd>{fmt(arsenal.fire_rate)}</dd>
        <dt>Magazine</dt>
        <dd>{fmt(arsenal.magazine)}</dd>
        <dt>Reload</dt>
        <dd>{fmt(arsenal.reload_time)}</dd>
      </dl>
      <h2>Slots</h2>
      <ol>
        {slots.map((s) => (
          <li key={s.index}>{s.name ?? "empty"}</li>
        ))}
      </ol>
      <h2>Assumptions</h2>
      <ul>
        {assumptions.map((a) => (
          <li key={a.id}>{a.text}</li>
        ))}
      </ul>
    </main>
  );
}
