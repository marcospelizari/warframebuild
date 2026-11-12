import { useEffect, useRef, useState } from "react";
import type { Row } from "@/lib/editor";
import s from "./Picker.module.css";
import u from "./ui.module.css";

type Item = { unique_name: string; name: string; stats: string[]; image: string | null; support: string };

type Props<T extends Item> = {
  title: string;
  rows: Row<T>[];
  drain?: (item: T) => number;
  onPick: (id: string | null) => void;
  onClose: () => void;
};

/** Modal list with search (F7): rows that cannot go here stay visible, greyed, with why. */
export function Picker<T extends Item>({ title, rows, drain, onPick, onClose }: Props<T>) {
  const ref = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState("");
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }, []);
  const q = text.trim().toLocaleLowerCase();
  const shown = q ? rows.filter((r) => r.item.name.toLocaleLowerCase().includes(q)) : rows;
  return (
    <dialog ref={ref} className={s.dialog} aria-labelledby="picker-title" onClose={onClose}>
      <div className={s.head}>
        <h2 id="picker-title" className="m-0 font-display text-2xl font-normal">
          {title}
        </h2>
        <button className={`${u.act} ml-auto`} type="button" onClick={() => onPick(null)}>
          Leave empty
        </button>
        <button className={u.lnk} type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="px-[18px] pb-2">
        <label htmlFor="picker-find" className={u.srOnly}>
          Search by name
        </label>
        <input
          id="picker-find"
          className={s.find}
          type="search"
          autoComplete="off"
          placeholder="Search by name"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <ul className={s.list} aria-label={title}>
        {shown.map(({ item, reason, current }) => (
          <li key={item.unique_name}>
            <button
              className={s.row}
              type="button"
              aria-disabled={reason ? true : undefined}
              aria-current={current || undefined}
              onClick={() => {
                if (!reason) onPick(item.unique_name);
              }}
            >
              {item.image ? (
                <img className={s.thumb} src={item.image} alt="" loading="lazy" />
              ) : (
                <span className={s.noThumb} aria-hidden="true" />
              )}
              <span className={s.text}>
                <span className="text-base font-semibold">{item.name}</span>
                <span className={s.stats}>{item.stats.join(", ").replace(/\n/g, " ")}</span>
                {reason && <span className={s.why}>{reason}</span>}
                {!reason && item.support !== "full" && (
                  <span className={s.stats}>
                    {item.support === "partial" ? "Only partly calculated" : "Its effect is not calculated"}
                  </span>
                )}
              </span>
              {drain && <span className={s.drain}>{drain(item)}</span>}
            </button>
          </li>
        ))}
        {shown.length === 0 && <li className="p-4 text-soft">Nothing by that name.</li>}
      </ul>
    </dialog>
  );
}
