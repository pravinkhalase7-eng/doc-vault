"use client";

import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function distance(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

type Zoom = { scale: number; x: number; y: number };

export function ZoomStage({
  naturalW,
  naturalH,
  active,
  onZoomed,
  onSingleTap,
  children,
}: {
  naturalW: number;
  naturalH: number;
  active: boolean;
  onZoomed?: (zoomed: boolean) => void;
  onSingleTap?: () => void;
  children: ReactNode;
}) {
  const viewRef = useRef<HTMLDivElement>(null);
  const zoomRef = useRef<Zoom>({ scale: 1, x: 0, y: 0 });
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; scale: number; x: number; y: number } | null>(null);
  const lastTap = useRef(0);
  const moved = useRef(false);
  const [, bump] = useState(0);
  const zoomed = zoomRef.current.scale > 1.02;

  function viewSize() {
    const el = viewRef.current;
    return { vw: el?.clientWidth || 1, vh: el?.clientHeight || 1 };
  }

  function fitScale() {
    if (!naturalW || !naturalH) return 1;
    const { vw, vh } = viewSize();
    return Math.min(vw / naturalW, vh / naturalH);
  }

  function maxScale() {
    const { vw } = viewSize();
    return Math.max(4, naturalW / Math.max(1, vw) / Math.max(fitScale(), 0.0001));
  }

  function apply(next: Zoom) {
    const { vw, vh } = viewSize();
    const fit = fitScale();
    const scale = clamp(next.scale, 1, maxScale());
    const dw = naturalW * fit * scale;
    const dh = naturalH * fit * scale;
    const maxX = Math.max(0, (dw - vw) / 2);
    const maxY = Math.max(0, (dh - vh) / 2);
    zoomRef.current = {
      scale,
      x: scale <= 1.01 ? 0 : clamp(next.x, -maxX, maxX),
      y: scale <= 1.01 ? 0 : clamp(next.y, -maxY, maxY),
    };
    onZoomed?.(zoomRef.current.scale > 1.02);
    bump((n) => n + 1);
  }

  useEffect(() => {
    if (!active) apply({ scale: 1, x: 0, y: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    function onWheel(event: WheelEvent) {
      const pinching = event.ctrlKey || event.metaKey || zoomRef.current.scale > 1.02;
      if (!pinching) return;
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      apply({ ...zoomRef.current, scale: zoomRef.current.scale * factor });
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [naturalW, naturalH]);

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    moved.current = false;
    if (pointers.current.size === 2) {
      event.currentTarget.setPointerCapture(event.pointerId);
      const [a, b] = [...pointers.current.values()];
      pinch.current = {
        dist: Math.max(1, distance(a, b)),
        scale: zoomRef.current.scale,
        x: zoomRef.current.x,
        y: zoomRef.current.y,
      };
      return;
    }
    if (zoomRef.current.scale > 1.02) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!pointers.current.has(event.pointerId)) return;
    const prev = pointers.current.get(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (prev && Math.hypot(event.clientX - prev.x, event.clientY - prev.y) > 4) moved.current = true;
    if (pointers.current.size === 2 && pinch.current) {
      event.preventDefault();
      const [a, b] = [...pointers.current.values()];
      const ratio = distance(a, b) / pinch.current.dist;
      apply({
        scale: pinch.current.scale * ratio,
        x: pinch.current.x,
        y: pinch.current.y,
      });
      return;
    }
    if (pointers.current.size === 1 && zoomRef.current.scale > 1.02 && prev) {
      event.preventDefault();
      apply({
        ...zoomRef.current,
        x: zoomRef.current.x + (event.clientX - prev.x),
        y: zoomRef.current.y + (event.clientY - prev.y),
      });
    }
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (moved.current) return;
    const now = Date.now();
    const rect = viewRef.current?.getBoundingClientRect();
    const px = event.clientX - (rect?.left || 0);
    const py = event.clientY - (rect?.top || 0);
    if (now - lastTap.current < 280) {
      lastTap.current = 0;
      const { vw, vh } = viewSize();
      if (zoomRef.current.scale > 1.05) {
        apply({ scale: 1, x: 0, y: 0 });
      } else {
        apply({
          scale: Math.min(2.6, maxScale()),
          x: (vw / 2 - px) * 1.4,
          y: (vh / 2 - py) * 1.4,
        });
      }
      return;
    }
    lastTap.current = now;
    window.setTimeout(() => {
      if (!lastTap.current) return;
      if (Date.now() - lastTap.current < 260) return;
      lastTap.current = 0;
      onSingleTap?.();
    }, 260);
  }

  const { scale, x, y } = zoomRef.current;
  const fit = fitScale();
  const ready = naturalW > 0 && naturalH > 0;

  return (
    <div
      ref={viewRef}
      className={zoomed ? "absolute inset-0 z-10 overflow-hidden touch-none" : "absolute inset-0 z-10 overflow-hidden touch-pan-y"}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div
        className="absolute left-1/2 top-1/2 will-change-transform"
        style={{
          width: ready ? naturalW : "100%",
          height: ready ? naturalH : "100%",
          pointerEvents: "none",
          transform: `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${ready ? fit * scale : 1})`,
          transformOrigin: "center center",
        }}
      >
        {children}
      </div>
    </div>
  );
}
