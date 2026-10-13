"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

const WIDTH = 280;
const GAP = 6;
const EDGE = 8;

/**
 * A small (?) button that explains something. Opens on hover, keyboard focus or
 * tap (tap again or tap elsewhere to close). The bubble renders in a portal with
 * fixed positioning, so scrolling tables and panels never clip it.
 */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const id = useId();
  const visible = hovered || pinned;

  // Place below the button, or above when there's no room; keep inside the viewport.
  // Runs before paint, so the bubble never flashes in the wrong spot.
  useLayoutEffect(() => {
    const button = buttonRef.current;
    const tip = tipRef.current;
    if (!visible || !button || !tip) return;
    const r = button.getBoundingClientRect();
    const width = tip.offsetWidth;
    const left = Math.min(
      Math.max(r.left + r.width / 2 - width / 2, EDGE),
      window.innerWidth - width - EDGE,
    );
    const below = r.bottom + GAP;
    const fitsBelow = below + tip.offsetHeight <= window.innerHeight - EDGE;
    tip.style.left = `${left}px`;
    tip.style.top = `${fitsBelow ? below : Math.max(r.top - GAP - tip.offsetHeight, EDGE)}px`;
  }, [visible]);

  useEffect(() => {
    if (!visible) return;
    const close = () => {
      setHovered(false);
      setPinned(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onPointer = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!buttonRef.current?.contains(target) && !tipRef.current?.contains(target)) close();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [visible]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={visible ? id : undefined}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
        onClick={(e) => {
          e.stopPropagation();
          if (visible && pinned) {
            setPinned(false);
            setHovered(false);
          } else {
            setPinned(true);
          }
        }}
        className="inline-flex h-3.5 w-3.5 shrink-0 cursor-help items-center justify-center rounded-full border border-current text-[9px] leading-none font-medium text-muted opacity-60 transition-opacity hover:opacity-100 focus-visible:opacity-100"
      >
        ?
      </button>
      {visible &&
        createPortal(
          <div
            ref={tipRef}
            id={id}
            role="tooltip"
            style={{ width: Math.min(WIDTH, window.innerWidth - 2 * EDGE) }}
            className="fixed z-50 rounded-sm border border-border-strong bg-panel px-3 py-2 text-left text-xs leading-relaxed font-normal whitespace-normal text-text-2 shadow-lg"
          >
            <p className="mb-0.5 font-medium text-text">{label}</p>
            {children}
          </div>,
          document.body,
        )}
    </>
  );
}
