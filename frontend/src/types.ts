export type Strength = "require" | "prefer" | "avoid";

export type Criterion = {
  id: string;
  text: string;
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
  evidence: Evidence[];
  missed_must?: boolean;
};

export type Block = { type: string; payload: Record<string, unknown> };

export type Turn = {
  session_id: string;
  route: string;
  criteria: Criterion[];
  blocks: Block[];
  assumption?: string | null;
};

export const DEMO_QUERY =
  "Middle school in Jacksonville with STEM and after-school care. Money is tight.";
