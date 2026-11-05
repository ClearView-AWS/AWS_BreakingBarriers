/** Demo chrome (persona switcher) stays off for parents unless explicitly enabled. */

export const DEMO_STORAGE_KEY = "gs-demo";

export function readDemoFlag(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1" || params.get("demo") === "true") return true;
    if (params.get("demo") === "0" || params.get("demo") === "false") return false;
    return localStorage.getItem(DEMO_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeDemoFlag(on: boolean): void {
  try {
    if (on) localStorage.setItem(DEMO_STORAGE_KEY, "1");
    else localStorage.removeItem(DEMO_STORAGE_KEY);
  } catch {
    // Storage can be blocked; URL sync still works for this visit.
  }
  try {
    const url = new URL(window.location.href);
    if (on) url.searchParams.set("demo", "1");
    else url.searchParams.delete("demo");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  } catch {
    // History API can fail in sandboxed embeds; ignore.
  }
}
