import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { BuildChange, EntryChange, GunChange, Update } from "@/api/client";
import { getUpdates } from "@/api/client";
import u from "@/components/ui.module.css";
import { dateLabel, trim } from "@/lib/format";

const KIND = {
  mod: "Mod",
  arcane: "Arcane",
  perk: "Incarnon evolution",
  weapon: "Gun",
};
const SUPPORT = {
  full: "calculated",
  partial: "partly calculated",
  unsupported: "not calculated",
};

/** Every game update and calculator change, newest first (U10). */
export function UpdatesPage() {
  const query = useQuery({ queryKey: ["updates"], queryFn: getUpdates });
  return (
    <main className="mx-auto max-w-[1000px] px-4 pt-11 pb-16 sm:px-8">
      <div className="flex items-center justify-center gap-6">
        <span className={`${u.orn} ${u.ornLeft}`} aria-hidden="true" />
        <h1 className="m-0 font-display text-4xl leading-tight font-normal">
          Game updates
        </h1>
        <span className={u.orn} aria-hidden="true" />
      </div>
      <p className="mx-auto mt-3 mb-10 max-w-[62ch] text-center text-base leading-relaxed text-soft">
        What each change to the game data, and each change to our calculation,
        did to the builds. Newest first.
      </p>
      {query.isError ? (
        <p role="alert" className="text-soft">
          Could not load the updates: {query.error.message}
        </p>
      ) : !query.data ? (
        <p className="text-muted">Loading…</p>
      ) : query.data.updates.length === 0 ? (
        <p className="text-center text-soft">
          No updates recorded yet. The first one appears after the next change
          to the builds.
        </p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-10 p-0">
          {query.data.updates.map((update) => (
            <li key={update.release}>
              <UpdateCard update={update} />
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}

function UpdateCard({ update }: { update: Update }) {
  const guns = update.guns.filter(
    (g) => g.builds.length > 0 || g.change !== "changed",
  );
  const stats = update.guns.filter((g) => g.stats_changed);
  return (
    <article
      className={`${u.gilt} px-5 py-6 sm:px-8`}
      aria-labelledby={`u-${update.release}`}
    >
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <h2
          id={`u-${update.release}`}
          className="m-0 font-display text-2xl font-normal text-cream"
        >
          {dateLabel(update.date)}
        </h2>
        <span className={u.tag}>
          {update.kind === "game" ? "Game update" : "Calculator update"}
        </span>
        {update.kind === "game" && update.game_update && (
          <span className="text-[15px] text-muted">{update.game_update}</span>
        )}
      </header>
      <ul className="mt-4 mb-0 flex flex-col gap-1.5 pl-5 text-base leading-relaxed text-soft">
        {update.summary.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {update.unavailable.length > 0 && (
        <p className="mt-3 mb-0 text-[14px] text-muted">
          Not compared: {update.unavailable.join("; ")}.
        </p>
      )}
      {update.entries.length > 0 && (
        <Section title={`Text changes (${update.entries.length})`}>
          {update.entries.map((entry) => (
            <EntryRow key={entry.key} entry={entry} />
          ))}
        </Section>
      )}
      {stats.length > 0 && (
        <Section title={`Gun stats (${stats.length})`}>
          {stats.map((g) => (
            <p key={g.slug} className="m-0 py-1.5">
              <GunLink gun={g} />
            </p>
          ))}
        </Section>
      )}
      {guns.length > 0 && (
        <Section
          title={`Builds (${guns.length} ${guns.length === 1 ? "gun" : "guns"})`}
        >
          <ul className="m-0 flex list-none flex-col divide-y divide-line p-0">
            {guns.map((g) => (
              <GunRow key={g.slug} gun={g} />
            ))}
          </ul>
        </Section>
      )}
    </article>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="mt-5 border-t border-line pt-4">
      <summary className="min-h-11 cursor-pointer text-[15px] font-semibold text-cyan">
        {title}
      </summary>
      <div className="pt-2">{children}</div>
    </details>
  );
}

function EntryRow({ entry }: { entry: EntryChange }) {
  const removed = entry.before.filter((line) => !entry.after.includes(line));
  const added = entry.after.filter((line) => !entry.before.includes(line));
  const support =
    entry.support_before &&
    entry.support_after &&
    entry.support_before !== entry.support_after
      ? `${SUPPORT[entry.support_before]} → ${SUPPORT[entry.support_after]}`
      : null;
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <p className="m-0 flex flex-wrap items-baseline gap-x-3">
        <span className="text-cream">{entry.name}</span>
        <span className="text-[13px] text-muted">
          {KIND[entry.kind]}
          {entry.change !== "changed" && `, ${entry.change}`}
        </span>
        {support && <span className={u.tag}>{support}</span>}
      </p>
      <ul className="m-0 mt-1.5 list-none p-0 font-game text-[14px] leading-relaxed">
        {removed.map((line) => (
          <li key={`-${line}`} className="text-[#ff9a7a]">
            <span className={u.srOnly}>Removed: </span>
            <span aria-hidden="true">− </span>
            <del>{line}</del>
          </li>
        ))}
        {added.map((line) => (
          <li key={`+${line}`} className="text-[#7fe0a8]">
            <span className={u.srOnly}>Added: </span>
            <span aria-hidden="true">+ </span>
            {line}
          </li>
        ))}
      </ul>
      {entry.unparsed.length > 0 && (
        <p className="m-0 mt-1.5 text-[13px] text-muted">
          Not calculated: {entry.unparsed.join("; ")}
        </p>
      )}
    </div>
  );
}

function GunLink({ gun }: { gun: GunChange }) {
  if (gun.change === "removed")
    return <span className="text-cream">{gun.name}</span>;
  return (
    <Link to="/w/$slug" params={{ slug: gun.slug }}>
      {gun.name}
    </Link>
  );
}

function GunRow({ gun }: { gun: GunChange }) {
  return (
    <li className="py-3">
      <p className="m-0 flex flex-wrap items-baseline gap-x-3">
        <GunLink gun={gun} />
        {gun.change !== "changed" && (
          <span className={u.tag}>{gun.change} gun</span>
        )}
      </p>
      {gun.builds.map((b) => (
        <BuildLine key={b.build} change={b} />
      ))}
    </li>
  );
}

function BuildLine({ change }: { change: BuildChange }) {
  const { kill_before: before, kill_after: after } = change;
  const label = change.build === "recommended" ? "Recommended" : change.build;
  const order = change.reordered ? "new slot order (element combinations)" : null;
  const parts =
    change.removed.length || change.added.length
      ? `${change.removed.join(", ") || "nothing"} → ${change.added.join(", ") || "nothing"}`
      : null;
  const swap = [parts, order].filter(Boolean).join("; ") || "same mods";
  return (
    <p className="m-0 mt-1 flex flex-wrap gap-x-3 text-[14px] text-soft">
      <span className="min-w-[110px] text-label">{label}</span>
      <span className="flex-1">{swap}</span>
      {before != null && after != null && (
        <span
          className={
            after < before
              ? "text-[#7fe0a8]"
              : after > before
                ? "text-[#ff9a7a]"
                : ""
          }
        >
          average kill {trim(before, 2)} s → {trim(after, 2)} s
        </span>
      )}
    </p>
  );
}
