import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { UpdatesResponse } from "@/api/client";
import { renderPage } from "@/test/render";
import { UpdatesPage } from "./Updates";

const body: UpdatesResponse = {
  data: { game_update: "Update 44.0", checked: "2026-11-12" },
  updates: [
    {
      kind: "game",
      release: "r2",
      date: "2026-11-20",
      game_update: "Update 44.1",
      summary: ["1 mod changed: Bore.", "Now only partly calculated: Bore."],
      entries: [
        {
          key: "/Bore",
          kind: "mod",
          name: "Bore",
          change: "changed",
          before: ["+120% Puncture"],
          after: ["+180% Puncture", "[PH] +1 max Puncture stacks"],
          support_before: "full",
          support_after: "partial",
          unparsed: ["[PH] +1 max Puncture stacks"],
        },
      ],
      guns: [
        {
          slug: "lex-prime",
          name: "Lex Prime",
          change: "changed",
          stats_changed: false,
          builds: [
            {
              build: "recommended",
              removed: ["Hornet Strike"],
              added: ["Bore"],
              kill_before: 2,
              kill_after: 1.5,
            },
          ],
        },
      ],
      unavailable: [],
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

function answer(response: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(response))));
}

test("an update shows its summary, the text change and the build change", async () => {
  answer(body);
  renderPage(UpdatesPage);
  const card = await screen.findByRole("article", { name: "20 Nov 2026" });
  expect(within(card).getByText("Game update")).toBeInTheDocument();
  expect(within(card).getByText("Now only partly calculated: Bore.")).toBeInTheDocument();

  fireEvent.click(within(card).getByText("Text changes (1)"));
  expect(within(card).getByText("calculated → partly calculated")).toBeInTheDocument();
  expect(within(card).getByText("+120% Puncture").tagName).toBe("DEL");
  expect(within(card).getByText("+180% Puncture")).toBeInTheDocument();

  fireEvent.click(within(card).getByText("Builds (1 gun)"));
  expect(within(card).getByRole("link", { name: "Lex Prime" })).toHaveAttribute(
    "href",
    "/w/lex-prime",
  );
  expect(within(card).getByText("Hornet Strike → Bore")).toBeInTheDocument();
  expect(within(card).getByText("average kill 2 s → 1.5 s")).toBeInTheDocument();
});

test("no updates yet says so", async () => {
  answer({ ...body, updates: [] });
  renderPage(UpdatesPage);
  expect(await screen.findByText(/No updates recorded yet/)).toBeInTheDocument();
});
