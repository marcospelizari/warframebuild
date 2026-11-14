import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { WeaponItem } from "@/api/client";
import { tagOf } from "@/lib/gun-filter";
import { GunPicture } from "./GunPicture";
import t from "./GunTile.module.css";
import u from "./ui.module.css";

/** A gun's picture tile linking to its builds (home list, tier list). `children`: extra
 * lines under the name. */
export function GunTile({ gun, children }: { gun: WeaponItem; children?: ReactNode }) {
  const tag = tagOf(gun);
  return (
    <Link className={t.tile} to="/w/$slug" params={{ slug: gun.slug }}>
      <span className={t.plinth}>
        <GunPicture src={gun.image} />
      </span>
      <span className="text-base font-semibold">{gun.name}</span>
      <span className="text-[13px] text-muted">
        {gun.weapon_type}, MR {gun.mastery}
      </span>
      {children}
      {tag && <span className={u.tag}>{tag}</span>}
      {gun.good_primer && <span className={u.tag}>Good primer</span>}
    </Link>
  );
}
