import { useState } from "react";
import type { WeaponItem, WeaponRef } from "@/api/client";
import u from "./ui.module.css";

const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** Icon, name between ornaments, one meta line, Edit / copy-link buttons (canvas F-Weapon v46). */
type Props = { weapon: WeaponRef; item: WeaponItem | undefined; onEdit?: () => void };

export function WeaponHeader({ weapon, item, onEdit }: Props) {
  const [copied, setCopied] = useState(false);
  const meta = [
    `${cap(weapon.category)} ${weapon.weapon_type.toLowerCase()}`,
    item ? `mastery rank ${item.mastery}` : null,
    item?.incarnon ? "Incarnon" : null,
  ].filter(Boolean);
  const copy = () => {
    void navigator.clipboard.writeText(window.location.href).then(() => setCopied(true));
  };
  return (
    <section className="flex flex-col items-center pt-2 pb-1 text-center">
      {item?.image && (
        <img src={item.image} alt="" className="size-[150px] object-contain sm:size-[200px]" />
      )}
      <div className="mt-2.5 flex max-w-full items-center justify-center gap-[22px]">
        <span className={`${u.orn} ${u.ornLeft}`} aria-hidden="true" />
        <h1 className="m-0 font-display text-[40px] leading-[1.05] font-normal sm:text-[56px]">
          {weapon.name}
        </h1>
        <span className={u.orn} aria-hidden="true" />
      </div>
      <p className="mt-2 mb-0 text-[15px] text-muted">{meta.join(", ")}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2.5">
        {onEdit && (
          <button className={`${u.act} ${u.actPrimary}`} type="button" onClick={onEdit}>
            Edit build
          </button>
        )}
        <button className={u.act} type="button" onClick={copy}>
          {copied ? "Link copied" : "Copy build link"}
        </button>
      </div>
    </section>
  );
}
