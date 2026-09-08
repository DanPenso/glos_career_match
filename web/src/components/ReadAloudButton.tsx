"use client";

import { useEffect, useRef, useState } from "react";
import { fetchTtsAudio } from "@/lib/api";

/** Turn briefing markdown into speakable plain English. */
export function markdownToSpeechText(markdown: string): string {
  return String(markdown || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => {
      let s = line.trim();
      if (!s) return "";
      s = s.replace(/^#{1,6}\s+/, "");
      s = s.replace(/^[-*+]\s+/, "");
      s = s.replace(/^\d+\.\s+/, "");
      s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
      s = s.replace(/\*([^*]+)\*/g, "$1");
      s = s.replace(/`([^`]+)`/g, "$1");
      s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
      s = s.replace(/[_~]/g, "");
      return s.trim();
    })
    .filter(Boolean)
    .join(". ")
    .replace(/\.\s*\./g, ".")
    .replace(/\s+/g, " ")
    .trim();
}

function pickBritishVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  const preferred =
    voices.find((v) => /en-GB/i.test(v.lang) && /female|uk|british/i.test(v.name)) ||
    voices.find((v) => /en-GB/i.test(v.lang)) ||
    voices.find((v) => /^en[-_]/i.test(v.lang));
  return preferred || voices[0] || null;
}

/** Split long text so engines that truncate single utterances still finish. */
function chunkText(text: string, maxLen = 180): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const chunks: string[] = [];
  let buf: string[] = [];
  for (const w of words) {
    const next = buf.length ? `${buf.join(" ")} ${w}` : w;
    if (next.length > maxLen && buf.length) {
      chunks.push(buf.join(" "));
      buf = [w];
    } else {
      buf.push(w);
    }
  }
  if (buf.length) chunks.push(buf.join(" "));
  return chunks;
}

/** Chunk near OpenAI TTS 4096-char limit on sentence boundaries. */
function chunkForOpenAiTts(text: string, maxLen = 3500): string[] {
  if (text.length <= maxLen) return [text];
  const parts: string[] = [];
  let rest = text;
  while (rest.length > maxLen) {
    let cut = rest.lastIndexOf(". ", maxLen);
    if (cut < maxLen * 0.5) cut = rest.lastIndexOf(" ", maxLen);
    if (cut < maxLen * 0.4) cut = maxLen;
    parts.push(rest.slice(0, cut + 1).trim());
    rest = rest.slice(cut + 1).trim();
  }
  if (rest) parts.push(rest);
  return parts.filter(Boolean);
}

type Engine = "openai" | "browser";

type Props = {
  text: string;
  label?: string;
};

export function ReadAloudButton({ text, label = "Read aloud" }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [statusNote, setStatusNote] = useState("");

  const activeRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlsRef = useRef<string[]>([]);
  const audioQueueRef = useRef<string[]>([]);
  const queueIndexRef = useRef(0);

  function revokeObjectUrls() {
    for (const url of objectUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    objectUrlsRef.current = [];
  }

  function stopAll() {
    activeRef.current = false;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    audioQueueRef.current = [];
    queueIndexRef.current = 0;
    revokeObjectUrls();
    setSpeaking(false);
    setPaused(false);
    setLoading(false);
    setEngine(null);
    setStatusNote("");
  }

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      typeof window.speechSynthesis === "undefined"
    ) {
      return;
    }
    const warm = () => {
      window.speechSynthesis.getVoices();
    };
    warm();
    window.speechSynthesis.addEventListener("voiceschanged", warm);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", warm);
      stopAll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    stopAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  function speakBrowser(plain: string) {
    if (!plain || typeof window === "undefined" || !window.speechSynthesis) {
      throw new Error("Browser speech unavailable");
    }
    const voice = pickBritishVoice();
    const chunks = chunkText(plain);
    if (!chunks.length) return;

    activeRef.current = true;
    setEngine("browser");
    setSpeaking(true);
    setPaused(false);
    setStatusNote("Using device voice");

    const utterances = chunks.map((chunk, i) => {
      const u = new SpeechSynthesisUtterance(chunk);
      u.lang = voice?.lang || "en-GB";
      if (voice) u.voice = voice;
      u.rate = 1;
      u.pitch = 1;
      u.onend = () => {
        if (!activeRef.current) return;
        if (i === utterances.length - 1) {
          activeRef.current = false;
          setSpeaking(false);
          setPaused(false);
          setEngine(null);
          setStatusNote("");
        }
      };
      u.onerror = () => {
        stopAll();
      };
      return u;
    });
    for (const u of utterances) {
      window.speechSynthesis.speak(u);
    }
  }

  function playNextAudio() {
    if (!activeRef.current) return;
    const i = queueIndexRef.current;
    const urls = audioQueueRef.current;
    if (i >= urls.length) {
      activeRef.current = false;
      setSpeaking(false);
      setPaused(false);
      setEngine(null);
      setStatusNote("");
      revokeObjectUrls();
      return;
    }
    const audio = new Audio(urls[i]);
    audioRef.current = audio;
    audio.onended = () => {
      queueIndexRef.current += 1;
      playNextAudio();
    };
    audio.onerror = () => {
      stopAll();
      setStatusNote("Playback failed");
    };
    void audio.play().catch(() => {
      stopAll();
      setStatusNote("Playback blocked — try again");
    });
  }

  async function speakOpenAi(plain: string) {
    const parts = chunkForOpenAiTts(plain);
    const urls: string[] = [];
    for (const part of parts) {
      if (!activeRef.current) {
        revokeObjectUrls();
        return;
      }
      const blob = await fetchTtsAudio(part);
      const url = URL.createObjectURL(blob);
      objectUrlsRef.current.push(url);
      urls.push(url);
    }
    if (!activeRef.current) {
      revokeObjectUrls();
      return;
    }
    audioQueueRef.current = urls;
    queueIndexRef.current = 0;
    setEngine("openai");
    setLoading(false);
    setSpeaking(true);
    setPaused(false);
    setStatusNote("OpenAI voice");
    playNextAudio();
  }

  async function start() {
    const plain = markdownToSpeechText(text);
    if (!plain) return;
    stopAll();
    activeRef.current = true;
    setLoading(true);
    setStatusNote("Preparing audio…");
    try {
      await speakOpenAi(plain);
    } catch {
      if (!activeRef.current) return;
      setLoading(false);
      try {
        speakBrowser(plain);
      } catch {
        stopAll();
        setStatusNote("Read aloud is not available right now.");
      }
    }
  }

  function togglePause() {
    if (!speaking) return;
    if (engine === "openai" && audioRef.current) {
      if (audioRef.current.paused) {
        void audioRef.current.play();
        setPaused(false);
      } else {
        audioRef.current.pause();
        setPaused(true);
      }
      return;
    }
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setPaused(false);
    } else {
      window.speechSynthesis.pause();
      setPaused(true);
    }
  }

  const plain = markdownToSpeechText(text);
  if (!plain) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {!speaking && !loading ? (
        <button
          type="button"
          onClick={() => void start()}
          className="rounded-full bg-[var(--ink)] px-3 py-1.5 text-xs font-medium text-[var(--paper)] transition hover:opacity-90"
          aria-label={label}
        >
          {label}
        </button>
      ) : loading ? (
        <span className="text-xs text-[var(--ink-muted)]" aria-live="polite">
          Preparing audio…
        </span>
      ) : (
        <>
          <button
            type="button"
            onClick={togglePause}
            className="rounded-full bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] ring-1 ring-[var(--line)] transition hover:bg-[var(--paper)]"
            aria-label={paused ? "Resume reading" : "Pause reading"}
          >
            {paused ? "Resume" : "Pause"}
          </button>
          <button
            type="button"
            onClick={stopAll}
            className="rounded-full bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] ring-1 ring-[var(--line)] transition hover:bg-[var(--paper)]"
            aria-label="Stop reading"
          >
            Stop
          </button>
          <span className="text-xs text-[var(--ink-muted)]" aria-live="polite">
            {paused ? "Paused" : statusNote || "Reading…"}
          </span>
        </>
      )}
      {!speaking && !loading && statusNote ? (
        <span className="text-xs text-[var(--ink-muted)]">{statusNote}</span>
      ) : null}
    </div>
  );
}
