"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Bookmark,
  Camera,
  Download,
  FileText,
  FolderInput,
  Heart,
  MessageCircle,
  MoreVertical,
  Play,
  Share2,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { cachedBlobUrl, loadBlobUrl, prefetchReelDocs } from "@/lib/preview-cache";
import { downloadDocument, isShareCancel, shareDocument } from "@/lib/files";
import { useAuth } from "@/lib/auth";
import {
  loadReelLikes,
  loadReelSaves,
  toggleReelLike,
  toggleReelSave,
} from "@/lib/reel-saves";
import { cn } from "@/lib/utils";
import { ZoomStage } from "@/components/reel-zoom";
import { MoveCollectionSheet } from "@/components/move-collection-sheet";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

type ReelDoc = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  size_bytes?: number;
  expiry_date?: string | null;
  ai_classification?: string | null;
  download_count?: number;
  share_count?: number;
  use_count?: number;
};

type Filter = "all" | "liked" | "saved";

function isImage(doc: ReelDoc) {
  return (
    (doc.mime_type || "").startsWith("image/") ||
    /\.(png|jpe?g|gif|webp|heic|heif|bmp|tiff?|avif)$/i.test(doc.original_filename || "")
  );
}

function isVideo(doc: ReelDoc) {
  return (
    (doc.mime_type || "").startsWith("video/") ||
    /\.(mp4|mov|webm|m4v)$/i.test(doc.original_filename || "")
  );
}

function isPdf(doc: ReelDoc) {
  return (doc.mime_type || "").includes("pdf") || /\.pdf$/i.test(doc.original_filename || "");
}

function circularNear(a: number, b: number, n: number, windowSize = 3) {
  if (n <= 1) return true;
  const dist = Math.abs(a - b);
  return Math.min(dist, n - dist) <= windowSize;
}

function kindLabel(doc: ReelDoc) {
  if (isImage(doc)) return "Photo";
  if (isVideo(doc)) return "Video";
  if (isPdf(doc)) return "PDF";
  return "File";
}

function usePreview(doc: ReelDoc, enabled: boolean) {
  const video = isVideo(doc);
  const [jpeg, setJpeg] = useState(
    () => cachedBlobUrl(`/documents/${doc.id}/reel-image`) || cachedBlobUrl(`/documents/${doc.id}/thumbnail`),
  );
  const [file, setFile] = useState(() => (video ? cachedBlobUrl(`/documents/${doc.id}/preview`) : ""));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setFailed(false);
    loadBlobUrl(`/documents/${doc.id}/thumbnail`)
      .then((next) => {
        if (!cancelled) setJpeg((current) => current || next);
      })
      .catch(() => undefined);
    if (video) {
      loadBlobUrl(`/documents/${doc.id}/preview`)
        .then((next) => {
          if (!cancelled) setFile(next);
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
      return () => {
        cancelled = true;
      };
    }
    loadBlobUrl(`/documents/${doc.id}/reel-image`)
      .then((next) => {
        if (!cancelled) setJpeg(next);
      })
      .catch(() => {
        loadBlobUrl(`/documents/${doc.id}/preview`)
          .then((next) => {
            if (!cancelled) setFile(next);
          })
          .catch(() => {
            if (!cancelled) setFailed(true);
          });
      });
    return () => {
      cancelled = true;
    };
  }, [doc.id, enabled, video]);

  return { jpeg, file, url: video ? file : jpeg || file, poster: jpeg, failed };
}

function Action({
  label,
  active,
  danger,
  onClick,
  children,
}: {
  label?: string;
  active?: boolean;
  danger?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} className="flex flex-col items-center gap-1 text-white">
      <span className={cn("drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]", active && "text-rose-400", danger && "text-rose-400")}>
        {children}
      </span>
      {label ? (
        <span
          className={cn(
            "text-[10px] font-medium leading-none drop-shadow-[0_1px_2px_rgba(0,0,0,1)]",
            danger ? "text-rose-300" : "text-white",
          )}
        >
          {label}
        </span>
      ) : null}
    </button>
  );
}

function ReelSlide({
  doc,
  active,
  nearby,
  liked,
  saved,
  muted,
  onMuted,
  onLike,
  onSave,
  onComment,
  onZoomed,
  onDeleted,
}: {
  doc: ReelDoc;
  active: boolean;
  nearby: boolean;
  liked: boolean;
  saved: boolean;
  muted: boolean;
  onMuted: (next: boolean) => void;
  onLike: () => void;
  onSave: () => void;
  onComment: () => void;
  onZoomed?: (zoomed: boolean) => void;
  onDeleted?: () => void;
}) {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [paused, setPaused] = useState(false);
  const [burst, setBurst] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const { jpeg, url, poster, failed } = usePreview(doc, nearby);
  const video = isVideo(doc);
  const pdf = isPdf(doc);
  const image = Boolean(jpeg) || (isImage(doc) && Boolean(url));
  const likes = (doc.use_count || 0) + (liked ? 1 : 0);
  const canZoom = Boolean(url && (image || video));
  const zoomW = natural.w;
  const zoomH = natural.h;

  useEffect(() => {
    if (!url || !image) return;
    const probe = new window.Image();
    probe.onload = () => setNatural({ w: probe.naturalWidth, h: probe.naturalHeight });
    probe.src = url;
  }, [url, image]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    el.muted = muted;
    if (active && !paused) {
      void el.play().catch(() => undefined);
    } else {
      el.pause();
    }
  }, [active, muted, paused, url]);

  useEffect(() => {
    if (!active) {
      setMenuOpen(false);
      onZoomed?.(false);
    }
  }, [active, onZoomed]);

  function burstHeart() {
    setBurst(true);
    window.setTimeout(() => setBurst(false), 700);
  }

  function onSingleTap() {
    if (menuOpen) {
      setMenuOpen(false);
      return;
    }
    if (video) setPaused((value) => !value);
  }

  async function onShare() {
    try {
      await shareDocument(doc.id, doc.title, doc.original_filename);
    } catch (err) {
      if (isShareCancel(err)) return;
      toast.error(err instanceof Error ? err.message : "Could not share");
    }
  }

  async function onDownload() {
    try {
      await downloadDocument(doc.id, doc.original_filename);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed");
    }
  }

  async function confirmDelete() {
    if (deleting) return;
    setDeleting(true);
    try {
      await api(`/documents/${doc.id}`, { method: "DELETE" });
      toast.success("Moved to trash");
      setDeleteOpen(false);
      setMenuOpen(false);
      onDeleted?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete");
    } finally {
      setDeleting(false);
    }
  }

  const meta = [kindLabel(doc), doc.ai_classification, doc.expiry_date ? `expires ${doc.expiry_date}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="relative h-full w-full overflow-hidden bg-black">
      {canZoom ? (
        <ZoomStage
          naturalW={zoomW}
          naturalH={zoomH}
          active={active}
          onZoomed={onZoomed}
          onSingleTap={onSingleTap}
        >
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={url}
              alt={doc.title}
              draggable={false}
              className="block h-full w-full max-w-none object-contain select-none"
            />
          ) : (
            <video
              ref={videoRef}
              src={url}
              poster={poster || undefined}
              className="block h-full w-full max-w-none object-contain"
              loop
              playsInline
              muted={muted}
              onLoadedMetadata={(event) => {
                const el = event.currentTarget;
                setNatural({ w: el.videoWidth, h: el.videoHeight });
              }}
            />
          )}
        </ZoomStage>
      ) : url && pdf && !jpeg ? (
        <iframe title={doc.title} src={url} className="pointer-events-none h-full w-full border-0 bg-neutral-950" />
      ) : url && image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={doc.title} className="h-full w-full object-contain" />
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-white">
          <span className="flex size-20 items-center justify-center rounded-3xl bg-white/10">
            <FileText className="size-9" />
          </span>
          <p className="text-lg font-semibold">{doc.title}</p>
          <p className="text-sm text-white/70">{failed ? "Preview unavailable" : nearby ? "Loading…" : kindLabel(doc)}</p>
        </div>
      )}

      {burst && <Heart className="reel-heart pointer-events-none absolute inset-0 z-20 m-auto size-24 fill-white text-white" />}

      {video && paused && (
        <Play className="pointer-events-none absolute inset-0 z-20 m-auto size-16 fill-white/90 text-white/90" />
      )}

      {menuOpen && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-black/70 via-black/20 to-transparent px-4 pb-6 pt-16">
          <p className="truncate pr-14 text-[17px] font-semibold text-white">{doc.title}</p>
          <p className="mt-0.5 truncate pr-14 text-[13px] text-white/80">{meta}</p>
        </div>
      )}

      <div className="pointer-events-none absolute inset-0 z-30">
        {menuOpen && (
          <div className="pointer-events-auto absolute right-3 bottom-16 flex flex-col items-center gap-4">
            {video && (
              <Action label={muted ? "Muted" : "Sound"} onClick={() => onMuted(!muted)}>
                {muted ? <VolumeX className="size-6" strokeWidth={2.25} /> : <Volume2 className="size-6" strokeWidth={2.25} />}
              </Action>
            )}
            <Action
              label={likes > 0 ? String(likes) : "Like"}
              active={liked}
              onClick={() => {
                onLike();
                burstHeart();
              }}
            >
              <Heart className={cn("size-7", liked && "fill-rose-400")} strokeWidth={2.25} />
            </Action>
            <Action label="Ask" onClick={onComment}>
              <MessageCircle className="size-7" strokeWidth={2.25} />
            </Action>
            <Action label="Share" onClick={() => void onShare()}>
              <Share2 className="size-7" strokeWidth={2.25} />
            </Action>
            <Action label={saved ? "Saved" : "Save"} active={saved} onClick={onSave}>
              <Bookmark className={cn("size-7", saved && "fill-white")} strokeWidth={2.25} />
            </Action>
            <Action
              label="Move"
              onClick={() => {
                setMoveOpen(true);
                setMenuOpen(false);
              }}
            >
              <FolderInput className="size-7" strokeWidth={2.25} />
            </Action>
            <Action label="Open" onClick={() => router.push(`/documents/${doc.id}`)}>
              <FileText className="size-7" strokeWidth={2.25} />
            </Action>
            <Action label="Download" onClick={() => void onDownload()}>
              <Download className="size-7" strokeWidth={2.25} />
            </Action>
            <Action
              label="Delete"
              danger
              onClick={() => {
                setDeleteOpen(true);
                setMenuOpen(false);
              }}
            >
              <Trash2 className="size-7" strokeWidth={2.25} />
            </Action>
          </div>
        )}
        <button
          type="button"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? "Hide actions" : "Show actions"}
          onClick={() => setMenuOpen((open) => !open)}
          className="pointer-events-auto absolute right-3 bottom-3 z-40 flex size-11 items-center justify-center rounded-full bg-black/60 text-white shadow-[0_2px_10px_rgba(0,0,0,0.55)]"
        >
          {menuOpen ? <X className="size-5" strokeWidth={2.25} /> : <MoreVertical className="size-5" strokeWidth={2.25} />}
        </button>
      </div>
      <MoveCollectionSheet documentId={doc.id} open={moveOpen} onOpenChange={setMoveOpen} />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {doc.title}?</AlertDialogTitle>
            <AlertDialogDescription>It goes to trash. You can restore it later.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={deleting} onClick={() => void confirmDelete()}>
              {deleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </article>
  );
}

export function DocumentReels() {
  const { user } = useAuth();
  const router = useRouter();
  const scroller = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<ReelDoc[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [active, setActive] = useState(0);
  const [muted, setMuted] = useState(true);
  const [likes, setLikes] = useState<Set<string>>(new Set());
  const [saves, setSaves] = useState<Set<string>>(new Set());
  const [ask, setAsk] = useState<ReelDoc | null>(null);
  const [askText, setAskText] = useState("");
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    setLikes(loadReelLikes(user?.id));
    setSaves(loadReelSaves(user?.id));
    api<{ items: ReelDoc[] }>("/documents?limit=200")
      .then((page) => setItems(page.items || []))
      .catch((err) => toast.error(err instanceof Error ? err.message : "Could not load reels"));
  }, [user?.id]);

  const feed = useMemo(() => {
    if (filter === "liked") return items.filter((doc) => likes.has(doc.id));
    if (filter === "saved") return items.filter((doc) => saves.has(doc.id));
    return items;
  }, [filter, items, likes, saves]);

  const looping = feed.length > 1;
  const primed = useRef(false);
  const wrapping = useRef(false);
  const slides = useMemo(() => {
    if (!looping) return feed.map((doc, real) => ({ doc, real, key: doc.id, loop: real }));
    return [
      { doc: feed[feed.length - 1], real: feed.length - 1, key: `${feed[feed.length - 1].id}-head`, loop: 0 },
      ...feed.map((doc, real) => ({ doc, real, key: doc.id, loop: real + 1 })),
      { doc: feed[0], real: 0, key: `${feed[0].id}-tail`, loop: feed.length + 1 },
    ];
  }, [feed, looping]);

  useEffect(() => {
    if (!feed.length) return;
    const nearbyDocs = [];
    for (let offset = -1; offset <= 4; offset += 1) {
      nearbyDocs.push(feed[(active + offset + feed.length) % feed.length]);
    }
    prefetchReelDocs(nearbyDocs);
  }, [active, feed]);

  function jumpTo(loopIndex: number, smooth = false) {
    const root = scroller.current;
    if (!root) return;
    const top = loopIndex * (root.clientHeight || 1);
    if (smooth) {
      root.scrollTo({ top, behavior: "smooth" });
      return;
    }
    wrapping.current = true;
    const snap = root.style.scrollSnapType;
    root.style.scrollSnapType = "none";
    root.scrollTop = top;
    root.style.scrollSnapType = snap;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        wrapping.current = false;
      });
    });
  }

  useEffect(() => {
    primed.current = false;
    setActive(0);
    setZoomed(false);
    jumpTo(looping ? 1 : 0);
    const timer = window.setTimeout(() => {
      primed.current = true;
    }, 80);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, feed.length, looping]);

  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    let ticking = false;
    let settle: number | null = null;

    function pageOffset() {
      const box = scroller.current;
      if (!box) return 0;
      return box.scrollTop / (box.clientHeight || 1);
    }

    function syncActive() {
      ticking = false;
      if (!primed.current || wrapping.current) return;
      const n = feed.length;
      const offset = pageOffset();
      const i = Math.round(offset);
      if (!looping) {
        setActive(Math.max(0, Math.min(n - 1, i)));
        return;
      }
      if (i <= 0) setActive(n - 1);
      else if (i >= n + 1) setActive(0);
      else setActive(i - 1);
    }

    function wrapIfClone() {
      if (!primed.current || wrapping.current || !looping) return;
      const n = feed.length;
      const offset = pageOffset();
      if (offset <= 0.02) {
        jumpTo(n);
        setActive(n - 1);
      } else if (offset >= n + 0.98) {
        jumpTo(1);
        setActive(0);
      }
    }

    function onScroll() {
      if (wrapping.current) return;
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(syncActive);
      }
      if (settle) window.clearTimeout(settle);
      settle = window.setTimeout(wrapIfClone, 80);
    }

    function onScrollEnd() {
      if (settle) window.clearTimeout(settle);
      wrapIfClone();
    }

    el.addEventListener("scroll", onScroll, { passive: true });
    el.addEventListener("scrollend", onScrollEnd);
    return () => {
      el.removeEventListener("scroll", onScroll);
      el.removeEventListener("scrollend", onScrollEnd);
      if (settle) window.clearTimeout(settle);
    };
  }, [feed.length, looping]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      if (!feed.length) return;
      const delta = event.key === "ArrowDown" ? 1 : -1;
      const next = (active + delta + feed.length) % feed.length;
      const loops = looping && ((active === 0 && next === feed.length - 1) || (active === feed.length - 1 && next === 0));
      jumpTo(looping ? next + 1 : next, !loops);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, feed.length, looping]);

  function sendAsk() {
    if (!ask) return;
    const q = askText.trim() || `What can you tell me about ${ask.title}?`;
    setAsk(null);
    setAskText("");
    router.push(`/ai?q=${encodeURIComponent(q)}&doc=${ask.id}`);
  }

  return (
    <div className="relative h-[calc(100dvh-4.75rem)] w-full bg-black text-white md:h-dvh">
      <div className="relative h-full w-full">
      <header className="absolute inset-x-0 top-0 z-30 flex items-center justify-between bg-gradient-to-b from-black/55 to-transparent px-3 pb-8 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <div className="flex items-center gap-3">
          <p className="text-lg font-semibold">Reels</p>
          {(["all", "liked", "saved"] as Filter[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setFilter(item)}
              className={cn(
                "text-sm capitalize",
                filter === item ? "font-semibold text-white" : "text-white/70",
              )}
            >
              {item === "all" ? "All" : item === "liked" ? "Liked" : "Saved"}
            </button>
          ))}
        </div>
        <Link
          href="/documents/upload"
          aria-label="Add a file"
          className="flex size-10 items-center justify-center rounded-full text-white"
        >
          <Camera className="size-5" />
        </Link>
      </header>

      {feed.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center px-8 text-center">
          <p className="text-lg font-semibold">{filter === "all" ? "No files yet" : `No ${filter} files`}</p>
          <p className="mt-1 text-sm text-white/70">
            {filter === "all"
              ? "Save a document and it will show up here as a reel you can swipe."
              : "Like or save a reel to find it in this tab."}
          </p>
          <Link href="/documents/upload" className="mt-5 rounded-full bg-white px-4 py-2 text-sm font-medium text-black">
            Add a file
          </Link>
        </div>
      ) : (
        <div ref={scroller} className={cn("reel-feed h-full", zoomed ? "overflow-hidden" : "overflow-y-auto")}>
          {slides.map((slide) => (
            <div
              key={slide.key}
              data-loop={slide.loop}
              className="reel-item"
            >
              <ReelSlide
                doc={slide.doc}
                active={slide.real === active}
                nearby={circularNear(slide.real, active, feed.length)}
                liked={likes.has(slide.doc.id)}
                saved={saves.has(slide.doc.id)}
                muted={muted}
                onMuted={setMuted}
                onZoomed={setZoomed}
                onLike={() => setLikes(toggleReelLike(slide.doc.id, user?.id))}
                onSave={() => setSaves(toggleReelSave(slide.doc.id, user?.id))}
                onComment={() => {
                  setAsk(slide.doc);
                  setAskText(`What can you tell me about ${slide.doc.title}?`);
                }}
                onDeleted={() => setItems((current) => current.filter((item) => item.id !== slide.doc.id))}
              />
            </div>
          ))}
        </div>
      )}

      {feed.length > 0 && (
        <p className="pointer-events-none absolute top-16 left-1/2 z-30 -translate-x-1/2 text-[11px] text-white/70 md:top-14">
          {active + 1} / {feed.length}
        </p>
      )}

      <Sheet open={Boolean(ask)} onOpenChange={(open) => !open && setAsk(null)}>
        <SheetContent side="bottom" className="rounded-t-3xl pb-8">
          <SheetHeader>
            <SheetTitle>Ask this file</SheetTitle>
          </SheetHeader>
          <p className="px-1 text-sm text-muted-foreground">{ask?.title}</p>
          <form
            className="flex gap-2 px-4 pb-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendAsk();
            }}
          >
            <Input
              value={askText}
              onChange={(e) => setAskText(e.target.value)}
              placeholder="Ask a question…"
            />
            <button type="submit" className="rounded-full bg-primary px-4 text-sm text-primary-foreground">
              Send
            </button>
          </form>
        </SheetContent>
      </Sheet>
      </div>
    </div>
  );
}
