import { Link, Outlet } from "@tanstack/react-router";

export function SiteLayout() {
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
          <nav aria-label="Main" className="text-[15px]">
            <Link to="/" hash="browse">
              All guns
            </Link>
          </nav>
        </div>
      </header>
      <div className="flex-1">
        <Outlet />
      </div>
      <footer className="mx-auto w-full max-w-[1376px] border-t border-line px-4 py-5 text-[13px] text-muted sm:px-8">
        Independent fan tool, not affiliated with Digital Extremes. Numbers are calculator estimates;
        check them in the arsenal.
      </footer>
    </div>
  );
}
