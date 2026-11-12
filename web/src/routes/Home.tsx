import { useQuery } from "@tanstack/react-query";
import { getWeapons } from "@/api/client";
import { GunBrowser } from "@/components/GunBrowser";
import { GunSearch } from "@/components/GunSearch";
import u from "@/components/ui.module.css";
import h from "./Home.module.css";

export function Home() {
  const list = useQuery({ queryKey: ["weapons"], queryFn: getWeapons });
  return (
    <>
      <section className={h.hero}>
        <div className="mx-auto flex max-w-[1000px] flex-col items-center px-4 pt-11 pb-10 text-center sm:px-8">
          <div className="flex max-w-full items-center justify-center gap-6">
            <span className={`${u.orn} ${u.ornLeft}`} aria-hidden="true" />
            <h1 className="m-0 font-display text-4xl leading-tight font-normal">Gun builds for Warframe</h1>
            <span className={u.orn} aria-hidden="true" />
          </div>
          <p className="mt-3 mb-6 max-w-[60ch] text-base leading-relaxed text-soft">
            Calculated mod builds for primaries and secondaries, tested against level 120 Steel Path
            enemies. Worth checking in your arsenal.
          </p>
          <GunSearch list={list.data} />
        </div>
      </section>
      <main className="mx-auto max-w-[1376px] px-4 pb-16 sm:px-8">
        {list.isError ? (
          <p role="alert" className="pt-10 text-soft">
            Could not load the gun list: {list.error.message}
          </p>
        ) : (
          <GunBrowser weapons={list.data?.weapons} />
        )}
      </main>
    </>
  );
}
