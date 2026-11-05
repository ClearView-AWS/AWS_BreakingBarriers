import { staffPost } from "./staff";
import type { Turn } from "./types";

export async function postTurn(body: Record<string, unknown>): Promise<Turn> {
  const response = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Search failed (${response.status})`);
  return response.json();
}

export async function fetchSession(sessionId: string) {
  const response = await fetch(`/api/session/${sessionId}`);
  if (!response.ok) throw new Error(`Session failed (${response.status})`);
  return response.json();
}

export async function fetchInbox() {
  const response = await fetch("/api/inbox");
  if (!response.ok) throw new Error(`Inbox failed (${response.status})`);
  return response.json();
}

export async function replyInbox(questionId: string, body: { text: string; value: string }) {
  const response = await staffPost(`/api/inbox/${questionId}/reply`, body);
  if (!response.ok) throw new Error(`Reply failed (${response.status})`);
  return response.json();
}
