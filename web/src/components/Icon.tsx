import { SYMBOLS } from "@symbols";
import type { SymbolName } from "../symbols/names";

/**
 * A symbol by its SF Symbols name, in the current text colour. The iPhone app build draws the
 * real SF Symbols; the web app draws Beacon's look-alikes (ADR 0016). Decorative unless `label`.
 */
export function Icon({ name, className = "size-6", label }: { name: SymbolName; className?: string; label?: string }) {
  const symbol = SYMBOLS[name];
  return (
    <svg
      viewBox={symbol.viewBox}
      fill="currentColor"
      className={`flex-none ${className}`}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      // Static markup from our own source (names.ts / fallback.ts or the build-time export).
      dangerouslySetInnerHTML={{ __html: symbol.body }}
    />
  );
}
