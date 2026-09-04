"use client";

import { useEffect, useRef, useState } from "react";
import { clampCrop, type CropNorm } from "@/lib/scan-pdf";

const DEFAULT_CROP: CropNorm = { x: 0.06, y: 0.06, w: 0.88, h: 0.88 };

type Handle = "nw" | "ne" | "sw" | "se" | "move";

export function PageCropper({
  src,
  onChange,
}: {
  src: string;
  onChange: (crop: CropNorm) => void;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [natural, setNatural] = useState({ w: 1, h: 1 });
  const [crop, setCrop] = useState<CropNorm>(DEFAULT_CROP);
  const drag = useRef<{ handle: Handle; start: CropNorm; x: number; y: number } | null>(null);

  useEffect(() => {
    onChange(crop);
  }, [crop, onChange]);

  function displayRect() {
    const el = frame.current;
    const vw = el?.clientWidth || 1;
    const vh = el?.clientHeight || 1;
    const scale = Math.min(vw / natural.w, vh / natural.h);
    const dw = natural.w * scale;
    const dh = natural.h * scale;
    return { left: (vw - dw) / 2, top: (vh - dh) / 2, dw, dh };
  }

  function updateFromPointer(event: React.PointerEvent, handle: Handle, start: CropNorm, originX: number, originY: number) {
    const box = displayRect();
    if (box.dw < 8 || box.dh < 8) return;
    const dx = (event.clientX - originX) / box.dw;
    const dy = (event.clientY - originY) / box.dh;
    let next = { ...start };
    if (handle === "move") {
      next.x = start.x + dx;
      next.y = start.y + dy;
    } else {
      if (handle.includes("w")) {
        next.x = start.x + dx;
        next.w = start.w - dx;
      }
      if (handle.includes("e")) next.w = start.w + dx;
      if (handle.includes("n")) {
        next.y = start.y + dy;
        next.h = start.h - dy;
      }
      if (handle.includes("s")) next.h = start.h + dy;
    }
    next = clampCrop(next);
    if (handle === "move") {
      next.x = Math.min(1 - next.w, Math.max(0, next.x));
      next.y = Math.min(1 - next.h, Math.max(0, next.y));
    }
    setCrop(next);
  }

  function begin(event: React.PointerEvent<HTMLElement>, handle: Handle) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { handle, start: crop, x: event.clientX, y: event.clientY };
  }

  function move(event: React.PointerEvent<HTMLElement>) {
    const current = drag.current;
    if (!current) return;
    updateFromPointer(event, current.handle, current.start, current.x, current.y);
  }

  function end() {
    drag.current = null;
  }

  const box = displayRect();
  const left = box.left + crop.x * box.dw;
  const top = box.top + crop.y * box.dh;
  const width = crop.w * box.dw;
  const height = crop.h * box.dh;

  return (
    <div ref={frame} className="relative h-full w-full overflow-hidden bg-black touch-none">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        draggable={false}
        onLoad={(event) =>
          setNatural({
            w: event.currentTarget.naturalWidth || 1,
            h: event.currentTarget.naturalHeight || 1,
          })
        }
        className="absolute inset-0 h-full w-full object-contain select-none"
      />
      <div
        className="absolute border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]"
        style={{ left, top, width, height }}
        onPointerDown={(event) => begin(event, "move")}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
      >
        {(["nw", "ne", "sw", "se"] as Handle[]).map((handle) => (
          <button
            key={handle}
            type="button"
            aria-label={`Resize ${handle}`}
            className="absolute size-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-white/90"
            style={{
              left: handle.includes("w") ? 0 : "100%",
              top: handle.includes("n") ? 0 : "100%",
            }}
            onPointerDown={(event) => begin(event, handle)}
            onPointerMove={move}
            onPointerUp={end}
            onPointerCancel={end}
          />
        ))}
      </div>
    </div>
  );
}
