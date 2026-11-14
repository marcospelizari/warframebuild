import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { getData } from "@/api/client";
import { dateLabel } from "@/lib/format";
import { SOURCE_URL } from "@/routes/About";

/** U4: which game data the builds come from, so an old date is visible on every page. */
function DataLine() {
  const data = useQuery({ queryKey: ["data"], queryFn: getData, staleTime: Infinity });
  if (!data.data) return null;
  const { game_update, checked } = data.data;
  return (
    <p className="m-0 mb-1.5">
      <Link to="/updates" className="text-muted">
        Game data: {game_update ? `${game_update} · ` : ""}checked {dateLabel(checked)}
      </Link>
    </p>
  );
}

/** A new page moves keyboard and screen-reader focus to its content; a build tab or an
    edit on the same gun (/w/<gun>/...) stays where it is. */
function usePageFocus() {
  const page = useRouterState({ select: (s) => s.location.pathname.split("/").slice(0, 3).join("/") });
  const main = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus({ preventScroll: true }); // a #hash link keeps its own scroll
  }, [page]);
  return main;
}

export function SiteLayout() {
  const main = usePageFocus();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-[1376px] flex-wrap items-center justify-between gap-6 px-4 py-4 sm:px-8">
          <Link
            to="/"
            className="flex items-center gap-2.5 font-display text-2xl leading-none text-cream no-underline hover:text-cream"
          >
            <span aria-hidden="true" className="size-[9px] rotate-45 border border-gold" />
            warframeBuild
          </Link>
          <nav aria-label="Main" className="flex gap-6 text-[15px]">
            <Link to="/" hash="browse">
              All guns
            </Link>
            <Link to="/tier-list/$category" params={{ category: "primary" }}>
              Tier list
            </Link>
            <Link to="/updates">Updates</Link>
          </nav>
        </div>
      </header>
      <div ref={main} tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </div>
      <footer className="mx-auto w-full max-w-[1376px] border-t border-line px-4 py-5 text-[13px] text-muted sm:px-8">
        <DataLine />
        Independent fan tool, not affiliated with Digital Extremes. Numbers are calculator estimates;
        check them in the arsenal.
        <nav aria-label="Site" className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          <Link to="/about" className="text-muted">
            About, terms and privacy
          </Link>
          <Link to="/about" hash="credits" className="text-muted">
            Credits
          </Link>
          <a href={SOURCE_URL} className="text-muted">
            Source code (AGPL-3.0)
          </a>
          <Link to="/about" hash="licences" className="text-muted">
            Build data: CC BY-NC-SA 3.0
          </Link>
        </nav>
      </footer>
    </div>
  );
}
