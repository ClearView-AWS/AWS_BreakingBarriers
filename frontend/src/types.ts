export type Strength = "require" | "prefer" | "avoid";

export type Criterion = {
  id: string;
  /** What the parent wrote. */
  text: string;
  /** The filter it became ("STEM-focused"). Use this for chips, pills and headers. */
  label?: string;
  need: string | null;
  strength: Strength;
  params: Record<string, unknown>;
  kind: string;
  value?: string | null;
  resolved_reading?: string | null;
  ambiguities?: { question?: string; options: string[]; option_ids: string[]; default?: string }[];
};

export type Evidence = {
  criterion_id: string;
  status: "confirmed" | "partial" | "needs_attention" | "unknown";
  value?: string | number | null;
  note?: string;
  source?: { type: string; path: string; as_of?: string | null; confidence?: string | null } | null;
  conflict?: { website_value?: string; profile_value?: string; path?: string } | null;
  review_ids?: string[];
  post_ids?: string[];
  /** When the school itself answered (call, email, staff). */
  answered_at?: string | null;
  stale?: boolean;
};

export type Card = {
  id: string;
  name: string;
  city?: string;
  entity_type?: string;
  level_codes?: string[];
  match: number;
  verified: string;
  summary?: string;
  distance_miles?: number | null;
  /** Listed tuition, private schools only. Not a net price. */
  tuition?: number | null;
  /** Map point. A few schools have none and appear only in the list. */
  lat?: number | null;
  lon?: number | null;
  evidence: Evidence[];
  missed_must?: boolean;
  /** Parent community activity at this school, for the needs in this search. */
  community?: {
    threads: number;
    discussed: { need: string; label: string; parents: number; threads: number; thread_ids: string[] }[];
    demand: { need: string; label: string; count: number }[];
  };
};

/** A nearby program that fills a criterion at one or more shown schools (results.programs). */
export type ProgramPin = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  links: { school_id: string; criterion_id: string; miles: number }[];
};

export type Block = { type: string; payload: Record<string, unknown> };

export type Turn = {
  session_id: string;
  route: string;
  criteria: Criterion[];
  blocks: Block[];
  assumption?: string | null;
  /** The reply's language: the language of the parent's latest typed message ("es", "ht"...). */
  language?: string | null;
  /** Set when this turn's message was not English and Amazon Translate read it. */
  read_from?: string | null;
  /** This turn's tap line ("You saved X."), already in the reply's language. */
  tap?: string | null;
};

/** Fallback first-run chips when `/api/examples` is unreachable. */
export const DEMO_QUERY =
  "Middle school in Seattle that must have a gifted program and after-school care. Prefer a small school.";

export const FALLBACK_EXAMPLES = [
  DEMO_QUERY,
  "Elementary school in Tacoma with English learner support",
  "High school in Spokane that must have sports. Gifted is a plus.",
];
