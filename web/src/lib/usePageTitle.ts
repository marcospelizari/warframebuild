import { useEffect } from "react";

export const SITE = "warframeBuild";

/** The tab title for client-side page changes; the server sets the same on a full load (G88). */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = title;
  }, [title]);
}
