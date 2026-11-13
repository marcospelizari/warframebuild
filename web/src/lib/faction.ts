/** URL segment of the Primer build: /w/<slug>/primer (no faction has this name). */
export const PRIMER = "primer";

/** URL segment of a faction name; the server uses the same rule (app/api/pages.py). */
export function factionSlug(name: string): string {
  return name.toLowerCase().replace(/ /g, "-");
}
