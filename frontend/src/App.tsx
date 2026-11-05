import { useEffect, useRef, useState } from "react";
import { HighlightAssistant } from "./Assistant";
import { FaqWidget } from "./Faq";
import type { Turn } from "./types";
import { SavedDeadline, onZonedTap, type Access } from "./GettingIn";
import { Chat, newTapLine, type Entry, type HistoryEntry } from "./Chat";
import type { Actions, Picked } from "./blocks";
import { CommunityHome, CommunityPage, PersonaSwitcher, type CommunityTarget } from "./Community";
import type { ResultsView } from "./Views";
import { t, useUiLanguage } from "./i18n";

type View = "search" | "saved" | "community";
type ChatTurn = Turn & { history?: HistoryEntry[] };

async function postChat(body: Record<string, unknown>): Promise<ChatTurn> {
  // /api/chat takes the same body as /api/turn, keeps the conversation and answers follow-ups.
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(t("app.error_status", { status: response.status }));
  return response.json();
}

export function App() {
  const [view, setView] = useState<View>("search");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(savedTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("gs-theme", theme);
    } catch {
      // Storage can be blocked; the theme still applies for this visit.
    }
  }, [theme]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<Picked[]>([]);
  // Results open as a list; once the parent picks Grid or Map, it sticks for the session.
  const [resultsView, setResultsView] = useState<ResultsView>("list");
  const [saved, setSaved] = useState<{ id: string; name: string; city?: string }[]>([]);
  const [checklist, setChecklist] = useState<{ school_name: string; question: string }[]>([]);
  // The persona switcher stands in for logins: Parent A, Parent B or School staff.
  const [persona, setPersona] = useState("parent_a");
  // null shows the Community home; a target shows that school's page.
  const [community, setCommunity] = useState<CommunityTarget | null>(null);
  // Set when someone posts in the community, so the results refresh on the way back.
  const communityChanged = useRef(false);
  const history = useRef<HistoryEntry[]>([]);

  const lastTurn = [...entries].reverse().find((entry): entry is Extract<Entry, { role: "agent" }> => entry.role === "agent")?.turn;
  // The whole UI follows the language of the latest reply (the parent's latest typed message).
  useUiLanguage(lastTurn?.language);

  // Everything the parent types or taps goes through here and lands in the chat.
  async function send(body: Record<string, unknown>) {
    const message = typeof body.message === "string" ? body.message.trim() : "";
    if (message) setEntries((list) => [...list, { role: "parent", kind: "message", text: message }]);
    setBusy(true);
    try {
      const data = await postChat({ session_id: sessionId, ...body });
      setSessionId(data.session_id);
      // The backend sends this turn's tap line already in the reply's language.
      const tap = message ? null : data.tap ?? newTapLine(history.current, data.history ?? []);
      history.current = data.history ?? [];
      setEntries((list) => [
        ...list,
        ...(tap ? [{ role: "parent", kind: "event", text: tap } as Entry] : []),
        { role: "agent", turn: data },
      ]);
      if (data.route === "save") void refreshSaved(data.session_id);
      return data;
    } catch (err) {
      setEntries((list) => [...list, { role: "system", text: err instanceof Error ? err.message : t("app.error") }]);
      return null;
    } finally {
      setBusy(false);
    }
  }
  // "Yes, it's mine" on a public school card. The backend keeps only the school ID.
  onZonedTap((schoolId, value) => void send({ action: "refresh", zoned: { school_id: schoolId, value } }));

  function openCommunity(target: CommunityTarget | null) {
    setCommunity(target);
    setView("community");
    window.scrollTo({ top: 0 });
  }

  function openSearch() {
    setView("search");
    // A school answer or parent posts can change a card's evidence. Rerun the search once.
    if (communityChanged.current && sessionId) void send({ action: "refresh" });
    communityChanged.current = false;
  }

  const actions: Actions = { send: (body) => void send(body), busy, picked, setPicked, openCommunity, resultsView, setResultsView, sessionId };

  async function refreshSaved(nextSession = sessionId) {
    if (!nextSession) return;
    const response = await fetch(`/api/session/${nextSession}`);
    const data = await response.json();
    setSaved(data.saved ?? []);
    setChecklist(data.checklist ?? []);
  }

  return (
    <div className={view === "search" ? "app chat-mode" : "app"}>
      <a className="skip-link" href="#main-content">
        {t("a11y.skip_main")}
      </a>
      <header className="topbar">
        <a className="brand" href="/" title={t("app.tagline")} onClick={(event) => event.preventDefault()}>
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">
            <strong>GreatSchools</strong>
            <em>Guided Search</em>
          </span>
        </a>
        <nav className="nav" aria-label="Primary">
          <button type="button" aria-pressed={view === "search"} onClick={openSearch}>{t("app.search")}</button>
          <button
            type="button"
            aria-pressed={view === "saved"}
            onClick={async () => {
              setView("saved");
              await refreshSaved();
            }}
          >
            {t("app.saved", { n: saved.length })}
          </button>
          <button type="button" aria-pressed={view === "community"} onClick={() => openCommunity(null)}>{t("app.community")}</button>
        </nav>
        <PersonaSwitcher value={persona} onChange={setPersona} />
        <button
          type="button"
          className="theme-switch"
          aria-pressed={theme === "dark"}
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
        >
          {theme === "light" ? "☾ Dark mode" : "☀ Light mode"}
        </button>
      </header>
      <main id="main-content" className={view === "search" ? "chat-main" : "wrap"} tabIndex={-1}>
        {view === "search" && (
          <Chat entries={entries} actions={actions} onSend={(text) => void send({ message: text })} />
        )}
        {view === "saved" && (
          <section aria-labelledby="saved-title">
            <h1 id="saved-title" className="section-title">{t("app.saved_title")}</h1>
            <p className="sr-only">{t("a11y.saved_help")}</p>
            {saved.length === 0 && <p role="status">{t("app.saved_empty")}</p>}
            <ul className="checklist" aria-label={t("app.saved_title")}>
              {saved.map((school) => (
                <li key={school.id}><strong>{school.name}</strong> · {school.city}<SavedDeadline access={(school as { access?: Access }).access} /></li>
              ))}
            </ul>
            {checklist.length > 0 && (
              <>
                <h2 className="section-title" id="checklist-title">{t("app.checklist")}</h2>
                <ul className="checklist" aria-labelledby="checklist-title">
                  {checklist.map((item, index) => (
                    <li key={index}><strong>{item.school_name}.</strong> {item.question}</li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
        {view === "community" && !community && (
          <CommunityHome onOpen={(schoolId) => openCommunity({ schoolId, from: "home" })} />
        )}
        {view === "community" && community && (
          <CommunityPage
            key={`${community.schoolId}-${community.draftNeed ?? ""}-${community.filterNeed ?? ""}`}
            schoolId={community.schoolId}
            persona={persona}
            sessionId={sessionId}
            draftNeed={community.draftNeed}
            filterNeed={community.filterNeed}
            backLabel={community.from === "results" ? t("app.back_results") : t("app.all_schools")}
            onBack={() => (community.from === "results" ? openSearch() : openCommunity(null))}
            onChanged={() => {
              communityChanged.current = true;
            }}
          />
        )}
      </main>
      <HighlightAssistant sessionId={sessionId} rootSelector="#root" />
      <FaqWidget persona={persona} />
    </div>
  );
}


type Theme = "dark" | "light";

// A choice the parent made wins; otherwise follow the device's light or dark setting.
function savedTheme(): Theme {
  try {
    const saved = localStorage.getItem("gs-theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    // Storage can be blocked; fall through to the device setting.
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
