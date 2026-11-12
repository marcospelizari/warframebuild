/** URL segment of a faction name; the server uses the same rule (app/api/pages.py). */
export function factionSlug(name: string): string {
  return name.toLowerCase().replace(/ /g, "-");
}
