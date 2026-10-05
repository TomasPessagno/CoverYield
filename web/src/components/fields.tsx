"use client";

import type { ReactNode } from "react";

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex min-w-0 flex-col gap-1.5 ${className}`} title={hint}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "num h-9 w-full rounded-sm border border-border bg-panel px-2.5 text-sm text-text outline-none transition-colors hover:border-border-strong focus:border-accent";

export function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
}) {
  return (
    <div className="relative">
      <input
        type="number"
        className={`${inputClass} ${suffix ? "pr-8" : ""}`}
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const v = e.target.valueAsNumber;
          if (Number.isFinite(v)) onChange(v);
        }}
      />
      {suffix && (
        <span className="num pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs text-muted">
          {suffix}
        </span>
      )}
    </div>
  );
}

export function SliderInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  format = (v) => String(v),
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  format?: (v: number) => string;
}) {
  return (
    <div className="flex h-9 items-center gap-3">
      <input
        type="range"
        className="h-1 w-full cursor-pointer"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(e.target.valueAsNumber)}
      />
      <span className="num w-14 shrink-0 text-right text-sm text-text">{format(value)}</span>
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  type = "button",
  variant = "primary",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  variant?: "primary" | "ghost";
}) {
  const styles =
    variant === "primary"
      ? "bg-accent text-accent-ink hover:opacity-85 disabled:opacity-40"
      : "border border-border text-text-2 hover:border-border-strong hover:text-text disabled:opacity-50";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`h-9 shrink-0 rounded-sm px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles}`}
    >
      {children}
    </button>
  );
}

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-sm border border-border bg-panel ${className}`}>
      {(title || right) && (
        <div className="flex items-center justify-between gap-4 border-b border-border px-4 py-2.5">
          {title && <h2 className="label text-text-2">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-sm border border-down/40 bg-down/10 px-3 py-2 text-sm text-down">
      {children}
    </p>
  );
}
