import h from "./GunPicture.module.css";

/** A gun icon from /img/weapons, or an empty diamond when it is not cached. */
export function GunPicture({ src, small = false }: { src: string | null; small?: boolean }) {
  const cls = small ? `${h.pic} ${h.picSm}` : h.pic;
  if (!src) return <span className={`${cls} ${h.blank}`} aria-hidden="true" />;
  return <img className={cls} src={src} alt="" loading="lazy" />;
}
