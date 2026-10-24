import { useEffect, useState } from "react";

/** Resolve a CSS custom property to a concrete colour (SVG chart attributes need real values). */
export function useCssVar(name: string, fallback: string): string {
  const read = () => {
    if (typeof window === "undefined") return fallback;
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  };
  const [value, setValue] = useState(read);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const update = () => setValue(read());
    mq?.addEventListener?.("change", update);
    return () => mq?.removeEventListener?.("change", update);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);
  return value;
}
