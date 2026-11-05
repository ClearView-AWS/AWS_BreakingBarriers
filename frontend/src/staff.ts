// The staff code unlocks school-staff actions and AI calls (backend/security.py). It lives
// only in this browser: open the site once with ?staff=CODE, or enter it when asked.
const KEY = "clearview.staffKey";

export function captureStaffCode(): void {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("staff");
  if (!code) return;
  localStorage.setItem(KEY, code);
  url.searchParams.delete("staff");
  window.history.replaceState(null, "", url.toString());
}

export function staffHeaders(): Record<string, string> {
  const code = localStorage.getItem(KEY);
  return code ? { "X-Staff-Key": code } : {};
}

/** POST as JSON with the staff code. On 401, ask for the code once and retry. */
export async function staffPost(path: string, body?: unknown): Promise<Response> {
  const send = () =>
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...staffHeaders() },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  const response = await send();
  if (response.status !== 401) return response;
  const code = window.prompt("School-staff code");
  if (!code) return response;
  localStorage.setItem(KEY, code.trim());
  return send();
}
