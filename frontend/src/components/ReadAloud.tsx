// Browser speechSynthesis — no AWS dependency. Speaks in the UI language when possible.
import { useEffect, useRef, useState } from "react";
import { t, uiLanguage } from "../i18n";

type Props = {
  text: string;
  /** BCP-47 tag from the reply; falls back to the current UI language. */
  lang?: string | null;
};

function pickVoice(lang: string): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  const exact = voices.find((voice) => voice.lang.toLowerCase() === lang.toLowerCase());
  if (exact) return exact;
  const prefix = lang.split("-")[0].toLowerCase();
  return voices.find((voice) => voice.lang.toLowerCase().startsWith(prefix)) ?? null;
}

export function ReadAloud({ text, lang }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const clean = text.replace(/\s+/g, " ").trim();
  const supported = typeof window !== "undefined" && !!window.speechSynthesis;

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      utterance.current = null;
    };
  }, []);

  if (!clean || !supported) return null;

  function stop() {
    window.speechSynthesis.cancel();
    utterance.current = null;
    setSpeaking(false);
  }

  function toggle() {
    if (speaking) {
      stop();
      return;
    }
    const tag = (lang || uiLanguage() || "en").replace("_", "-");
    const next = new SpeechSynthesisUtterance(clean);
    next.lang = tag;
    const voice = pickVoice(tag);
    if (voice) next.voice = voice;
    next.onend = () => setSpeaking(false);
    next.onerror = () => setSpeaking(false);
    utterance.current = next;
    setSpeaking(true);
    window.speechSynthesis.speak(next);
  }

  return (
    <button type="button" className="read-aloud" aria-pressed={speaking} onClick={toggle}>
      {speaking ? t("a11y.stop_reading") : t("a11y.read_aloud")}
    </button>
  );
}
