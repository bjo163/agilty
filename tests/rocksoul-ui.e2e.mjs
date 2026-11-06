import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "g4f", "gui", "rocksoul");
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
const remoteChats = new Map([["shared-test-123", { id: "shared-test-123", title: "Shared fixture", messages: [{ role: "user", content: "server-restored conversation" }], updated: 1 }]]);
const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  const json = (data) => { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(data)); };
  if (url.pathname.startsWith("/backend-api/v2/chat/")) {
    const id = url.pathname.split("/").at(-1);
    if (req.method === "POST") { let raw = ""; for await (const chunk of req) raw += chunk; remoteChats.set(id, JSON.parse(raw)); return json({ share_id: id }); }
    if (remoteChats.has(id)) return json(remoteChats.get(id));
    res.writeHead(404).end(); return;
  }
  if (url.pathname === "/backend-api/v2/health/DemoProvider" || url.pathname === "/backend-api/v2/quota/DemoProvider") return json({ status: "healthy", remaining: 42 });
  if (url.pathname === "/backend-api/v2/conversation") {
    for await (const chunk of req) { /* consume multipart attachment request */ }
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.end('event: content\ndata: {"type":"content","content":"attachment endpoint response"}\n\n');
    return;
  }
  if (url.pathname === "/backend-api/v2/providers") return json([{ name: "DemoProvider", label: "Demo Provider", auth: false, live: true }]);
  if (url.pathname === "/backend-api/v2/models/DemoProvider") return json([{ id: "demo-model", label: "Demo Model" }]);
  if (url.pathname === "/backend-api/v2/status") return json({ status: "ok", version: "test", latest_version: "test", total_providers: 1, working_providers: 1, total_models: 1 });
  if (url.pathname === "/backend-api/v2/version") return json({ version: "test", latest_version: "test" });
  if (url.pathname === "/backend-api/v2/stats") return json({ totals: { requests: 2, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 }, models: {}, providers: {} });
  if (url.pathname === "/backend-api/v2/log") return json({ logs: [{ timestamp: "now", event: "browser-test" }], count: 1 });
  if (url.pathname === "/backend-api/v2/webmcp/tools") {
    if (req.method === "POST") {
      for await (const chunk of req) { /* consume mock tool request */ }
      return json({ jsonrpc: "2.0", id: 1, result: { content: [{ type: "text", text: "mock tool executed" }] } });
    }
    return json({ tools: [{ name: "search_web", description: "Search the web" }, { name: "read_page", description: "Read a page" }] });
  }
  if (url.pathname === "/pa/providers") return json([{ name: "DemoExtension", description: "Mock extension" }]);
  if (url.pathname === "/v1/models") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ data: [{ id: "browser-test-model" }] }));
    return;
  }
  if (url.pathname === "/v1/chat/completions") {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    let prompt = "";
    try {
      const payload = JSON.parse(raw);
      prompt = payload.messages?.at(-1)?.content || "";
    } catch {}
    if (prompt === "trigger error") {
      res.writeHead(503, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: "mock provider unavailable" } }));
      return;
    }
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
    if (prompt === "eof without newline") {
      res.end('data: {"choices":[{"delta":{"content":"SSE EOF flush"}}]}');
      return;
    }
    if (prompt === "stop after partial") {
      res.write('data: {"choices":[{"delta":{"content":"partial before stop"}}]}\n\n');
      // Keep the stream open so the browser Stop control exercises AbortController.
      return;
    }
    res.write('data: {"choices":[{"delta":{"content":"ROCKSOUL browser test"}}]}\n\n');
    res.write("data: [DONE]\n\n");
    res.end();
    return;
  }
  const appRoutes = new Set(["/", "/index.html", "/home.html", "/chat/", "/providers/", "/providers", "/stats/", "/status/", "/logs/", "/agent/", "/browser/", "/playground/", "/apps/", "/private/"]);
  const isAppRoute = appRoutes.has(url.pathname) || ["/providers/", "/chat/", "/apps/", "/private/", "/playground/"].some(prefix => url.pathname.startsWith(prefix));
  const relative = isAppRoute ? "index.html" : url.pathname.replace(/^\/rocksoul-assets\//, "");
  if (relative.includes("..") || relative.startsWith("/")) {
    res.writeHead(404).end();
    return;
  }
  try {
    const body = await readFile(resolve(root, relative));
    const ext = relative.slice(relative.lastIndexOf("."));
    res.writeHead(200, { "content-type": mime[ext] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404).end();
  }
});

await new Promise((resolveListen) => server.listen(4173, "127.0.0.1", resolveListen));
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:4173/");
  await page.locator(".metric-card").first().waitFor();
  await page.locator("#model-select option[value='browser-test-model']").waitFor();
  assert.equal(await page.locator("#model-select").inputValue(), "auto");

  await page.locator("#prompt").fill("Say hello");
  await page.locator("#send").click();
  await page.getByText("ROCKSOUL browser test").waitFor();

  await page.locator("#new-chat").click();
  await page.locator("#prompt").fill("eof without newline");
  await page.locator("#send").click();
  await page.getByText("SSE EOF flush").waitFor();

  await page.locator("#new-chat").click();
  await page.locator("#prompt").fill("trigger error");
  await page.locator("#send").click();
  await page.getByText(/mock provider unavailable/).waitFor();

  await page.locator("#new-chat").click();
  await page.locator("#prompt").fill("stop after partial");
  await page.locator("#send").click();
  await page.getByText("partial before stop").waitFor();
  await page.locator("#stop").waitFor({ state: "visible" });
  await page.locator("#stop").click();
  await page.locator("#stop").waitFor({ state: "hidden" });
  await page.reload();
  await page.getByText("partial before stop").waitFor();

  await page.goto("http://127.0.0.1:4173/chat/?chat=shared-test-123");
  await page.getByText("server-restored conversation").waitFor();

  await page.goto("http://127.0.0.1:4173/chat/");
  await page.locator("#attachment-input").setInputFiles({ name: "attachment.png", mimeType: "image/png", buffer: Buffer.from("hello from attachment") });
  await page.locator("#prompt").fill("Summarize this file");
  await page.locator("#send").click();
  await page.getByText("attachment endpoint response").waitFor();

  await page.goto("http://127.0.0.1:4173/agent/");
  await page.locator(".tool-runner").waitFor();
  page.once("dialog", dialog => dialog.accept());
  await page.locator(".tool-runner textarea").fill('{"query":"test"}');
  await page.locator(".tool-runner button[type=submit]").click();
  await page.getByText(/mock tool executed/).waitFor();

  for (const [route, selector] of [
    ["/providers/", ".workspace-card"],
    ["/providers/DemoProvider", ".tag"],
    ["/status/", ".metric-card"],
    ["/stats/", ".metric-card"],
    ["/logs/", ".log-entry"],
    ["/agent/", ".data-panel"],
    ["/browser/", ".data-panel"],
    ["/apps/", ".workspace-card"],
    ["/private/", ".upload-form"],
    ["/playground/", "#composer"]
  ]) {
    await page.goto("http://127.0.0.1:4173" + route);
    await page.locator(selector).first().waitFor();
    if (route === "/providers/DemoProvider") { await page.locator('[data-route="/providers/"].active').waitFor(); await page.getByRole("button", { name: "Check health" }).click(); await page.getByText(/healthy/).waitFor(); }
  }

  const restrictedPage = await browser.newPage();
  const pageErrors = [];
  restrictedPage.on("pageerror", error => pageErrors.push(error.message));
  await restrictedPage.addInitScript(() => Object.defineProperty(window, "localStorage", { get() { throw new DOMException("blocked", "SecurityError"); } }));
  await restrictedPage.goto("http://127.0.0.1:4173/");
  await restrictedPage.locator("#new-chat").click();
  assert.deepEqual(pageErrors, []);
  await restrictedPage.close();

  console.log("ROCKSOUL browser smoke passed: all migrated workspace pages, confirmed WebMCP execution, model discovery, SSE EOF flush, provider errors, stop, history reload, and blocked-storage resilience.");
} finally {
  if (browser) await browser.close();
  await new Promise((resolveClose) => server.close(resolveClose));
}
