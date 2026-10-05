"use client";

import { useEffect, useId, useRef, useState } from "react";

import { api, type TickerMatch, type UniverseTicker } from "@/lib/api";

type Option = { symbol: string; label: string };

/**
 * Ticker input with suggestions: the built-in universe matches instantly,
 * Yahoo search results arrive after a short debounce. Enter submits.
 */
export function TickerSearch({
  universe,
  onSubmit,
  initial = "",
}: {
  universe: UniverseTicker[];
  onSubmit: (symbol: string) => void;
  initial?: string;
}) {
  const [query, setQuery] = useState(initial);
  const [remote, setRemote] = useState<TickerMatch[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const boxRef = useRef<HTMLDivElement>(null);

  const q = query.trim().toLowerCase();
  const local: Option[] = q
    ? universe
        .filter((t) => t.symbol.toLowerCase().startsWith(q) || t.name.toLowerCase().includes(q))
        .slice(0, 6)
        .map((t) => ({ symbol: t.symbol, label: t.name }))
    : universe.slice(0, 8).map((t) => ({ symbol: t.symbol, label: t.name }));
  const seen = new Set(local.map((o) => o.symbol));
  const options: Option[] = [
    ...local,
    ...(q ? remote : [])
      .filter((r) => !seen.has(r.symbol))
      .slice(0, 6)
      .map((r) => ({ symbol: r.symbol, label: r.label.replace(/^\S+\s+—\s+/, "") })),
  ];

  useEffect(() => {
    if (q.length < 1) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api
        .search(q, ctrl.signal)
        .then(setRemote)
        .catch(() => {});
    }, 250);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function choose(symbol: string) {
    setQuery(symbol);
    setOpen(false);
    onSubmit(symbol);
  }

  return (
    <div ref={boxRef} className="relative">
      <input
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        className="num h-9 w-full rounded-sm border border-border bg-panel px-2.5 text-sm text-text uppercase outline-none placeholder:text-muted placeholder:normal-case hover:border-border-strong focus:border-accent"
        placeholder="Ticker or company, e.g. AAPL"
        value={query}
        spellCheck={false}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setActive((a) => Math.min(a + 1, options.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            const pick = open && options[active] ? options[active].symbol : query.trim();
            if (pick) choose(pick.toUpperCase());
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute top-10 right-0 left-0 z-30 max-h-80 overflow-auto rounded-sm border border-border bg-panel-2 py-1 shadow-xl shadow-black/40"
        >
          {options.map((o, i) => (
            <li
              key={o.symbol}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(o.symbol);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-baseline gap-3 px-2.5 py-1.5 text-sm ${
                i === active ? "bg-panel-2" : ""
              }`}
            >
              <span className="num w-20 shrink-0 font-medium text-text">{o.symbol}</span>
              <span className="truncate text-text-2">{o.label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
