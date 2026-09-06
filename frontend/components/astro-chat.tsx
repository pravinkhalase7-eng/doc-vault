"use client";

import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  MoreVertical,
  SendHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { newId } from "@/lib/id";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type AstroChatResponse = {
  conversation_id: string;
  message_id: string;
  answer: string;
  external_ai: boolean;
  model: string | null;
  astrology_profile?: {
    name?: string;
    date_of_birth?: string | null;
    birth_time?: string | null;
    birth_place?: string | null;
    has_birth_date?: boolean;
    has_birth_time?: boolean;
    has_birth_place?: boolean;
    chart_engine_available?: boolean;
  };
};

type ThreadItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: string;
  sending?: boolean;
};

const SUGGESTIONS = [
  "What themes may shape my year ahead?",
  "How should I think about career timing?",
  "What does Vedic astrology say about relationships carefully?",
  "Any gentle remedies worth considering?",
];

function dayKey(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function formatDayLabel(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (dayKey(iso) === dayKey(today.toISOString())) return "Today";
  if (dayKey(iso) === dayKey(yesterday.toISOString())) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function formatTime(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function DayChip({ iso }: { iso?: string }) {
  return (
    <div className="my-3 flex justify-center">
      <span className="rounded-full bg-muted/80 px-3 py-0.5 text-[11px] text-muted-foreground">
        {formatDayLabel(iso)}
      </span>
    </div>
  );
}

function renderContent(text: string) {
  const lines = text.split("\n");
  return lines.map((line, index) => {
    const match = line.replace(/\*\*/g, "").match(/^(Short Answer|Astrological Indicators|Interpretation|Guidance|Timing):?\s*$/i);
    if (match) {
      return (
        <p key={index} className="mt-2 first:mt-0 text-[12px] font-semibold uppercase tracking-wide text-[var(--mint)]">
          {match[1]}
        </p>
      );
    }
    if (!line.trim()) return <br key={index} />;
    const html = line
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");
    return (
      <p
        key={index}
        className="text-[14.5px] leading-relaxed"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  });
}

export function AstroChat() {
  const router = useRouter();
  const { user, load } = useAuth();
  const prefs = user?.preferences;
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [thread, setThread] = useState<ThreadItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [birthName, setBirthName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [birthTime, setBirthTime] = useState("");
  const [birthPlace, setBirthPlace] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bootstrapped = useRef(false);
  const canSend = Boolean(message.trim()) && !busy;

  const hasDob = Boolean(prefs?.birth_date);
  const dismissed = Boolean(prefs?.astro_onboarding_dismissed);
  const cloud = Boolean(prefs?.external_ai_enabled && prefs?.ai_privacy_mode !== "PRIVATE");

  useEffect(() => {
    setBirthName(prefs?.birth_name || user?.full_name || "");
    setBirthDate(prefs?.birth_date || "");
    setBirthTime(prefs?.birth_time || "");
    setBirthPlace(prefs?.birth_place || "");
    if (!hasDob && !dismissed) setShowProfileForm(true);
  }, [prefs?.birth_name, prefs?.birth_date, prefs?.birth_time, prefs?.birth_place, prefs?.astro_onboarding_dismissed, user?.full_name, hasDob, dismissed]);

  function scrollToLatest() {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  useLayoutEffect(() => {
    const id = window.requestAnimationFrame(() => {
      scrollToLatest();
      window.requestAnimationFrame(scrollToLatest);
    });
    return () => window.cancelAnimationFrame(id);
  }, [thread, busy, showProfileForm]);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    (async () => {
      try {
        const convos = await api<Array<{ id: string; channel?: string }>>("/ai/conversations?channel=astro");
        const latest = convos[0];
        if (!latest) return;
        const detail = await api<{
          id: string;
          messages: Array<{ id: string; role: string; content: string; created_at?: string }>;
        }>(`/ai/conversations/${latest.id}`);
        setConversationId(detail.id);
        setThread(
          (detail.messages || [])
            .filter((item) => item.role === "user" || item.role === "assistant")
            .map((item) => ({
              id: item.id,
              role: item.role as "user" | "assistant",
              content: item.content,
              at: item.created_at || new Date().toISOString(),
            })),
        );
      } catch {
        /* fresh chat */
      }
    })();
  }, []);

  async function saveProfile(dismissOnly = false) {
    setSavingProfile(true);
    try {
      if (dismissOnly) {
        await api("/users/me/preferences", {
          method: "PATCH",
          body: JSON.stringify({ astro_onboarding_dismissed: true }),
        });
      } else {
        if (!birthDate.trim()) {
          toast.error("Date of birth helps personalize answers");
          setSavingProfile(false);
          return;
        }
        await api("/users/me/preferences", {
          method: "PATCH",
          body: JSON.stringify({
            birth_name: birthName.trim() || null,
            birth_date: birthDate.trim(),
            birth_time: birthTime.trim() || null,
            birth_place: birthPlace.trim() || null,
            astro_onboarding_dismissed: true,
          }),
        });
        toast.success("Birth details saved");
      }
      await load();
      setShowProfileForm(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save birth details");
    } finally {
      setSavingProfile(false);
    }
  }

  async function send(text = message) {
    const bodyText = text.trim();
    if (!bodyText || busy) return;
    setBusy(true);
    setMessage("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    const userItem: ThreadItem = {
      id: newId(),
      role: "user",
      content: bodyText,
      at: new Date().toISOString(),
      sending: true,
    };
    setThread((t) => [...t, userItem]);
    try {
      const chat = await api<AstroChatResponse>("/ai/astro/chat", {
        method: "POST",
        body: JSON.stringify({
          message: bodyText,
          conversation_id: conversationId,
          language: prefs?.language || "en",
        }),
      });
      setConversationId(chat.conversation_id);
      setThread((t) => [
        ...t.map((item) => (item.id === userItem.id ? { ...item, sending: false } : item)),
        {
          id: chat.message_id,
          role: "assistant",
          content: chat.answer,
          at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setThread((t) => t.filter((item) => item.id !== userItem.id));
      setMessage(bodyText);
      toast.error(err instanceof Error ? err.message : "Astro request failed");
    } finally {
      setBusy(false);
    }
  }

  async function newChat() {
    setConversationId(null);
    setThread([]);
    setMessage("");
  }

  async function clearChat() {
    if (conversationId) {
      try {
        await api(`/ai/conversations/${conversationId}`, { method: "DELETE" });
      } catch {
        /* ignore */
      }
    }
    await newChat();
  }

  const profileHint = useMemo(() => {
    if (!hasDob) return "Add birth details for personalized guidance";
    if (!prefs?.birth_time) return "Birth time missing · Lagna/houses limited";
    if (prefs?.birth_place) return `${prefs.birth_place} · chart engine not connected yet`;
    return "Chart engine not connected yet · no invented positions";
  }, [hasDob, prefs?.birth_time, prefs?.birth_place]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="z-20 flex items-center gap-3 border-b bg-card px-3 py-2.5">
        <Avatar size="lg" className="bg-[color-mix(in_srgb,var(--mint)_35%,transparent)]">
          <AvatarFallback className="bg-transparent text-[var(--mint-foreground)] dark:text-[var(--mint)]">
            <Sparkles className="size-5" />
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold leading-tight">Astro</p>
          <p className="truncate text-[12px] text-muted-foreground">
            {busy ? "typing…" : cloud ? "Vedic guide · Cloud AI" : "Vedic guide · on device"}
          </p>
        </div>
        <button
          type="button"
          aria-label="Edit birth details"
          onClick={() => setShowProfileForm(true)}
          className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground hover:bg-muted"
        >
          Profile
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger
            className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
            aria-label="Astro menu"
          >
            <MoreVertical className="size-5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-44">
            <DropdownMenuItem onClick={() => void newChat()}>New chat</DropdownMenuItem>
            <DropdownMenuItem onClick={() => void clearChat()}>Clear chat</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setShowProfileForm(true)}>Birth details</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/ai")}>Vault AI</DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/settings")}>Settings</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <div ref={listRef} className="vault-chat-bg relative min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {showProfileForm && (
          <div className="mx-auto mb-4 max-w-md rounded-2xl border bg-card p-4 shadow-sm">
            <div className="mb-3 flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">Birth details</p>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  Saved once for personalized Vedic guidance. Chart positions are never invented.
                </p>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="rounded-full p-1 text-muted-foreground hover:bg-muted"
                onClick={() => void saveProfile(true)}
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="astro-name">Name</Label>
                <Input id="astro-name" value={birthName} onChange={(e) => setBirthName(e.target.value)} placeholder="Birth name" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="astro-dob">Date of birth</Label>
                <Input id="astro-dob" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="astro-time">Birth time (optional)</Label>
                  <Input id="astro-time" type="time" value={birthTime} onChange={(e) => setBirthTime(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="astro-place">Birth place</Label>
                  <Input id="astro-place" value={birthPlace} onChange={(e) => setBirthPlace(e.target.value)} placeholder="City" />
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <Button className="flex-1 rounded-full" disabled={savingProfile} onClick={() => void saveProfile(false)}>
                  Save
                </Button>
                <Button
                  variant="ghost"
                  className="rounded-full"
                  disabled={savingProfile}
                  onClick={() => void saveProfile(true)}
                >
                  Not now
                </Button>
              </div>
            </div>
          </div>
        )}

        {thread.length === 0 && !busy && (
          <div className="mx-auto mt-8 max-w-md text-center">
            <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-card shadow-sm">
              <Sparkles className="size-7 text-[var(--mint)]" />
            </div>
            <p className="text-lg font-semibold">Vedic astrology Q&amp;A</p>
            <p className="mt-1 text-sm text-muted-foreground">{profileHint}</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => void send(item)}
                  className="rounded-full border bg-card/90 px-3 py-1.5 text-left text-[13px] shadow-sm"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mx-auto flex max-w-2xl flex-col">
          {thread.map((item, index) => {
            const prev = thread[index - 1];
            const showDay = !prev || dayKey(prev.at) !== dayKey(item.at);
            const mine = item.role === "user";
            return (
              <Fragment key={item.id}>
                {showDay ? <DayChip iso={item.at} /> : null}
                <div className={cn("mb-2 flex", mine ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-3.5 py-2.5 shadow-sm",
                      mine
                        ? "rounded-br-md bg-[var(--mint)] text-[var(--mint-foreground)]"
                        : "rounded-bl-md border bg-card",
                    )}
                  >
                    {mine ? (
                      <p className="whitespace-pre-wrap text-[14.5px] leading-relaxed">{item.content}</p>
                    ) : (
                      <div className="space-y-0.5">{renderContent(item.content)}</div>
                    )}
                    <p className={cn("mt-1 text-right text-[10px]", mine ? "opacity-70" : "text-muted-foreground")}>
                      {item.sending ? "…" : formatTime(item.at)}
                    </p>
                  </div>
                </div>
              </Fragment>
            );
          })}
          {busy && (
            <div className="mb-2 flex justify-start">
              <div className="rounded-2xl rounded-bl-md border bg-card px-3.5 py-2.5 text-sm text-muted-foreground shadow-sm">
                Thinking…
              </div>
            </div>
          )}
        </div>
      </div>

      <footer className="z-20 border-t bg-card/95 px-2 py-2 backdrop-blur">
        <form
          className="mx-auto flex max-w-2xl items-end gap-2 px-1"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <div className="flex min-h-11 flex-1 items-end rounded-3xl border bg-background px-3 py-1">
            <textarea
              ref={inputRef}
              rows={1}
              value={message}
              placeholder="Ask about timing, career, relationships…"
              className="max-h-28 min-h-10 w-full resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-muted-foreground"
              onChange={(e) => {
                setMessage(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 112)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
          </div>
          <button
            type="submit"
            aria-label="Send"
            disabled={!canSend}
            className="mb-0.5 flex size-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint)] text-[var(--mint-foreground)] shadow-sm disabled:opacity-40"
          >
            <SendHorizontal className="size-5 shrink-0" />
          </button>
        </form>
        <p className="mx-auto mt-1 max-w-2xl px-2 text-center text-[10px] text-muted-foreground">
          Guidance only · never invents chart data · not medical/financial advice
        </p>
      </footer>
    </div>
  );
}
