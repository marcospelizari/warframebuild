import type { PerkTier } from "@/api/client";

type Props = {
  tiers: PerkTier[];
  perks: string[];
  onPerks: (perks: string[]) => void;
  busy: boolean;
  error: string | null;
  onReset: () => void;
};

/** Shown while editing: Incarnon evolutions per tier, calculation state, way back. */
export function EditBar({ tiers, perks, onPerks, busy, error, onReset }: Props) {
  const chosen = (tier: PerkTier) => tier.options.find((o) => perks.includes(o.name))?.name ?? "";
  const set = (tier: PerkTier, name: string) => {
    const names = new Set(tier.options.map((o) => o.name));
    const rest = perks.filter((p) => !names.has(p));
    onPerks(name ? [...rest, name] : rest);
  };
  return (
    <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 border border-line bg-panel px-4 py-3">
      <p className="m-0 flex-[1_1_260px] text-[15px] text-soft" aria-live="polite">
        {error ? (
          <span role="alert" className="text-[#ff9a7a]">
            {error}
          </span>
        ) : busy ? (
          "Calculating…"
        ) : (
          "Editing. Pick a slot to change it; numbers update as you go."
        )}
      </p>
      {tiers.map((tier) => (
        <label key={tier.tier} className="flex items-center gap-2 text-sm text-muted">
          Evolution {tier.tier}
          <select
            className="min-h-[44px] border border-line bg-surface px-2 text-cream"
            value={chosen(tier)}
            onChange={(e) => set(tier, e.target.value)}
          >
            <option value="">None</option>
            {tier.options.map((o) => (
              <option key={o.name} value={o.name}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
      ))}
      <button className="text-[15px] text-cyan underline min-h-[44px]" type="button" onClick={onReset}>
        Back to the calculated build
      </button>
    </div>
  );
}
