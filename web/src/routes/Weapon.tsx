import { useQuery } from "@tanstack/react-query";
import { getBuilds, getMods } from "@/api/client";
import { ModGrid } from "@/components/ModGrid";
import { StatsPanel } from "@/components/StatsPanel";

// Step 10b: the Recommended build in the F grid and stats panel; header, tabs and
// scoring strip arrive in 10d.
export function WeaponPage({ slug }: { slug: string }) {
  const builds = useQuery({ queryKey: ["builds", slug], queryFn: () => getBuilds(slug) });
  const mods = useQuery({ queryKey: ["mods", slug], queryFn: () => getMods(slug) });
  if (builds.isError || mods.isError) {
    return <p role="alert">{(builds.error ?? mods.error)?.message}</p>;
  }
  if (!builds.data || !mods.data) return <p>Loading…</p>;
  const { weapon, variants } = builds.data;
  const stored = variants[0]?.recommended;
  if (!stored) return <p role="alert">No builds for {weapon.name} yet.</p>;
  return (
    <main className="mx-auto max-w-[1360px] px-4 py-8">
      <h1 className="text-center font-display text-4xl text-cream">{weapon.name}</h1>
      <div className="mt-8 flex flex-wrap items-start gap-8">
        <section aria-label="Recommended build" className="min-w-0 flex-[2_1_940px]">
          <ModGrid stored={stored} items={mods.data} weaponType={weapon.weapon_type} />
        </section>
        <StatsPanel stored={stored} />
      </div>
    </main>
  );
}
