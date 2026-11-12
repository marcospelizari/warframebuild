import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import type { WeaponList } from "@/api/client";
import { suggest, tagOf } from "@/lib/gun-filter";
import { GunPicture } from "./GunPicture";
import h from "./GunSearch.module.css";
import u from "./ui.module.css";

const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** Name search with suggestions; Enter opens the first gun, Escape clears. */
export function GunSearch({ list }: { list: WeaponList | undefined }) {
  const [text, setText] = useState("");
  const navigate = useNavigate();
  const found = list ? suggest(list.weapons, list.excluded, text) : [];
  const first = found.find((s) => s.kind === "gun");
  const open = found.length > 0;
  return (
    <form
      role="search"
      className={u.gilt}
      style={{ width: "min(760px, 100% - 12px)", boxSizing: "border-box", padding: "8px 18px 10px" }}
      onSubmit={(e) => {
        e.preventDefault();
        if (first?.kind === "gun") void navigate({ to: "/w/$slug", params: { slug: first.weapon.slug } });
      }}
    >
      <span className={`${u.dia} ${u.diaTop}`} aria-hidden="true" />
      <span className={`${u.dia} ${u.diaBottom}`} aria-hidden="true" />
      <label htmlFor="q" className={u.srOnly}>
        Gun name
      </label>
      <div className="relative text-left">
        <div className={h.field}>
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 22 22" fill="none" stroke="#cfa448" strokeWidth="1.6" strokeLinecap="round">
            <circle cx="9.5" cy="9.5" r="6.5" />
            <path d="M14.5 14.5 L20 20" />
          </svg>
          <input
            id="q"
            className={h.find}
            type="search"
            autoComplete="off"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setText("");
            }}
            placeholder="Soma Prime, Lex, Kuva Bramma…"
            aria-controls="sugg"
          />
          {text && (
            <button className={h.clr} type="button" onClick={() => setText("")} aria-label="Clear search">
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <path d="M3 3 L13 13 M13 3 L3 13" />
              </svg>
            </button>
          )}
        </div>
        {open && (
          <ul id="sugg" aria-label="Matching guns" className={h.sugg}>
            {found.map((s) =>
              s.kind === "gun" ? (
                <li key={s.weapon.slug}>
                  <Link className={h.sg} to="/w/$slug" params={{ slug: s.weapon.slug }}>
                    <GunPicture src={s.weapon.image} small />
                    <span className="flex-1 text-lg">{s.weapon.name}</span>
                    {tagOf(s.weapon) && <span className={u.tag}>{tagOf(s.weapon)}</span>}
                    <span className="text-sm text-muted">
                      {cap(s.weapon.category)} {s.weapon.weapon_type.toLowerCase()}
                    </span>
                  </Link>
                </li>
              ) : (
                <li key={`x-${s.weapon.name}`} className={`${h.sg} ${h.sgOut}`}>
                  <GunPicture src={null} small />
                  <span className="flex-1 text-lg">{s.weapon.name}</span>
                  <span className="text-sm">No builds: {s.weapon.reason}</span>
                </li>
              ),
            )}
          </ul>
        )}
      </div>
      {list && text.trim() && !open && (
        <p className="mt-3 mb-0 text-left text-soft">
          No gun by that name. Check the spelling, or browse all guns below.
        </p>
      )}
    </form>
  );
}
