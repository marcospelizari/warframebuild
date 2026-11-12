import type { DamageType } from "@/api/client";
import { damageIcon } from "./art";
import u from "./ui.module.css";

const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

type Props = { elements: DamageType[]; value: DamageType | null; onChange: (e: DamageType) => void };

/** Progenitor bonus element; only optimized elements are offered (C7). */
export function ElementSwitch({ elements, value, onChange }: Props) {
  if (elements.length < 2) return null;
  return (
    <div role="group" aria-label="Bonus element" className="flex flex-wrap items-center justify-center gap-1.5">
      <span className="mr-1 text-sm text-muted">Bonus element</span>
      {elements.map((e) => {
        const icon = damageIcon(e);
        return (
          <button
            key={e}
            className={`${u.chip} inline-flex items-center gap-1.5`}
            type="button"
            aria-pressed={e === value}
            onClick={() => onChange(e)}
          >
            {icon && <img src={icon} alt="" className="size-4" />}
            {cap(e)}
          </button>
        );
      })}
    </div>
  );
}
