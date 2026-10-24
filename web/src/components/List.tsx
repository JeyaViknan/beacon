import { Link } from "react-router-dom";
import type { SymbolName } from "../symbols/names";
import { Icon } from "./Icon";

/** An inset grouped section: optional header and footer around a rounded list of rows. */
export function Section({
  header,
  footer,
  children,
  className = "",
}: {
  header?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      {header ? <h2 className="mb-[7px] px-4 text-footnote text-label-2 uppercase">{header}</h2> : null}
      <div className="list">{children}</div>
      {footer ? <p className="mt-[7px] px-4 text-footnote text-label-2">{footer}</p> : null}
    </section>
  );
}

/** The coloured rounded square in front of a row, as in the Settings app. */
export function IconTile({ name, color }: { name: SymbolName; color: string }) {
  return (
    <span className="flex size-[30px] flex-none items-center justify-center rounded-[8px] text-white" style={{ background: color }}>
      <Icon name={name} className="size-[26px]" />
    </span>
  );
}

interface RowContent {
  /** A Settings-style tile, or a bare symbol in the given colour. */
  tile?: { name: SymbolName; color: string };
  symbol?: { name: SymbolName; color: string; label?: string };
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  /** Trailing secondary text, like a Settings value. */
  value?: React.ReactNode;
  /** Anything else on the trailing side (a switch, a badge). */
  trailing?: React.ReactNode;
  chevron?: boolean;
  /** Action rows are tinted text; destructive ones red. */
  tone?: "default" | "action" | "destructive";
  /** Centred action text, as in "Log Out". */
  center?: boolean;
}

function Content({ tile, symbol, title, subtitle, value, trailing, chevron, tone = "default", center }: RowContent) {
  const titleColor = tone === "action" ? "text-tint" : tone === "destructive" ? "text-red" : "";
  return (
    <>
      {tile ? <IconTile name={tile.name} color={tile.color} /> : null}
      {symbol ? (
        <span style={{ color: symbol.color }}>
          <Icon name={symbol.name} className="size-7" label={symbol.label} />
        </span>
      ) : null}
      <span className={`min-w-0 flex-1 ${center ? "text-center" : ""}`}>
        <span className={`block text-body ${titleColor}`}>{title}</span>
        {subtitle ? <span className="mt-0.5 block text-subhead text-label-2">{subtitle}</span> : null}
      </span>
      {value !== undefined ? <span className="max-w-[55%] truncate text-body text-label-2 tabular">{value}</span> : null}
      {trailing}
      {chevron ? (
        <span className="-mr-1 text-label-3">
          <Icon name="chevron.right" className="size-5" />
        </span>
      ) : null}
    </>
  );
}

const rowCls = "flex min-h-[52px] w-full items-center gap-3 px-4 py-2.5 text-left";
const inset = (c: RowContent) => ({ "--separator-inset": c.tile ? "58px" : c.symbol ? "56px" : "16px" }) as React.CSSProperties;

export function Row(props: RowContent) {
  return (
    <div className={rowCls} style={inset(props)}>
      <Content {...props} />
    </div>
  );
}

export function RowLink({ to, label, ...props }: RowContent & { to: string; label?: string }) {
  return (
    <Link to={to} className={`pressable ${rowCls}`} style={inset(props)} aria-label={label}>
      <Content chevron {...props} />
    </Link>
  );
}

export function RowButton({
  onClick,
  disabled,
  ...props
}: RowContent & { onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`pressable ${rowCls} disabled:opacity-40`}
      style={inset(props)}
    >
      <Content {...props} />
    </button>
  );
}

export function RowExternal({ href, ...props }: RowContent & { href: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className={`pressable ${rowCls}`} style={inset(props)}>
      <Content
        {...props}
        trailing={
          <span className="text-label-3">
            <Icon name="arrow.up.right" className="size-5" />
          </span>
        }
      />
    </a>
  );
}

/** UISwitch. */
export function Switch({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative inline-flex h-[31px] w-[51px] flex-none items-center rounded-full transition-colors duration-200 disabled:opacity-50"
      style={{ background: checked ? "var(--green)" : "var(--fill)" }}
    >
      <span
        className="absolute size-[27px] rounded-full bg-white transition-transform duration-200 motion-reduce:transition-none"
        style={{
          transform: `translateX(${checked ? 22 : 2}px)`,
          boxShadow: "0 3px 8px rgb(0 0 0 / 0.15), 0 3px 1px rgb(0 0 0 / 0.06)",
        }}
      />
    </button>
  );
}

/** UISegmentedControl. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="flex h-9 rounded-full bg-fill-3 p-[2px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className="flex-1 rounded-full text-footnote font-semibold"
          style={value === o.value ? { background: "var(--segment)", boxShadow: "var(--segment-shadow)" } : undefined}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
