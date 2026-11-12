import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect } from "react";
import { ApiFailure, getBuilds, getMods, getWeapons } from "@/api/client";
import { BuildFrame } from "@/components/BuildFrame";
import { BuildTabs } from "@/components/BuildTabs";
import { ScoreStrip } from "@/components/ScoreStrip";
import { StatsPanel } from "@/components/StatsPanel";
import { WeaponHeader } from "@/components/WeaponHeader";
import { factionSlug } from "@/lib/faction";

const SITE = "warframeBuild";
const BUSY = new Set(["no_release", "release_mismatch", "release_gone"]);

/** Page states (F5): what a player can do when there is no build to show. */
function Problem({ error }: { error: Error }) {
  const failure = error instanceof ApiFailure ? error : null;
  let text = `Could not load this gun: ${error.message}`;
  if (failure?.status === 404) text = "There is no gun at this address.";
  else if (failure?.code && BUSY.has(failure.code))
    text = "Builds are being updated. Try again in a few minutes.";
  else if (failure?.status === 429) text = "Too many requests. Wait a moment, then reload.";
  return <NotShown text={text} />;
}

function NotShown({ text }: { text: string }) {
  return (
    <main className="mx-auto max-w-[1376px] px-4 py-16 text-center sm:px-8">
      <p role="alert" className="m-0 text-lg text-soft">
        {text}
      </p>
      <p className="mt-4">
        <Link to="/" hash="browse">
          Browse all guns
        </Link>
      </p>
    </main>
  );
}

export function WeaponPage({ slug, faction }: { slug: string; faction: string | null }) {
  const builds = useQuery({ queryKey: ["builds", slug], queryFn: () => getBuilds(slug) });
  const mods = useQuery({ queryKey: ["mods", slug], queryFn: () => getMods(slug) });
  const list = useQuery({ queryKey: ["weapons"], queryFn: getWeapons });
  const variant = builds.data?.variants[0];
  const factions = variant ? Object.keys(variant.factions) : [];
  const name = faction === null ? null : factions.find((f) => factionSlug(f) === faction);
  const gun = builds.data?.weapon.name;

  useEffect(() => {
    if (!gun) return;
    document.title = name
      ? `${gun} build against ${name} | ${SITE}`
      : `${gun} build: mods, forma, arcane | ${SITE}`;
  }, [gun, name]);

  const error = builds.error ?? mods.error;
  if (error) return <Problem error={error} />;
  if (!builds.data || !mods.data) {
    return (
      <main className="mx-auto min-h-[60vh] max-w-[1376px] px-4 py-16 text-center text-lg sm:px-8">
        Loading builds…
      </main>
    );
  }
  if (!variant) return <NotShown text={`No builds for ${builds.data.weapon.name} yet.`} />;
  const stored = name ? variant.factions[name] : faction === null ? variant.recommended : null;
  if (!stored) return <NotShown text="There is no such faction build for this gun." />;
  const { weapon } = builds.data;
  return (
    <main className="mx-auto max-w-[1376px] px-4 pt-5 pb-16 sm:px-8">
      <WeaponHeader weapon={weapon} item={list.data?.weapons.find((w) => w.slug === slug)} />
      <BuildTabs
        slug={slug}
        factions={factions}
        faction={name ?? null}
        level={stored.build.combat.level}
      />
      <ScoreStrip build={stored.build} faction={name ?? null} />
      <div className="mt-7 flex flex-wrap items-start gap-9">
        <div className="min-w-0 flex-[999_1_760px]">
          <BuildFrame
            title={name ? `Against ${name}` : "Recommended"}
            stored={stored}
            items={mods.data}
            weaponType={weapon.weapon_type}
          />
        </div>
        <StatsPanel stored={stored} />
      </div>
    </main>
  );
}
