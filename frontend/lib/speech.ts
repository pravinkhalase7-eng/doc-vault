export type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

export type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    0: { transcript: string };
  }>;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

export function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as SpeechWindow;
  return speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition || null;
}

export function speechSupported() {
  return Boolean(getSpeechRecognition());
}

export function speechLang(code?: string) {
  const value = (code || "en").toLowerCase();
  if (value.startsWith("hi")) return "hi-IN";
  if (value.startsWith("mr")) return "mr-IN";
  if (value.startsWith("en")) return "en-IN";
  return code || "en-IN";
}

export function speakText(text: string, lang = "en-IN") {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const cleaned = text.replace(/\n+/g, ". ").replace(/\s+/g, " ").trim();
  if (!cleaned) return;
  const utter = new SpeechSynthesisUtterance(cleaned.slice(0, 700));
  utter.lang = lang;
  utter.rate = 1.02;
  window.speechSynthesis.speak(utter);
}

export function stopSpeaking() {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}
