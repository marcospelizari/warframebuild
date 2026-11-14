import type { ReactNode } from "react";
import { SITE, usePageTitle } from "@/lib/usePageTitle";

/** Public repository: the AGPL source offer for visitors of the site (Q22, T4). */
export const SOURCE_URL = "https://gitlab.com/warframebuild/warframebuild";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="mb-10">
      <h2 id={`${id}-title`} className="mt-0 mb-3 font-display text-2xl font-normal">
        {title}
      </h2>
      <div className="flex flex-col gap-3 leading-relaxed text-soft">{children}</div>
    </section>
  );
}

/** Terms, privacy, licences and credits (T4, Q22, G40). */
export function AboutPage() {
  usePageTitle(`About | ${SITE}`);
  return (
    <main className="mx-auto max-w-[760px] px-4 pt-11 pb-16 sm:px-8">
      <h1 className="mt-0 mb-8 text-center font-display text-4xl leading-tight font-normal">
        About warframeBuild
      </h1>
      <Section id="terms" title="Terms">
        <p>
          warframeBuild is a free, non-commercial fan tool. It is not affiliated with, endorsed by
          or sponsored by Digital Extremes. Warframe is their trademark.
        </p>
        <p>
          Builds and kill times are calculator estimates and may be wrong. The site is provided as
          is, without warranty of any kind. Check numbers in the in-game arsenal.
        </p>
      </Section>
      <Section id="privacy" title="Privacy">
        <p>
          No accounts, no cookies, no analytics, no ads. The server writes no access log. To limit
          request rates it keeps each visitor's IP address in memory only, never on disk; it is
          gone when the server restarts.
        </p>
      </Section>
      <Section id="licences" title="Source code and licences">
        <p>
          The source code is licensed under the GNU AGPL-3.0:{" "}
          <a href={SOURCE_URL}>{SOURCE_URL.replace("https://", "")}</a>.
        </p>
        <p>
          Builds use values from the WARFRAME Wiki, so the build data shown here is shared under{" "}
          <a href="https://creativecommons.org/licenses/by-nc-sa/3.0/">CC BY-NC-SA 3.0</a>, as is
          the wiki. Data from WFCD and warframe-public-export-plus is under the MIT License. Full
          notices: <a href={`${SOURCE_URL}/-/blob/master/NOTICE`}>NOTICE</a>.
        </p>
      </Section>
      <Section id="credits" title="Credits">
        <ul className="m-0 flex flex-col gap-2 pl-5">
          <li>
            <a href="https://www.digitalextremes.com/">Digital Extremes</a>: game data from the
            official Public Export; game images, unmodified, used under the{" "}
            <a href="https://www.warframe.com/contentpolicy">Warframe Content Policy</a>.
          </li>
          <li>
            <a href="https://wiki.warframe.com">WARFRAME Wiki</a> contributors: damage formulas,
            Incarnon evolutions, enemies and faction modifiers, Archon Shards, mod card images.
          </li>
          <li>
            <a href="https://github.com/WFCD">Warframe Community Developers (WFCD)</a>:
            warframe-items and warframestat.us.
          </li>
          <li>
            <a href="https://github.com/calamity-inc/warframe-public-export-plus">
              warframe-public-export-plus
            </a>{" "}
            (Calamity, Inc. and AMelonInsideLemon): mod and weapon compatibility tags.
          </li>
        </ul>
      </Section>
    </main>
  );
}
