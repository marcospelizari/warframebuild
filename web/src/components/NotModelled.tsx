import type { Build, BuildsResponse } from "@/api/client";
import s from "./NotModelled.module.css";

type Entry = BuildsResponse["not_modelled"][number];

const KIND = { perk: "Incarnon evolution", mod: "Mod", arcane: "Arcane" } as const;
const SHOWN = 2; // names on the closed line

/** Names of `kind` already in the build (an edit can add a partial mod). */
function inBuild(build: Build, kind: Entry["kind"]): Set<string> {
  if (kind === "perk") return new Set(build.perks);
  if (kind === "arcane") return new Set(build.arcane ? [build.arcane.name] : []);
  return new Set([...build.slots, build.exilus].flatMap((s) => (s?.name ? [s.name] : [])));
}

type Props = { all: Entry[]; build: Build };

/** U5: what the gun can use but the calculator leaves out; any of it may beat the build. */
export function NotModelled({ all, build }: Props) {
  const entries = all.filter((e) => !inBuild(build, e.kind).has(e.name));
  if (!entries.length) return null;
  const more = entries.length - SHOWN;
  return (
    <details className={s.box}>
      <summary>
        <span className="text-soft">Not fully calculated, may be stronger: </span>
        <span className="text-cream">
          {entries
            .slice(0, SHOWN)
            .map((e) => e.name)
            .join(", ")}
        </span>
        {more > 0 && <span className="text-muted"> (+{more} more)</span>}
      </summary>
      <ul className={s.list}>
        {entries.map((e) => (
          <li key={`${e.kind}:${e.name}`}>
            <span className="text-cream">{e.name}</span>{" "}
            <span className="text-xs text-muted">
              {KIND[e.kind]}, {e.support === "partial" ? "partly calculated" : "not calculated"}
            </span>
            {e.text.map((t) => (
              <span key={t} className="block">
                {t}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </details>
  );
}
