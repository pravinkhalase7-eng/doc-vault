"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Mic, SendHorizonal, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { api, apiBlobPost } from "@/lib/api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import {
  getSpeechRecognition,
  playAudioBlob,
  speakText,
  stopSpeaking,
  type SpeechRecognitionLike,
} from "@/lib/speech";

type CoachMode = "english" | "pavi";

type Line = {
  id: string;
  role: "user" | "assistant";
  content: string;
  spoken?: string;
  at: string;
  sending?: boolean;
  external_ai?: boolean;
};

const starters: Record<CoachMode, string[]> = {
  english: [
    "I got to market yesterday",
    "Let's practice a job interview",
    "Make this more polite: Give me the file now",
  ],
  pavi: [
    "Draft a polite WhatsApp message",
    "Help me plan my evening",
    "Explain GST in simple words",
  ],
};

export function CoachChat({
  mode,
  title,
  hint,
  initials,
}: {
  mode: CoachMode;
  title: string;
  hint: string;
  initials: string;
}) {
  const router = useRouter();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [thread, setThread] = useState<Line[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechMode, setSpeechMode] = useState(mode === "english");
  const [keyboardInset, setKeyboardInset] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const voiceRef = useRef("");
  const sentByVoiceRef = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread, busy]);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const sync = () => {
      const hidden = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      setKeyboardInset(hidden > 40 ? hidden : 0);
    };
    viewport.addEventListener("resize", sync);
    viewport.addEventListener("scroll", sync);
    sync();
    return () => {
      viewport.removeEventListener("resize", sync);
      viewport.removeEventListener("scroll", sync);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const convos = await api<Array<{ id: string }>>(`/ai/conversations?kind=${mode}`);
        const latest = convos[0];
        if (!latest || cancelled) return;
        const detail = await api<{
          id: string;
          messages: Array<{
            id: string;
            role: string;
            content: string;
            external_ai?: boolean;
            created_at?: string;
          }>;
        }>(`/ai/conversations/${latest.id}`);
        if (cancelled) return;
        setConversationId(detail.id);
        setThread(
          (detail.messages || [])
            .filter((item) => item.role === "user" || item.role === "assistant")
            .map((item) => ({
              id: item.id,
              role: item.role as "user" | "assistant",
              content: item.content,
              at: item.created_at || new Date().toISOString(),
              external_ai: Boolean(item.external_ai),
            })),
        );
      } catch {
        /* start empty */
      }
    })();
    return () => {
      cancelled = true;
      recRef.current?.abort();
      stopSpeaking();
    };
  }, [mode]);

  async function speakCoach(text: string) {
    const cleaned = text.replace(/\n+/g, " ").replace(/\s+/g, " ").trim();
    if (!cleaned) return;
    try {
      const blob = await apiBlobPost("/ai/speak", { text: cleaned.slice(0, 1800), language: "en-IN" });
      await playAudioBlob(blob);
    } catch {
      speakText(cleaned, "en-IN");
    }
  }

  async function send(text: string, fromVoice = false) {
    const message = text.trim();
    if (!message || busy) return;
    setDraft("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    sentByVoiceRef.current = fromVoice;
    const tempId = `tmp-${Date.now()}`;
    setThread((rows) => [
      ...rows,
      { id: tempId, role: "user", content: message, at: new Date().toISOString(), sending: true },
    ]);
    setBusy(true);
    try {
      const result = await api<{
        conversation_id: string;
        message_id: string;
        answer: string;
        spoken?: string;
        external_ai: boolean;
      }>("/ai/coach", {
        method: "POST",
        body: JSON.stringify({
          mode,
          message,
          conversation_id: conversationId,
          speech_mode: speechMode,
        }),
      });
      setConversationId(result.conversation_id);
      const spoken = result.spoken || result.answer;
      setThread((rows) => [
        ...rows.map((row) => (row.id === tempId ? { ...row, sending: false } : row)),
        {
          id: result.message_id,
          role: "assistant",
          content: result.answer,
          spoken,
          at: new Date().toISOString(),
          external_ai: result.external_ai,
        },
      ]);
      if (speechMode || fromVoice) void speakCoach(spoken);
    } catch (error) {
      setThread((rows) => rows.filter((row) => row.id !== tempId));
      toast.error(error instanceof Error ? error.message : "Could not reply");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function speakLast() {
    const last = [...thread].reverse().find((row) => row.role === "assistant");
    if (!last) return;
    void speakCoach(last.spoken || last.content);
  }

  function toggleMic() {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      toast.error("Voice input is not available in this browser");
      return;
    }
    setSpeechMode(true);
    const rec = new Ctor();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    voiceRef.current = "";
    rec.onresult = (event) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript;
      }
      voiceRef.current = text.trim();
      setDraft(voiceRef.current);
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed") toast.error("Allow microphone access to practice speaking");
      else if (event.error !== "aborted") toast.error("Could not hear that");
      setListening(false);
    };
    rec.onend = () => {
      recRef.current = null;
      setListening(false);
      const spoken = voiceRef.current.trim();
      if (spoken) void send(spoken, true);
    };
    recRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      toast.error("Could not start the microphone");
    }
  }

  const empty = thread.length === 0 && !busy;

  return (
    <div
      className="flex h-full min-h-0 flex-col bg-background"
      style={keyboardInset ? { paddingBottom: keyboardInset } : undefined}
    >
      <header className="z-20 flex items-center gap-3 border-b bg-card px-3 py-2.5">
        <button
          type="button"
          aria-label="Back"
          onClick={() => router.push("/home")}
          className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
        >
          <ArrowLeft className="size-5" />
        </button>
        <Avatar size="lg" className="bg-[color-mix(in_srgb,var(--mint)_35%,transparent)]">
          <AvatarFallback className="bg-transparent text-sm font-semibold text-[var(--mint-foreground)] dark:text-[var(--mint)]">
            {initials}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold leading-tight">{title}</p>
          <p className="truncate text-[12px] text-muted-foreground">
            {busy ? "typing…" : listening ? "listening…" : speechMode ? "Speech on · tap mic to talk" : hint}
          </p>
        </div>
        {mode === "english" ? (
          <>
            <button
              type="button"
              aria-pressed={speechMode}
              aria-label={speechMode ? "Turn speech mode off" : "Turn speech mode on"}
              onClick={() => {
                const next = !speechMode;
                setSpeechMode(next);
                if (!next) stopSpeaking();
              }}
              className={cn(
                "rounded-full px-3 py-1.5 text-[12px] font-medium",
                speechMode ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
              )}
            >
              Speech
            </button>
            <button
              type="button"
              aria-label="Hear the last correction"
              onClick={speakLast}
              className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
            >
              <Volume2 className="size-5" />
            </button>
          </>
        ) : null}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        {empty ? (
          <div className="mx-auto max-w-md space-y-4 pt-6">
            <p className="text-sm text-muted-foreground">{hint}</p>
            <div className="flex flex-col gap-2">
              {starters[mode].map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void send(prompt)}
                  className="rounded-2xl border bg-card px-4 py-3 text-left text-sm hover:bg-muted/60"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          thread.map((item) => {
            const mine = item.role === "user";
            return (
              <div key={item.id} className={cn("mt-3 flex w-full", mine ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "inline-flex w-fit max-w-[78%] flex-col rounded-[1.5rem] px-4 py-2.5 text-left text-[16px] leading-relaxed",
                    mine
                      ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                      : "bg-[#eef0f3] text-foreground dark:bg-[#232326]",
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{item.content}</p>
                  {!mine ? (
                    <span className="mt-1 text-[10px] text-muted-foreground/80">
                      {item.external_ai ? "Gemini" : "Coach"}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="border-t bg-card px-3 pt-3"
        style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
      >
        <div className="flex items-end gap-2">
          <button
            type="button"
            aria-label={listening ? "Stop listening" : "Speak"}
            onClick={toggleMic}
            className={cn(
              "flex size-12 shrink-0 items-center justify-center rounded-full",
              listening ? "bg-destructive text-white" : "bg-muted text-foreground",
            )}
          >
            <Mic className="size-5" />
          </button>
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            enterKeyHint="send"
            autoCapitalize="sentences"
            autoCorrect="on"
            onChange={(event) => {
              setDraft(event.target.value);
              event.target.style.height = "auto";
              event.target.style.height = `${Math.min(event.target.scrollHeight, 128)}px`;
            }}
            placeholder={mode === "english" ? "Type or speak a sentence…" : "Message Pavi…"}
            className="max-h-32 min-h-12 flex-1 resize-none rounded-2xl border bg-background px-3 py-3 text-[16px] outline-none"
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                void send(draft);
              }
            }}
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            aria-label="Send"
            className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
          >
            <SendHorizonal className="size-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
