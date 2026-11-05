import type { Page, Route } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

function fixture(name: string) {
  return JSON.parse(readFileSync(join(root, name), "utf8"));
}

const t1 = fixture("t1.json");
const t2 = fixture("t2.json");
const session = fixture("session.json");
const faq = fixture("faq.json");
const personas = fixture("personas.json");
const cschools = fixture("cschools.json");
const cschool = fixture("cschool.json");
const thread = fixture("thread.json");
const assist = fixture("assist.json");
const zones = fixture("zones.json");

/** Mock Guided Search API with captured fixtures so a11y runs offline. */
export async function mockApi(page: Page) {
  let chatCalls = 0;

  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/health") {
      return route.fulfill({ json: { ok: true } });
    }
    if (path === "/api/faq" || path.startsWith("/api/faq")) {
      return route.fulfill({ json: faq });
    }
    if (path === "/api/community/personas") {
      return route.fulfill({ json: personas });
    }
    if (path === "/api/community/schools" && method === "GET") {
      return route.fulfill({ json: cschools });
    }
    if (path.match(/\/api\/community\/schools\/[^/]+$/) && method === "GET") {
      return route.fulfill({ json: cschool });
    }
    if (path.includes("/digest") && method === "POST") {
      return route.fulfill({ json: { digest: cschool.digest ?? null } });
    }
    if (path.startsWith("/api/community/threads/")) {
      return route.fulfill({ json: thread });
    }
    if (path.startsWith("/api/session/")) {
      return route.fulfill({ json: session });
    }
    if (path === "/api/assist" || path.startsWith("/api/assist")) {
      return route.fulfill({ json: assist });
    }
    if (path.includes("/zones") || path.includes("/zone")) {
      return route.fulfill({ json: zones });
    }
    if (path === "/api/ui-text" && method === "POST") {
      return route.fulfill({ json: { language: "en", strings: {} } });
    }
    if (path === "/api/chat" && method === "POST") {
      chatCalls += 1;
      const body = request.postDataJSON() as Record<string, unknown>;
      // First parent message → clarifying turn; later → results with evidence grid.
      const payload = chatCalls === 1 && body.message ? t1 : t2;
      return route.fulfill({ json: payload });
    }

    return route.fulfill({ status: 404, json: { error: `unmocked ${method} ${path}` } });
  });
}
