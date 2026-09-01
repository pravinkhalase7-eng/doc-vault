"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Camera,
  Check,
  CheckCheck,
  ChevronRight,
  Download,
  FileText,
  Folder,
  Folders,
  FolderPlus,
  Image as ImageIcon,
  MessageSquare,
  Mic,
  MoreVertical,
  Plus,
  Search,
  SendHorizontal,
  Settings,
  Share2,
  Shield,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiBlob, apiForm } from "@/lib/api";
import { downloadDocument, isShareCancel, shareDocument } from "@/lib/files";
import { useAuth } from "@/lib/auth";
import {
  getSpeechRecognition,
  speakText,
  speechLang,
  speechSupported,
  stopSpeaking,
  type SpeechRecognitionLike,
} from "@/lib/speech";
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
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type Evidence = {
  document_id: string;
  document_title: string;
  page_number: number | null;
  text_reference: string;
  original_filename?: string;
  mime_type?: string;
  size_bytes?: number;
};

type Attachment = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  size_bytes?: number;
  previewUrl?: string;
  local?: boolean;
};

type CollectionNode = {
  id: string;
  name: string;
  document_count?: number;
  documents?: Array<{
    id: string;
    title: string;
    original_filename: string;
    mime_type?: string;
    size_bytes?: number;
  }>;
  children?: CollectionNode[];
};

type ChatProposal = {
  id: string;
  kind: string;
  status: string;
  summary?: string;
};

type Chat = {
  conversation_id: string;
  message_id: string;
  answer: string;
  evidence: Evidence[];
  data_access: Record<string, unknown>;
  external_ai: boolean;
  model: string | null;
  collection_tree?: CollectionNode[];
  proposal?: ChatProposal | null;
};

type ThreadItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: string;
  attachments?: Attachment[];
  chat?: Chat;
  sending?: boolean;
};

const PreviewCtx = createContext<(att: Attachment) => void>(() => {});

type VaultDoc = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  size_bytes?: number;
};

type VaultCollection = {
  id: string;
  name: string;
  parent_id?: string | null;
  document_ids: string[];
};

type UploadSource = "document" | "camera" | "gallery";
type ChatMode = "chat" | "voice";

type Pending =
  | { kind: "file"; localId: string; file: File; previewUrl?: string }
  | { kind: "vault"; localId: string; doc: VaultDoc };

const suggestions = [
  "Show me all collections",
  "When does my car insurance expire?",
  "Which documents are expiring this month?",
  "Do I have all documents required for passport renewal?",
  "Show documents related to my house.",
];

function isImageMime(mime?: string, name?: string) {
  if (mime?.startsWith("image/")) return true;
  return /\.(png|jpe?g|gif|webp|heic|bmp)$/i.test(name || "");
}

function formatBytes(n?: number) {
  if (!n) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(iso?: string) {
  const date = iso ? new Date(iso) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function extLabel(name?: string, mime?: string) {
  const fromName = name?.split(".").pop()?.toUpperCase();
  if (fromName && fromName.length <= 5) return fromName;
  return mime?.split("/")[1]?.toUpperCase() || "FILE";
}

function fileStem(name: string) {
  return name.replace(/\.[^.]+$/, "") || name;
}

function proposalFromAccess(access: Record<string, unknown> | undefined): ChatProposal | null {
  const raw = access?.proposal;
  if (!raw || typeof raw !== "object") return null;
  const item = raw as ChatProposal;
  if (!item.id || !item.kind) return null;
  return item;
}

function isConfirmableProposal(kind?: string) {
  return kind === "delete_collection_files" || kind === "delete_collection" || kind === "delete_document";
}

function isClearCommand(text: string) {
  const value = text.trim().toLowerCase().replace(/[.?!]+$/, "");
  return (
    value === "clear" ||
    value === "clear chat" ||
    value === "clear history" ||
    value === "clear the chat" ||
    value === "clear chat history"
  );
}

export function VaultChat() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const [message, setMessage] = useState(params.get("q") || "");
  const [busy, setBusy] = useState(false);
  const [thread, setThread] = useState<ThreadItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [trayOpen, setTrayOpen] = useState(false);
  const [vaultOpen, setVaultOpen] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const [vaultDocs, setVaultDocs] = useState<VaultDoc[]>([]);
  const [vaultQuery, setVaultQuery] = useState("");
  const [vaultPicked, setVaultPicked] = useState<Set<string>>(new Set());
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [collections, setCollections] = useState<VaultCollection[]>([]);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [creatingCollection, setCreatingCollection] = useState(false);
  const [namingOpen, setNamingOpen] = useState(false);
  const [namingFiles, setNamingFiles] = useState<File[]>([]);
  const [namingTitles, setNamingTitles] = useState<string[]>([]);
  const [namingCollection, setNamingCollection] = useState<VaultCollection | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const bootstrapped = useRef(false);
  const skipHistory = useRef(false);
  const uploadSourceRef = useRef<UploadSource>("document");
  const chosenCollectionRef = useRef<VaultCollection | null>(null);
  const stashedFilesRef = useRef<File[]>([]);
  const [preview, setPreview] = useState<Attachment | null>(null);
  const [mode, setMode] = useState<ChatMode>("chat");
  const [listening, setListening] = useState(false);
  const [voiceText, setVoiceText] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const voiceTextRef = useRef("");
  const sendRef = useRef<(text?: string) => void>(() => {});
  const spokenRef = useRef<string | null>(null);
  const modeRef = useRef<ChatMode>("chat");

  const cloud = Boolean(user?.preferences?.external_ai_enabled);
  const canSend = Boolean(message.trim() || pending.length) && !busy;
  modeRef.current = mode;

  const vaultFiltered = useMemo(() => {
    const q = vaultQuery.trim().toLowerCase();
    if (!q) return vaultDocs;
    return vaultDocs.filter(
      (doc) =>
        doc.title.toLowerCase().includes(q) ||
        doc.original_filename.toLowerCase().includes(q),
    );
  }, [vaultDocs, vaultQuery]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [thread, busy, pending]);

  useEffect(() => {
    sendRef.current = (text) => void send(text);
  });

  useEffect(() => {
    if (mode !== "voice" || busy) return;
    const last = [...thread].reverse().find((item) => item.role === "assistant" && item.content);
    if (!last || last.id === spokenRef.current) return;
    spokenRef.current = last.id;
    speakText(last.content, speechLang(user?.preferences?.language));
  }, [thread, busy, mode, user]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      stopSpeaking();
    };
  }, []);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    (async () => {
      let latestId: string | null = null;
      try {
        const convos = await api<Array<{ id: string }>>("/ai/conversations");
        const latest = convos[0];
        if (latest) {
          const detail = await api<{
            id: string;
            messages: Array<{
              id: string;
              role: string;
              content: string;
              evidence?: Evidence[];
              data_access?: Record<string, unknown>;
              external_ai?: boolean;
              model?: string | null;
              created_at?: string;
            }>;
          }>(`/ai/conversations/${latest.id}`);
          latestId = detail.id;
          const loaded = (detail.messages || []).filter(
            (item) => item.role === "user" || item.role === "assistant",
          );
          if (!skipHistory.current) {
            setConversationId(detail.id);
            setThread(
              loaded.map((item) => {
                const access = item.data_access || {};
                const attachments = Array.isArray(access.attachments)
                  ? (access.attachments as Attachment[])
                  : [];
                  const collectionTree = Array.isArray(access.collection_tree)
                    ? (access.collection_tree as CollectionNode[])
                    : [];
                const proposal = proposalFromAccess(access);
                return {
                  id: item.id,
                  role: item.role as "user" | "assistant",
                  content: item.content,
                  at: item.created_at || new Date().toISOString(),
                  attachments,
                  chat:
                    item.role === "assistant"
                      ? {
                          conversation_id: detail.id,
                          message_id: item.id,
                          answer: item.content,
                          evidence: item.evidence || [],
                          data_access: access,
                          external_ai: Boolean(item.external_ai),
                          model: item.model || null,
                          collection_tree: collectionTree,
                          proposal,
                        }
                      : undefined,
                };
              }),
            );
          }
          const q = params.get("q");
          const extraDoc = params.get("doc");
          const extraIds = extraDoc ? [extraDoc] : [];
          const lastUser = [...loaded].reverse().find((item) => item.role === "user");
          if (q && lastUser?.content !== q && !skipHistory.current) await send(q, latestId, extraIds);
        } else {
          const q = params.get("q");
          const extraDoc = params.get("doc");
          if (q && !skipHistory.current) await send(q, latestId, extraDoc ? [extraDoc] : []);
        }
      } catch {
        const q = params.get("q");
        const extraDoc = params.get("doc");
        if (q && !skipHistory.current) await send(q, latestId, extraDoc ? [extraDoc] : []);
      }
      await refreshPending();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function beginUpload(source: UploadSource, files: File[] = []) {
    setTrayOpen(false);
    uploadSourceRef.current = source;
    stashedFilesRef.current = files;
    chosenCollectionRef.current = null;
    setNewCollectionName("");
    try {
      setCollections(await api<VaultCollection[]>("/collections"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load collections");
      setCollections([]);
    }
    setCollectionOpen(true);
  }

  function openFilePicker(source: UploadSource) {
    window.setTimeout(() => {
      if (source === "camera") cameraInput.current?.click();
      else if (source === "gallery") galleryInput.current?.click();
      else docInput.current?.click();
    }, 280);
  }

  async function pickCollection(col: VaultCollection) {
    chosenCollectionRef.current = col;
    setCollectionOpen(false);
    const stashed = stashedFilesRef.current;
    stashedFilesRef.current = [];
    if (stashed.length) {
      openNaming(stashed, col);
      return;
    }
    openFilePicker(uploadSourceRef.current);
  }

  function openNaming(files: File[], col: VaultCollection) {
    setNamingFiles(files);
    setNamingTitles(files.map((file) => fileStem(file.name)));
    setNamingCollection(col);
    setNamingOpen(true);
  }

  async function refreshPending() {
    try {
      const rows = await api<Array<{ id: string }>>("/ai/proposals");
      setPendingIds(new Set((rows || []).map((row) => row.id)));
    } catch {
      setPendingIds(new Set());
    }
  }

  async function createAndPickCollection() {
    const name = newCollectionName.trim();
    if (!name) return;
    setCreatingCollection(true);
    try {
      const created = await api<VaultCollection>("/collections", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setCollections((current) => [...current, created]);
      setNewCollectionName("");
      await pickCollection(created);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create collection");
    } finally {
      setCreatingCollection(false);
    }
  }

  async function uploadToCollection(files: File[], col: VaultCollection, titles: string[] = []) {
    if (!files.length) return;
    setBusy(true);
    skipHistory.current = true;
    const savedNames = files.map((file, index) => (titles[index] || "").trim() || fileStem(file.name));
    const savedLabel = savedNames.join(", ");
    const userText = `Saved ${savedLabel} to ${col.name}`;
    const assistantText = `Saved ${savedLabel} to ${col.name}. Ask me about ${savedLabel} whenever you want.`;
    const localAttachments: Attachment[] = files.map((file, index) => {
      const image = file.type.startsWith("image/") || isImageMime(file.type, file.name);
      return {
        id: crypto.randomUUID(),
        title: savedNames[index] || file.name,
        original_filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        previewUrl: image ? URL.createObjectURL(file) : undefined,
        local: true,
      };
    });
    const userItem: ThreadItem = {
      id: crypto.randomUUID(),
      role: "user",
      content: userText,
      at: new Date().toISOString(),
      attachments: localAttachments,
      sending: true,
    };
    flushSync(() => {
      setThread((t) => [...t, userItem]);
    });
    try {
      const uploaded: VaultDoc[] = [];
      for (let index = 0; index < files.length; index += 1) {
        const body = new FormData();
        body.append("files", files[index]);
        const title = savedNames[index];
        if (title) body.append("title", title);
        body.append("collection_id", col.id);
        const result = await apiForm<{ documents: VaultDoc[] }>("/documents/upload", body);
        uploaded.push(...(result.documents || []));
      }
      if (!uploaded.length) throw new Error("Upload did not save any files");
      const uploadedAttachments: Attachment[] = uploaded.map((doc, index) => ({
        id: doc.id,
        title: doc.title,
        original_filename: doc.original_filename,
        mime_type: doc.mime_type,
        size_bytes: doc.size_bytes,
        previewUrl: localAttachments[index]?.previewUrl,
      }));
      const note = await api<{
        conversation_id: string;
        user_message_id: string;
        assistant_message_id: string;
      }>("/ai/notes", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: conversationId,
          user_content: userText,
          assistant_content: assistantText,
          document_ids: uploaded.map((doc) => doc.id),
        }),
      });
      setConversationId(note.conversation_id);
      setThread((t) => [
        ...t.map((item) =>
          item.id === userItem.id
            ? { ...item, id: note.user_message_id, attachments: uploadedAttachments, sending: false }
            : item,
        ),
        {
          id: note.assistant_message_id,
          role: "assistant",
          content: assistantText,
          at: new Date().toISOString(),
        },
      ]);
      toast.success(`Saved to ${col.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setThread((t) => t.filter((item) => item.id !== userItem.id));
    } finally {
      setBusy(false);
      chosenCollectionRef.current = null;
    }
  }

  function onPickedFiles(list: FileList | null) {
    const files = Array.from(list || []);
    const col = chosenCollectionRef.current;
    if (col && files.length) {
      openNaming(files, col);
      return;
    }
    if (files.length) beginUpload(uploadSourceRef.current, files);
  }

  function addDeviceFiles(list: FileList | File[] | null) {
    if (!list) return;
    beginUpload("document", Array.from(list));
  }

  function removePending(localId: string) {
    setPending((current) => {
      const item = current.find((entry) => entry.localId === localId);
      if (item?.kind === "file" && item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      return current.filter((entry) => entry.localId !== localId);
    });
  }

  async function openVault() {
    setTrayOpen(false);
    setVaultOpen(true);
    setVaultQuery("");
    setVaultPicked(new Set());
    try {
      const page = await api<{ items: VaultDoc[] }>("/documents?limit=200");
      setVaultDocs(page.items || []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load vault");
    }
  }

  function confirmVaultPicks() {
    const chosen = vaultDocs.filter((doc) => vaultPicked.has(doc.id));
    setPending((current) => {
      const have = new Set(current.filter((item) => item.kind === "vault").map((item) => item.doc.id));
      return [
        ...current,
        ...chosen
          .filter((doc) => !have.has(doc.id))
          .map((doc) => ({ kind: "vault" as const, localId: crypto.randomUUID(), doc })),
      ];
    });
    setVaultOpen(false);
  }

  async function send(text = message, existingConversation = conversationId, extraDocIds: string[] = []) {
    const caption = text.trim();
    if (isClearCommand(caption) && pending.length === 0 && extraDocIds.length === 0) {
      clearChat();
      setMessage("");
      if (inputRef.current) inputRef.current.style.height = "auto";
      return;
    }
    if (!caption && pending.length === 0 && extraDocIds.length === 0) return;
    setBusy(true);
    setTrayOpen(false);
    setVoiceText("");
    voiceTextRef.current = "";
    const queued = pending;
    const optimistic: Attachment[] = queued.map((item) =>
      item.kind === "file"
        ? {
            id: item.localId,
            title: item.file.name,
            original_filename: item.file.name,
            mime_type: item.file.type,
            size_bytes: item.file.size,
            previewUrl: item.previewUrl,
            local: true,
          }
        : {
            id: item.doc.id,
            title: item.doc.title,
            original_filename: item.doc.original_filename,
            mime_type: item.doc.mime_type,
            size_bytes: item.doc.size_bytes,
          },
    );
    const names = queued
      .map((item) => (item.kind === "file" ? item.file.name : item.doc.title))
      .filter(Boolean)
      .join(", ");
    const bodyText = caption || (names ? `What can you tell me about ${names}?` : "Hello");
    skipHistory.current = true;
    const extraOptimistic: Attachment[] = extraDocIds
      .filter((docId) => !optimistic.some((att) => att.id === docId))
      .map((docId) => ({
        id: docId,
        title: caption || "Attached file",
        original_filename: "Attached file",
      }));
    const userItem: ThreadItem = {
      id: crypto.randomUUID(),
      role: "user",
      content: caption,
      at: new Date().toISOString(),
      attachments: [...optimistic, ...extraOptimistic],
      sending: true,
    };
    flushSync(() => {
      setThread((t) => [...t, userItem]);
      setMessage("");
      setPending([]);
    });
    if (inputRef.current) inputRef.current.style.height = "auto";
    try {
      const uploadedIds: string[] = [];
      const fileItems = queued.filter((item) => item.kind === "file");
      if (fileItems.length) {
        const form = new FormData();
        fileItems.forEach((item) => form.append("files", item.file));
        const result = await apiForm<{ documents: VaultDoc[] }>("/documents/upload", form);
        const uploadedDocs = result.documents || [];
        uploadedIds.push(...uploadedDocs.map((doc) => doc.id));
        const uploadedByLocal = new Map(
          fileItems.map((item, index) => [item.localId, uploadedDocs[index]?.id || item.localId]),
        );
        setThread((t) =>
          t.map((item) =>
            item.id === userItem.id
              ? {
                  ...item,
                  attachments: (item.attachments || []).map((att) => ({
                    ...att,
                    id: uploadedByLocal.get(att.id) || att.id,
                    local: false,
                  })),
                }
              : item,
          ),
        );
      }
      const vaultIds = queued.filter((item) => item.kind === "vault").map((item) => item.doc.id);
      const documentIds = [...vaultIds, ...uploadedIds, ...extraDocIds];
      const chat = await api<Chat>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: bodyText,
          conversation_id: existingConversation,
          document_ids: documentIds,
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
          chat: {
            ...chat,
            collection_tree:
              chat.collection_tree?.length
                ? chat.collection_tree
                : Array.isArray(chat.data_access?.collection_tree)
                  ? (chat.data_access.collection_tree as CollectionNode[])
                  : [],
            proposal: chat.proposal || proposalFromAccess(chat.data_access),
          },
        },
      ]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "AI request blocked");
      setThread((t) => t.filter((item) => item.id !== userItem.id));
      setPending(queued);
      if (caption) {
        if (modeRef.current === "voice") {
          setVoiceText(caption);
          voiceTextRef.current = caption;
        } else {
          setMessage(caption);
        }
      }
    } finally {
      setBusy(false);
      void refreshPending();
      if (modeRef.current === "chat") inputRef.current?.focus({ preventScroll: true });
    }
  }

  async function newChat() {
    setThread([]);
    setConversationId(null);
    setMessage("");
    setPending([]);
  }

  function clearChat() {
    skipHistory.current = true;
    setThread([]);
    setMessage("");
    setPending([]);
    setPreview(null);
    setTrayOpen(false);
    setVoiceText("");
    voiceTextRef.current = "";
    stopListening(false);
    stopSpeaking();
  }

  function stopListening(sendTranscript: boolean) {
    const rec = recognitionRef.current;
    if (!rec) {
      setListening(false);
      if (sendTranscript && voiceTextRef.current) sendRef.current(voiceTextRef.current);
      return;
    }
    rec.onend = () => {
      recognitionRef.current = null;
      setListening(false);
      const text = voiceTextRef.current.trim();
      if (sendTranscript && text) sendRef.current(text);
    };
    try {
      rec.stop();
    } catch {
      recognitionRef.current = null;
      setListening(false);
    }
  }

  function cancelListening() {
    const rec = recognitionRef.current;
    if (rec) {
      rec.onend = null;
      try {
        rec.abort();
      } catch {
        /* already stopped */
      }
    }
    recognitionRef.current = null;
    setListening(false);
    setVoiceText("");
    voiceTextRef.current = "";
  }

  function exitVoice() {
    cancelListening();
    stopSpeaking();
    setMode("chat");
    modeRef.current = "chat";
    window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 50);
  }

  function startListening() {
    if (busy || listening || modeRef.current !== "voice") return;
    const Speech = getSpeechRecognition();
    if (!Speech) {
      toast.error("Voice is not supported in this browser. Try Chrome or Safari.");
      return;
    }
    stopSpeaking();
    setVoiceText("");
    voiceTextRef.current = "";
    const rec = new Speech();
    rec.lang = speechLang(user?.preferences?.language);
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.onresult = (event) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript;
      }
      const next = text.trim();
      voiceTextRef.current = next;
      setVoiceText(next);
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed") toast.error("Allow microphone access to talk to DocVault");
      else if (event.error === "no-speech") toast.error("Didn't catch that. Tap the mic and try again.");
      else if (event.error !== "aborted") toast.error("Could not hear that");
      setListening(false);
      recognitionRef.current = null;
    };
    rec.onend = () => {
      recognitionRef.current = null;
      setListening(false);
      const text = voiceTextRef.current.trim();
      if (text) sendRef.current(text);
    };
    recognitionRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      recognitionRef.current = null;
      toast.error("Could not start the microphone");
    }
  }

  function markExistingRepliesSpoken() {
    const last = [...thread].reverse().find((item) => item.role === "assistant" && item.content);
    if (last) spokenRef.current = last.id;
  }

  function openVoiceTab(listen = true) {
    markExistingRepliesSpoken();
    setMode("voice");
    modeRef.current = "voice";
    setTrayOpen(false);
    if (listen) window.setTimeout(() => startListening(), 200);
  }

  function setChatMode(next: ChatMode) {
    if (next === modeRef.current) return;
    if (next === "chat") {
      cancelListening();
      stopSpeaking();
    } else {
      markExistingRepliesSpoken();
    }
    setMode(next);
    modeRef.current = next;
    if (next === "voice") window.setTimeout(() => startListening(), 200);
  }

  return (
    <PreviewCtx.Provider value={(att) => setPreview(att)}>
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="z-20 flex items-center gap-3 border-b bg-card px-3 py-2.5">
        <Avatar size="lg" className="bg-[color-mix(in_srgb,var(--mint)_35%,transparent)]">
          <AvatarFallback className="bg-transparent text-sm font-semibold text-[var(--mint-foreground)] dark:text-[var(--mint)]">
            DV
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold leading-tight">DocVault</p>
          <p className="truncate text-[12px] text-muted-foreground">
            {cloud ? "Cloud AI · Gemini" : "Private AI · on device"}
          </p>
        </div>
        <button
          type="button"
          aria-label="Search"
          onClick={() => router.push("/search")}
          className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
        >
          <Search className="size-5" />
        </button>
        <button
          type="button"
          aria-label="Settings"
          onClick={() => router.push("/settings")}
          className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
        >
          <Settings className="size-5" />
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger
            className="flex size-10 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
            aria-label="Chat menu"
          >
            <MoreVertical className="size-5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-44">
            <DropdownMenuItem onClick={newChat}>New chat</DropdownMenuItem>
            <DropdownMenuItem onClick={clearChat}>Clear chat</DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/reels")}>Reels</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/privacy")}>
              <Shield className="size-4" />
              Privacy Center
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
      <div className="z-20 grid grid-cols-2 border-b bg-card px-2" role="tablist" aria-label="Ask My Vault">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "chat"}
          onClick={() => setChatMode("chat")}
          className={cn(
            "flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium",
            mode === "chat" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground",
          )}
        >
          <MessageSquare className="size-4" />
          Chat
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "voice"}
          onClick={() => setChatMode("voice")}
          className={cn(
            "flex items-center justify-center gap-1.5 py-2.5 text-sm font-medium",
            mode === "voice" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground",
          )}
        >
          <Mic className="size-4" />
          Voice
        </button>
      </div>

      <div
        ref={listRef}
        className="vault-chat-bg relative min-h-0 flex-1 overflow-y-auto px-3 py-4"
        onClick={() => setTrayOpen(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          addDeviceFiles(e.dataTransfer.files);
        }}
      >
        {thread.length === 0 && !busy && (
          <div className="mx-auto mt-10 max-w-md text-center">
            <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-card shadow-sm">
              <span className="text-2xl">🔒</span>
            </div>
            <p className="text-lg font-semibold">Ask My Vault</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === "voice"
                ? "Tap the mic and say a command, like “delete Passport” or “show me all collections”."
                : "Messages stay in your vault. Tap + to save a file into a collection, then ask about it."}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {suggestions.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => send(item)}
                  className="rounded-full border bg-card/90 px-3 py-1.5 text-left text-[13px] shadow-sm"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mx-auto flex max-w-2xl flex-col gap-1.5">
          {thread.map((item) => (
            <Bubble
              key={item.id}
              item={item}
              pendingIds={pendingIds}
              onReply={(text) => void send(text)}
            />
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm bg-card px-4 py-3 shadow-sm">
                <span className="flex gap-1">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.2s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70 [animation-delay:-0.1s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/70" />
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <footer className="relative z-20 bg-background/95 pb-[calc(4.75rem+env(safe-area-inset-bottom))] pt-1 md:pb-3">
        {mode === "chat" && trayOpen && (
          <div className="mx-auto mb-2 max-w-2xl px-3">
            <div className="grid grid-cols-4 gap-3 rounded-2xl bg-card p-4 shadow-lg ring-1 ring-border">
              <AttachAction
                label="Document"
                className="bg-[#7f66ff]"
                icon={FileText}
                onClick={() => void beginUpload("document")}
              />
              <AttachAction
                label="Camera"
                className="bg-[#ff2e74]"
                icon={Camera}
                onClick={() => void beginUpload("camera")}
              />
              <AttachAction
                label="Gallery"
                className="bg-[#c155f7]"
                icon={ImageIcon}
                onClick={() => void beginUpload("gallery")}
              />
              <AttachAction
                label="Vault"
                className="bg-[var(--mint)] text-[var(--mint-foreground)]"
                icon={Folders}
                onClick={openVault}
              />
            </div>
          </div>
        )}

        {pending.length > 0 && (
          <div className="mx-auto mb-2 flex max-w-2xl gap-2 overflow-x-auto px-3">
            {pending.map((item) => (
              <PendingChip key={item.localId} item={item} onRemove={() => removePending(item.localId)} />
            ))}
          </div>
        )}

        {mode === "chat" ? (
        <form
          className="mx-auto flex max-w-2xl items-end gap-2 px-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <button
            type="button"
            aria-label={trayOpen ? "Close attachments" : "Attach"}
            onClick={() => setTrayOpen((open) => !open)}
            className="mb-0.5 flex size-11 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
          >
            <Plus className={cn("size-7 transition-transform", trayOpen && "rotate-45")} />
          </button>
          <div className="flex min-w-0 flex-1 items-end rounded-[1.6rem] bg-card px-3 py-1.5 shadow-sm ring-1 ring-border">
            <textarea
              ref={inputRef}
              rows={1}
              value={message}
              placeholder="Message"
              className="max-h-28 min-h-10 w-full resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-muted-foreground"
              onChange={(e) => {
                setMessage(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 112)}px`;
              }}
              onPaste={(e) => {
                const files = Array.from(e.clipboardData.files || []);
                if (files.length) {
                  e.preventDefault();
                  addDeviceFiles(files);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            {!message && pending.length === 0 && (
              <button
                type="button"
                aria-label="Camera"
                className="mb-1.5 ml-1 text-muted-foreground"
                onClick={() => void beginUpload("camera")}
              >
                <Camera className="size-5" />
              </button>
            )}
          </div>
          {canSend ? (
            <button
              type="submit"
              aria-label="Send"
              className="mb-0.5 flex size-11 items-center justify-center rounded-full bg-[var(--mint)] text-[var(--mint-foreground)] shadow-sm"
            >
              <SendHorizontal className="size-5" />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Voice"
              onClick={() => openVoiceTab(true)}
              className="mb-0.5 flex size-11 items-center justify-center rounded-full bg-[var(--mint)] text-[var(--mint-foreground)] shadow-sm"
            >
              <Mic className="size-5" />
            </button>
          )}
        </form>
        ) : (
        <div className="mx-auto max-w-2xl px-4 pb-2 pt-1">
          <p className="min-h-10 text-center text-[15px] leading-snug">
            {voiceText || (listening ? "Listening…" : busy ? "Working on that…" : "Tap the mic and speak a command")}
          </p>
          <p className="mt-1 text-center text-[12px] text-muted-foreground">
            {listening
              ? "Tap the mic to send, or Cancel to stop."
              : speechSupported()
                ? "Commands like delete, clear, and show collections work here."
                : "Voice needs Chrome or Safari."}
          </p>
          <div className="mt-3 flex items-center justify-center gap-6">
            <button
              type="button"
              aria-label="Cancel voice"
              onClick={exitVoice}
              className="flex size-12 flex-col items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-muted/80"
            >
              <X className="size-5" />
            </button>
            <button
              type="button"
              aria-label={listening ? "Send voice command" : "Start talking"}
              disabled={busy}
              onClick={() => (listening ? stopListening(true) : startListening())}
              className={cn(
                "flex size-[4.5rem] items-center justify-center rounded-full text-[var(--mint-foreground)] shadow-lg disabled:opacity-40",
                listening ? "bg-[var(--mint)] ring-4 ring-[color-mix(in_srgb,var(--mint)_45%,transparent)]" : "bg-[var(--mint)]",
              )}
            >
              <Mic className={cn("size-8", listening && "animate-pulse")} />
            </button>
            <span className="size-12" />
          </div>
          <button
            type="button"
            onClick={exitVoice}
            className="mx-auto mt-3 block text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            Cancel voice
          </button>
        </div>
        )}
      </footer>

      <input
        ref={docInput}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          onPickedFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={galleryInput}
        type="file"
        accept="image/*,video/*"
        multiple
        className="hidden"
        onChange={(e) => {
          onPickedFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          onPickedFiles(e.target.files);
          e.target.value = "";
        }}
      />

      <Sheet open={vaultOpen} onOpenChange={setVaultOpen}>
        <SheetContent side="bottom" className="h-[min(80dvh,36rem)] rounded-t-3xl">
          <SheetHeader>
            <SheetTitle>Send from vault</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
            <Input
              placeholder="Search files"
              value={vaultQuery}
              onChange={(e) => setVaultQuery(e.target.value)}
            />
            <div className="min-h-0 flex-1 overflow-y-auto">
              {vaultFiltered.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">No files in your vault yet.</p>
              )}
              <div className="grid grid-cols-3 gap-1.5">
                {vaultFiltered.map((doc) => {
                  const selected = vaultPicked.has(doc.id);
                  const image = isImageMime(doc.mime_type, doc.original_filename);
                  return (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() =>
                        setVaultPicked((current) => {
                          const next = new Set(current);
                          if (next.has(doc.id)) next.delete(doc.id);
                          else next.add(doc.id);
                          return next;
                        })
                      }
                      className={cn(
                        "relative aspect-square overflow-hidden rounded-xl bg-muted text-left",
                        selected && "ring-2 ring-primary",
                      )}
                    >
                      {image ? (
                        <AuthThumb id={doc.id} alt={doc.title} className="size-full object-cover" />
                      ) : (
                        <FileTile att={{ id: doc.id, title: doc.title, original_filename: doc.original_filename, mime_type: doc.mime_type, size_bytes: doc.size_bytes }} />
                      )}
                      <span className="absolute inset-x-0 bottom-0 truncate bg-black/55 px-1.5 py-1 text-[10px] text-white">
                        {doc.title}
                      </span>
                      {selected && (
                        <span className="absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                          <Check className="size-3" />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button
              size="xl"
              className="rounded-full"
              disabled={vaultPicked.size === 0}
              onClick={confirmVaultPicks}
            >
              {vaultPicked.size ? `Attach ${vaultPicked.size}` : "Attach"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={collectionOpen}
        onOpenChange={(open) => {
          setCollectionOpen(open);
          if (!open && !chosenCollectionRef.current) stashedFilesRef.current = [];
        }}
      >
        <SheetContent side="bottom" className="h-[min(80dvh,36rem)] rounded-t-3xl">
          <SheetHeader>
            <SheetTitle>Save to which collection?</SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
              {collections.length === 0 && (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No collections yet. Create one below, then pick the file.
                </p>
              )}
              {collections.map((col) => (
                <button
                  key={col.id}
                  type="button"
                  onClick={() => void pickCollection(col)}
                  className="flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-left hover:bg-muted"
                >
                  <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <Folder className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{col.name || "Untitled"}</span>
                    <span className="block text-xs text-muted-foreground">
                      {col.document_ids?.length || 0}{" "}
                      {col.document_ids?.length === 1 ? "file" : "files"}
                    </span>
                  </span>
                </button>
              ))}
            </div>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void createAndPickCollection();
              }}
            >
              <Input
                placeholder="New collection name"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
              />
              <Button
                type="submit"
                className="rounded-full"
                disabled={!newCollectionName.trim() || creatingCollection}
              >
                <FolderPlus className="size-4" />
                Create
              </Button>
            </form>
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={namingOpen}
        onOpenChange={(open) => {
          setNamingOpen(open);
          if (!open) {
            setNamingFiles([]);
            setNamingTitles([]);
            setNamingCollection(null);
            chosenCollectionRef.current = null;
          }
        }}
      >
        <SheetContent side="bottom" className="h-[min(80dvh,36rem)] rounded-t-3xl">
          <SheetHeader>
            <SheetTitle>
              {namingFiles.length === 1 ? "Name this file" : "Name these files"}
            </SheetTitle>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
            <p className="text-sm text-muted-foreground">
              This name is saved with the file so you can later say “delete {namingTitles[0] || "Passport"}”.
              {namingCollection?.name ? ` Saving to ${namingCollection.name}.` : ""}
            </p>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
              {namingFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="space-y-1.5">
                  <Label htmlFor={`file-name-${index}`}>{file.name}</Label>
                  <Input
                    id={`file-name-${index}`}
                    value={namingTitles[index] || ""}
                    placeholder="File name"
                    onChange={(e) =>
                      setNamingTitles((current) => current.map((title, i) => (i === index ? e.target.value : title)))
                    }
                  />
                </div>
              ))}
            </div>
            <Button
              size="xl"
              className="rounded-full"
              disabled={!namingCollection || namingTitles.some((title) => !title.trim())}
              onClick={() => {
                const col = namingCollection;
                const files = namingFiles;
                const titles = namingTitles.map((title) => title.trim());
                setNamingOpen(false);
                setNamingFiles([]);
                setNamingTitles([]);
                setNamingCollection(null);
                if (col && files.length) void uploadToCollection(files, col, titles);
              }}
            >
              Save
            </Button>
          </div>
        </SheetContent>
      </Sheet>
      {preview ? <ChatFilePreview att={preview} onClose={() => setPreview(null)} /> : null}
    </div>
    </PreviewCtx.Provider>
  );
}

function AttachAction({
  label,
  className,
  icon: Icon,
  onClick,
}: {
  label: string;
  className: string;
  icon: typeof FileText;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="flex flex-col items-center gap-1.5">
      <span className={cn("flex size-14 items-center justify-center rounded-full text-white shadow-md", className)}>
        <Icon className="size-6" />
      </span>
      <span className="text-[11px] text-muted-foreground">{label}</span>
    </button>
  );
}

function PendingChip({ item, onRemove }: { item: Pending; onRemove: () => void }) {
  const image =
    item.kind === "file"
      ? Boolean(item.previewUrl)
      : isImageMime(item.doc.mime_type, item.doc.original_filename);
  const name = item.kind === "file" ? item.file.name : item.doc.title;
  return (
    <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-card ring-1 ring-border">
      {item.kind === "file" && item.previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.previewUrl} alt="" className="size-full object-cover" />
      ) : item.kind === "vault" && image ? (
        <AuthThumb id={item.doc.id} alt="" className="size-full object-cover" />
      ) : (
        <div className="flex size-full flex-col items-center justify-center px-1 text-center">
          <FileText className="size-4 text-primary" />
          <p className="mt-0.5 truncate text-[9px] leading-tight">{name}</p>
        </div>
      )}
      <button
        type="button"
        aria-label="Remove attachment"
        onClick={onRemove}
        className="absolute top-0.5 right-0.5 flex size-5 items-center justify-center rounded-full bg-black/70 text-white"
      >
        <X className="size-3" />
      </button>
    </div>
  );
}

function isSaveNote(item: ThreadItem) {
  const text = (item.content || "").trim();
  if (/^saved .+ to /i.test(text) || /^upload to /i.test(text)) {
    return true;
  }
  return item.chat?.data_access?.note === true;
}

function Bubble({
  item,
  pendingIds,
  onReply,
}: {
  item: ThreadItem;
  pendingIds?: Set<string>;
  onReply?: (text: string) => void;
}) {
  const mine = item.role === "user";
  const tree = item.chat?.collection_tree?.length
    ? item.chat.collection_tree
    : Array.isArray(item.chat?.data_access?.collection_tree)
      ? (item.chat.data_access.collection_tree as CollectionNode[])
      : [];
  const saveNote = isSaveNote(item);
  const files = !mine && !saveNote && !item.attachments?.length ? filesFromMessage(item) : [];
  const media = Boolean((!saveNote && item.attachments?.length) || tree.length || files.length);
  const proposal = item.chat?.proposal || proposalFromAccess(item.chat?.data_access);
  const canConfirm = Boolean(
    proposal &&
      proposal.status === "pending" &&
      isConfirmableProposal(proposal.kind) &&
      pendingIds?.has(proposal.id),
  );
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "rounded-2xl px-2.5 py-1.5 shadow-sm",
          media ? "w-[min(100%,22rem)] max-w-[94%]" : "max-w-[86%]",
          mine
            ? "rounded-br-sm bg-accent text-accent-foreground"
            : "rounded-bl-sm bg-card text-card-foreground",
        )}
      >
        {!saveNote && item.attachments?.length ? <MediaGrid items={item.attachments} /> : null}
        {item.content ? (
          <p className="whitespace-pre-wrap px-0.5 text-[15px] leading-snug">{item.content}</p>
        ) : null}
        {tree.length > 0 ? <CollectionExplorer nodes={tree} /> : null}
        {!tree.length && files.length ? <MediaGrid items={files} /> : null}
        <div className="mt-0.5 flex items-center justify-end gap-1 px-0.5">
          {!mine && item.chat && (
            <span className="mr-auto text-[10px] text-muted-foreground">
              {item.chat.external_ai ? "Gemini" : "Private"}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground">{formatTime(item.at)}</span>
          {mine && (item.sending ? <Check className="size-3.5 text-muted-foreground" /> : <CheckCheck className="size-3.5 text-primary" />)}
        </div>
        {!mine && item.chat && !canConfirm && (
          <div className="mt-1 flex gap-1">
            <button
              type="button"
              className="rounded-full p-1 text-muted-foreground hover:bg-muted"
              aria-label="Helpful"
              onClick={() =>
                api("/ai/feedback", {
                  method: "POST",
                  body: JSON.stringify({ message_id: item.chat?.message_id, rating: "correct" }),
                }).then(() => toast.success("Thanks"))
              }
            >
              <ThumbsUp className="size-3.5" />
            </button>
            <button
              type="button"
              className="rounded-full p-1 text-muted-foreground hover:bg-muted"
              aria-label="Not helpful"
              onClick={() =>
                api("/ai/feedback", {
                  method: "POST",
                  body: JSON.stringify({ message_id: item.chat?.message_id, rating: "incorrect" }),
                }).then(() => toast.success("Noted"))
              }
            >
              <ThumbsDown className="size-3.5" />
            </button>
          </div>
        )}
        {canConfirm && (
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              className="h-8 flex-1 rounded-full"
              onClick={() => onReply?.("Confirm")}
            >
              Confirm
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 flex-1 rounded-full"
              onClick={() => onReply?.("Cancel")}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function CollectionExplorer({ nodes }: { nodes: CollectionNode[] }) {
  const [open, setOpen] = useState<Set<string>>(new Set());

  function toggle(id: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="mt-1.5 space-y-1">
      {nodes.map((node) => (
        <CollectionFolder key={node.id} node={node} open={open} onToggle={toggle} />
      ))}
    </div>
  );
}

function CollectionFolder({
  node,
  open,
  onToggle,
}: {
  node: CollectionNode;
  open: Set<string>;
  onToggle: (id: string) => void;
}) {
  const expanded = open.has(node.id);
  const children = node.children || [];
  const [files, setFiles] = useState<Attachment[]>(
    (node.documents || []).map((doc) => ({
      id: doc.id,
      title: doc.title,
      original_filename: doc.original_filename,
      mime_type: doc.mime_type,
      size_bytes: doc.size_bytes,
    })),
  );

  useEffect(() => {
    if (!expanded) return;
    let alive = true;
    api<Array<{ id: string; title: string; original_filename: string; mime_type?: string; size_bytes?: number }>>(
      `/collections/${node.id}/files`,
    )
      .then((rows) => {
        if (!alive) return;
        setFiles(
          (rows || []).map((doc) => ({
            id: doc.id,
            title: doc.title,
            original_filename: doc.original_filename,
            mime_type: doc.mime_type,
            size_bytes: doc.size_bytes,
          })),
        );
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [expanded, node.id]);

  return (
    <div>
      <button
        type="button"
        onClick={() => onToggle(node.id)}
        className="flex w-full items-center gap-2 rounded-xl px-1.5 py-2 text-left hover:bg-black/5 dark:hover:bg-white/5"
      >
        <ChevronRight className={cn("size-4 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-90")} />
        <Folder className="size-4 shrink-0 text-[var(--mint)]" />
        <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{node.name}</span>
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {files.length} {files.length === 1 ? "file" : "files"}
          {children.length ? ` · ${children.length} folder${children.length === 1 ? "" : "s"}` : ""}
        </span>
      </button>
      {expanded && (
        <div className="ml-3 space-y-2 border-l border-border/80 py-1 pl-2">
          {children.map((child) => (
            <CollectionFolder key={child.id} node={child} open={open} onToggle={onToggle} />
          ))}
          {files.length > 0 ? <MediaGrid items={files} /> : null}
          {children.length === 0 && files.length === 0 && (
            <p className="px-2 py-1 text-[12px] text-muted-foreground">Empty</p>
          )}
        </div>
      )}
    </div>
  );
}

function filesFromMessage(item: ThreadItem): Attachment[] {
  const merged = new Map<string, Attachment>();
  const docs = Array.isArray(item.chat?.data_access?.documents)
    ? (item.chat.data_access.documents as Array<{
        id: string;
        title: string;
        original_filename?: string;
        mime_type?: string;
        size_bytes?: number;
      }>)
    : [];
  for (const doc of docs) {
    if (!doc?.id) continue;
    merged.set(doc.id, {
      id: doc.id,
      title: doc.title,
      original_filename: doc.original_filename || doc.title,
      mime_type: doc.mime_type,
      size_bytes: doc.size_bytes,
    });
  }
  for (const ev of item.chat?.evidence || []) {
    const current = merged.get(ev.document_id);
    merged.set(ev.document_id, {
      id: ev.document_id,
      title: ev.document_title || current?.title || "File",
      original_filename: ev.original_filename || current?.original_filename || ev.document_title,
      mime_type: ev.mime_type || current?.mime_type,
      size_bytes: ev.size_bytes || current?.size_bytes,
    });
  }
  return [...merged.values()];
}

function MediaGrid({ items }: { items: Attachment[] }) {
  if (!items.length) return null;
  const shown = items.slice(0, 4);
  const extra = items.length - shown.length;
  return (
    <div
      className={cn(
        "mb-1 overflow-hidden rounded-xl",
        items.length === 1 ? "max-w-[220px]" : "grid grid-cols-2 gap-0.5",
      )}
    >
      {shown.map((att, index) => (
        <MediaTile
          key={`${att.id}-${index}`}
          att={att}
          solo={items.length === 1}
          overflow={index === shown.length - 1 ? extra : 0}
        />
      ))}
    </div>
  );
}

function MediaTile({ att, solo, overflow }: { att: Attachment; solo?: boolean; overflow?: number }) {
  const openPreview = useContext(PreviewCtx);
  const knownNonImage =
    Boolean(att.mime_type) &&
    !att.mime_type!.startsWith("image/") &&
    !isImageMime(att.mime_type, att.original_filename);
  return (
    <button type="button" className="block w-full text-left" onClick={() => openPreview(att)}>
      <span className={cn("relative block overflow-hidden bg-black/10", solo ? "h-52 w-full" : "aspect-square")}>
        {att.previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={att.previewUrl} alt={att.title} className="size-full object-cover" />
        ) : !att.local && !knownNonImage ? (
          <AuthThumb
            id={att.id}
            alt={att.title}
            className="size-full object-cover"
            fallback={<FileTile att={att} />}
          />
        ) : (
          <FileTile att={att} />
        )}
        {overflow ? (
          <span className="absolute inset-0 flex items-center justify-center bg-black/55 text-2xl font-semibold text-white">
            +{overflow}
          </span>
        ) : null}
      </span>
    </button>
  );
}

function FileTile({ att }: { att: Attachment }) {
  return (
    <span className="flex size-full flex-col items-center justify-center gap-1 bg-[#1f2c34] px-2 text-center text-white">
      <span className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-bold">
        {extLabel(att.original_filename || att.title, att.mime_type)}
      </span>
      <span className="line-clamp-2 text-[11px] leading-tight">{att.title || att.original_filename}</span>
      {att.size_bytes ? <span className="text-[10px] text-white/70">{formatBytes(att.size_bytes)}</span> : null}
    </span>
  );
}

function AuthThumb({
  id,
  alt,
  className,
  fallback,
}: {
  id: string;
  alt: string;
  className?: string;
  fallback?: ReactNode;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    let objectUrl = "";
    apiBlob(`/documents/${id}/preview`)
      .then((blob) => {
        if (!alive) return;
        const type = (blob.type || "").toLowerCase();
        if (type.includes("pdf") || type.startsWith("text/") || type.includes("json")) {
          setFailed(true);
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);
  if (failed) return <>{fallback ?? <FileTile att={{ id, title: alt, original_filename: alt }} />}</>;
  if (!url) {
    return (
      <div className={cn("flex items-center justify-center bg-muted", className)}>
        <ImageIcon className="size-6 text-muted-foreground" />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      className={className}
      onError={() => {
        setFailed(true);
        setUrl(null);
      }}
    />
  );
}

function ChatFilePreview({ att, onClose }: { att: Attachment; onClose: () => void }) {
  const [url, setUrl] = useState(att.previewUrl || "");
  const image = Boolean(att.previewUrl) || isImageMime(att.mime_type, att.original_filename);
  const pdf = (att.mime_type || "").includes("pdf") || /\.pdf$/i.test(att.original_filename || att.title || "");
  const [kind, setKind] = useState<"loading" | "image" | "pdf" | "other">(
    att.previewUrl ? "image" : att.local ? (image ? "image" : pdf ? "pdf" : "other") : "loading",
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (att.previewUrl) {
      setUrl(att.previewUrl);
      setKind("image");
      return;
    }
    if (att.local) {
      setKind(image ? "image" : pdf ? "pdf" : "other");
      return;
    }
    let alive = true;
    let objectUrl = "";
    setKind("loading");
    apiBlob(`/documents/${att.id}/preview`)
      .then((blob) => {
        if (!alive) return;
        objectUrl = URL.createObjectURL(blob);
        const type = (blob.type || att.mime_type || "").toLowerCase();
        if (type.includes("pdf") || pdf) setKind("pdf");
        else if (type.startsWith("image/") || image || !type || type.startsWith("application/octet-stream")) setKind("image");
        else setKind("other");
        setUrl(objectUrl);
      })
      .catch(() => {
        if (alive) setKind("other");
      });
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [att, image, pdf]);

  async function onShare() {
    if (att.local) return;
    try {
      await shareDocument(att.id, att.title, att.original_filename);
    } catch (err) {
      if (!isShareCancel(err)) toast.error(err instanceof Error ? err.message : "Could not share");
    }
  }

  async function onDownload() {
    if (att.local) return;
    try {
      await downloadDocument(att.id, att.original_filename || att.title);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not download");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black text-white">
      <header className="flex items-center gap-2 px-3 py-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
        <button type="button" aria-label="Close preview" onClick={onClose} className="flex size-10 items-center justify-center rounded-full hover:bg-white/10">
          <X className="size-5" />
        </button>
        <p className="min-w-0 flex-1 truncate text-sm font-medium">{att.title || att.original_filename}</p>
        {!att.local && (
          <>
            <button type="button" aria-label="Share" onClick={() => void onShare()} className="flex size-10 items-center justify-center rounded-full hover:bg-white/10">
              <Share2 className="size-4" />
            </button>
            <button type="button" aria-label="Download" onClick={() => void onDownload()} className="flex size-10 items-center justify-center rounded-full hover:bg-white/10">
              <Download className="size-4" />
            </button>
          </>
        )}
      </header>
      <div className="flex min-h-0 flex-1 items-center justify-center pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        {kind === "loading" ? (
          <p className="text-sm text-white/70">Loading preview…</p>
        ) : kind === "image" && url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={att.title} className="max-h-full max-w-full object-contain" />
        ) : kind === "pdf" && url ? (
          <iframe title={att.title} src={url} className="h-full w-full border-0 bg-neutral-900" />
        ) : (
          <div className="px-6 text-center text-sm text-white/70">
            <FileTile att={att} />
            <p className="mt-3">Preview is not available for this file.</p>
          </div>
        )}
      </div>
    </div>
  );
}
