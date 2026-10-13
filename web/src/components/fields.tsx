"use client";

import { createContext, useContext, useId, type ReactNode } from "react";

import { InfoTip } from "@/components/InfoTip";

const FieldIdContext = createContext<string | undefined>(undefined);

/** The id the surrounding Field's label points at; inputs use it so the label stays linked. */
export function useFieldId() {
  return useContext(FieldIdContext);
}

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <span className="flex items-center gap-1">
        <label htmlFor={id} className="label">
          {label}
        </label>
        {hint && <InfoTip label={label}>{hint}</InfoTip>}
      </span>
      <FieldIdContext.Provider value={id}>{children}</FieldIdContext.Provider>
    </div>
  );
}

/** A small labelled checkbox, with an optional (?) explanation. */
export function Checkbox({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-text-2 hover:text-text">
        <input
          type="checkbox"
          className="h-3.5 w-3.5 cursor-pointer"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        {label}
      </label>
      {hint && <InfoTip label={label}>{hint}</InfoTip>}
    </span>
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
  const id = useFieldId();
  return (
    <div className="relative">
      <input
        id={id}
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

/** A number input that may be left empty, meaning "no value" (e.g. no upper limit). */
export function OptionalNumberInput({
  value,
  onChange,
  min,
  step = 1,
  suffix,
  placeholder,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  min?: number;
  step?: number;
  suffix?: string;
  placeholder?: string;
}) {
  const id = useFieldId();
  return (
    <div className="relative">
      <input
        id={id}
        type="number"
        className={`${inputClass} placeholder:text-muted ${suffix ? "pr-8" : ""}`}
        value={value ?? ""}
        min={min}
        step={step}
        placeholder={placeholder}
        onChange={(e) => {
          if (e.target.value === "") return onChange(null);
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
  const id = useFieldId();
  return (
    <div className="flex h-9 items-center gap-3">
      <input
        id={id}
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
