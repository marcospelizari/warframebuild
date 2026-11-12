import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { Category, WeaponItem } from "@/api/client";
import { browse, NO_FILTERS, tagOf, typesIn } from "@/lib/gun-filter";
import b from "./GunBrowser.module.css";
import { GunPicture } from "./GunPicture";
import u from "./ui.module.css";

const LIMIT = 30;
const TABS: [Category, string, string][] = [
  ["primary", "Primary", "primaries"],
  ["secondary", "Secondary", "secondaries"],
];

/** "All guns": Primary / Secondary tabs, type and kind filters, picture tiles. */
export function GunBrowser({ weapons }: { weapons: WeaponItem[] | undefined }) {
  const [tab, setTab] = useState<Category>("primary");
  const [filters, setFilters] = useState(NO_FILTERS);
  const [all, setAll] = useState(false);
  const list = weapons ?? [];
  const kept = browse(list, { tab, ...filters });
  const shown = all ? kept : kept.slice(0, LIMIT);
  const inTab = list.filter((w) => w.category === tab).length;
  const plural = TABS.find(([id]) => id === tab)?.[2];
  const set = (change: Partial<typeof NO_FILTERS>) => {
    setFilters({ ...filters, ...change });
    setAll(false);
  };
  return (
    <section id="browse" aria-labelledby="hb" className="pt-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="hb" className="m-0 font-display text-[34px] leading-tight font-normal">
          All guns
        </h2>
        <div role="group" aria-label="Slot" className="flex border-b border-line">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              className={u.tab}
              type="button"
              aria-pressed={tab === id}
              onClick={() => {
                setTab(id);
                setFilters({ ...filters, type: "all" });
                setAll(false);
              }}
            >
              {label}{" "}
              <span className="font-sans text-sm text-muted">
                {list.filter((w) => w.category === id).length}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Weapon type" className="flex flex-wrap gap-1.5">
          {["all", ...typesIn(list, tab)].map((t) => (
            <button
              key={t}
              className={u.chip}
              type="button"
              aria-pressed={filters.type === t}
              onClick={() => set({ type: t })}
            >
              {t === "all" ? "All types" : t}
            </button>
          ))}
        </div>
        <span aria-hidden="true" className="mx-1.5 hidden h-7 w-px bg-line sm:block" />
        <button
          className={u.chip}
          type="button"
          aria-pressed={filters.incarnon}
          onClick={() => set({ incarnon: !filters.incarnon })}
        >
          Incarnon
        </button>
        <button
          className={u.chip}
          type="button"
          aria-pressed={filters.progenitor}
          onClick={() => set({ progenitor: !filters.progenitor })}
        >
          Kuva, Tenet or Coda
        </button>
        <span className="ml-auto text-sm text-muted" aria-live="polite">
          {weapons ? `${kept.length} of ${inTab} ${plural}` : "Loading guns…"}
        </span>
      </div>
      {weapons && kept.length === 0 && (
        <p className="mt-7 mb-0 text-soft">
          No gun matches these filters.{" "}
          <button className={u.lnk} type="button" onClick={() => set(NO_FILTERS)}>
            Clear filters
          </button>
        </p>
      )}
      <ul className={b.grid}>
        {shown.map((w) => (
          <li key={w.slug}>
            <Link className={b.tile} to="/w/$slug" params={{ slug: w.slug }}>
              <span className={b.plinth}>
                <GunPicture src={w.image} />
              </span>
              <span className="text-base font-semibold">{w.name}</span>
              <span className="text-[13px] text-muted">
                {w.weapon_type}, MR {w.mastery}
              </span>
              {tagOf(w) && <span className={u.tag}>{tagOf(w)}</span>}
            </Link>
          </li>
        ))}
      </ul>
      {!all && kept.length > LIMIT && (
        <div className="mt-6 flex justify-center">
          <button className={u.act} type="button" onClick={() => setAll(true)}>
            Show all {kept.length} guns
          </button>
        </div>
      )}
    </section>
  );
}
