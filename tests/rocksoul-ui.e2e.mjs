import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "g4f", "gui", "rocksoul");
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
const remoteChats = new Map([["shared-test-123", { id: "shared-test-123", title: "Shared fixture", messages: [{ role: "user", content: "server-restored conversation" }], updated: 1 }]]);
const toolAuditEvents = [];
const uploadedBuckets = new Map();
let documentPromptReceived = "";
let chatWriteCount = 0;
let chatCompletionCount = 0;
let oauthPollCount = 0;
let failChatWrites = false;
const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  const json = (data) => { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(data)); };
  if (url.pathname === "/__test/fail-share") { failChatWrites = true; return json({ ok: true }); }
  if (url.pathname.startsWith("/backend-api/v2/chat/")) {
    const id = url.pathname.split("/").at(-1);
    if (req.method === "POST") { chatWriteCount += 1; let raw = ""; for await (const chunk of req) raw += chunk; if (failChatWrites) { res.writeHead(503).end("mock share unavailable"); return; } remoteChats.set(id, JSON.parse(raw)); return json({ share_id: id }); }
    if (remoteChats.has(id)) return json(remoteChats.get(id));
    res.writeHead(404).end(); return;
  }
  if (url.pathname === "/backend-api/v2/health/DemoProvider" || url.pathname === "/backend-api/v2/quota/DemoProvider") return json({ status: "healthy", remaining: 42 });
  if (url.pathname === "/backend-api/v2/oauth/DemoProvider") { let raw = ""; for await (const chunk of req) raw += chunk; const payload = raw ? JSON.parse(raw) : {}; if (payload.action === "poll") { oauthPollCount += 1; return json(oauthPollCount === 1 ? { status: "pending", message: "Authorization pending" } : { status: "success", message: "GitHub OAuth successful" }); } return json({ status: "pending", verification_uri: "https://auth.example.test/device", user_code: "ROCK-SOUL", device_code: "mock-device-code", interval: 1, expires_in: 60 }); }
  if (/^\/backend-api\/v2\/files\/[^/]+$/.test(url.pathname)) {
    const bucket = url.pathname.split("/").at(-1);
    if (req.method === "DELETE") { uploadedBuckets.delete(bucket); return json({ deleted: true }); }
    if (req.method === "POST") { for await (const chunk of req) { /* consume multipart document upload */ } uploadedBuckets.set(bucket, "Mock document extracted text"); return json({ bucket_id: bucket, files: ["notes.txt"], media: [] }); }
  }
  if (/^\/backend-api\/v2\/files\/[^/]+\/stream$/.test(url.pathname)) {
    const bucket = url.pathname.split("/").at(-2);
    if (uploadedBuckets.has(bucket)) { res.writeHead(200, { "content-type": "text/plain" }); res.end(uploadedBuckets.get(bucket)); return; }
    res.writeHead(404).end(); return;
  }
  if (url.pathname === "/backend-api/v2/conversation") {
    for await (const chunk of req) { /* consume multipart attachment request */ }
    res.writeHead(200, { "content-type": "text/event-stream" });
    res.end('event: content\ndata: {"type":"content","content":"attachment endpoint response","alt":"Generated test media","urls":["/media/generated.png","/media/generated.mp4","/media/generated.mp3"]}\n\nevent: content\ndata: {"type":"content","content":"<audio controls></audio>\\n\\nAudio transcript","data":"data:audio/mpeg;base64,SUQz"}\n\n');
    return;
  }
  if (url.pathname === "/backend-api/v2/providers") return json([{ name: "DemoProvider", label: "Demo Provider", auth: true, live: true, login: true }]);
  if (url.pathname === "/backend-api/v2/models/DemoProvider") return json([{ id: "demo-model", label: "Demo Model" }]);
  if (url.pathname === "/backend-api/v2/status") return json({ status: "ok", version: "test", latest_version: "test", total_providers: 1, working_providers: 1, total_models: 1 });
  if (url.pathname === "/backend-api/v2/version") return json({ version: "test", latest_version: "test" });
  if (url.pathname === "/backend-api/v2/stats") return json({ totals: { requests: 2, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 }, models: {}, providers: {} });
  if (url.pathname === "/backend-api/v2/log") { if (req.method === "POST") { let raw = ""; for await (const chunk of req) raw += chunk; toolAuditEvents.push(JSON.parse(raw)); return json({}); } return json({ logs: [{ timestamp: "now", event: "browser-test" }], count: 1 }); }
  if (url.pathname === "/backend-api/v2/webmcp/tools") {
    if (req.method === "POST") {
      for await (const chunk of req) { /* consume mock tool request */ }
      return json({ jsonrpc: "2.0", id: 1, result: { content: [{ type: "text", text: "mock tool executed" }] } });
    }
    return json({ tools: [{ name: "search_web", description: "Search the web" }, { name: "read_page", description: "Read a page" }] });
  }
  if (url.pathname === "/pa/providers") return json([{ name: "DemoExtension", description: "Mock extension", url: "javascript:alert(1)" }]);
  if (url.pathname === "/v1/models") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ data: [{ id: "browser-test-model" }] }));
    return;
  }
  if (url.pathname === "/v1/chat/completions") {
    chatCompletionCount += 1;
    let raw = "";
    for await (const chunk of req) raw += chunk;
    let prompt = "";
    try {
      const payload = JSON.parse(raw);
      prompt = payload.messages?.at(-1)?.content || "";
      documentPromptReceived = prompt;
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
    res.write('data: {"choices":[{"delta":{"content":"**ROCKSOUL browser test**\\n\\n```js\\nconst answer = 42;\\n```\\n\\n![pixel](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j8WQAAAAASUVORK5CYII=)\\n\\n[audio sample](https://example.com/sample.mp3)"}}]}\n\n');
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
  const startupErrors = [];
  const failedRequests = [];
  page.on("pageerror", error => startupErrors.push(error.stack || error.message));
  page.on("requestfailed", request => failedRequests.push(request.url() + ": " + (request.failure()?.errorText || "failed")));
  await page.goto("http://127.0.0.1:4173/");
  await page.locator(".skip-link").focus();
  assert.equal(await page.evaluate(() => document.activeElement.classList.contains("skip-link")), true, "skip navigation should be keyboard focusable");
  await page.keyboard.press("Enter");
  assert.equal(await page.evaluate(() => document.activeElement.id), "main-content", "skip navigation should move focus to the main landmark");
  await page.locator("#locale-select").selectOption("id");
  await page.getByRole("link", { name: /Ringkasan/ }).waitFor();
  await page.reload();
  assert.equal(await page.locator("#locale-select").inputValue(), "id", "locale should persist across reload");
  await page.locator("#locale-select").selectOption("en");
  await page.getByRole("link", { name: /Overview/ }).waitFor();
  try { await page.locator(".metric-card").first().waitFor({ timeout: 12000 }); }
  catch { throw new Error("Overview metrics did not render. startupErrors=" + JSON.stringify(startupErrors) + " failedRequests=" + JSON.stringify(failedRequests)); }
  assert.equal(await page.locator("#model-select option[value='browser-test-model']").count(), 1, "runtime model should be listed");
  assert.equal(await page.locator("#model-select").inputValue(), "auto");

  await page.goto("http://127.0.0.1:4173/chat/");
  await page.locator("#prompt").waitFor({ state: "visible" });
  await page.locator("#prompt").fill("Say hello");
  await page.locator("#send").click();
  await page.getByText("ROCKSOUL browser test").waitFor();
  await page.locator(".markdown-body strong").filter({ hasText: "ROCKSOUL browser test" }).waitFor();
  await page.locator(".code-block code").filter({ hasText: "const answer = 42;" }).waitFor();
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async value => { window.__copiedCode = value; } } }));
  await page.locator(".code-copy").first().click();
  await page.getByRole("button", { name: "Copied" }).waitFor();
  assert.equal(await page.evaluate(() => window.__copiedCode), "const answer = 42;");
  await page.locator(".markdown-image").waitFor();
  await page.locator(".markdown-audio").waitFor();
  assert.equal(await page.locator(".markdown-image").getAttribute("alt"), "pixel");
  assert.equal(await page.locator(".message-action-regenerate").count(), 1);
  await page.locator(".message-action-regenerate").click();
  for (let attempt = 0; attempt < 40 && chatCompletionCount < 2; attempt += 1) await page.waitForTimeout(50);
  assert.equal(chatCompletionCount, 2, "regenerate should issue a fresh request to the existing g4f chat API");
  await page.getByText("ROCKSOUL browser test").last().waitFor();
  const downloads = [];
  page.on("download", download => downloads.push(download.suggestedFilename()));
  await page.locator("#export-md").click();
  await page.locator("#export-json").click();
  await page.waitForTimeout(100);
  assert.ok(downloads.includes("Say-hello.md"));
  assert.ok(downloads.includes("Say-hello.json"));
  await page.locator("#history-search").fill("Say hello");
  assert.equal(await page.locator(".history-item").count(), 1);
  page.once("dialog", dialog => dialog.accept("Browser smoke renamed"));
  await page.locator(".history-mini-action").filter({ hasText: "Rename" }).first().click();
  await page.locator(".history-open.active").getByText("Browser smoke renamed", { exact: true }).waitFor();
  await page.locator(".history-mini-action").filter({ hasText: "Pin" }).click();
  await page.locator(".history-mini-action").filter({ hasText: "Unpin" }).waitFor();
  await page.locator(".message.assistant .message-action-copy").click();
  assert.ok((await page.evaluate(() => window.__copiedCode)).includes("const answer = 42;"));
  await page.addInitScript(() => { Object.defineProperty(window.crypto, "randomUUID", { configurable: true, value: undefined }); });
  await page.evaluate(() => { const key = "rocksoul-chat-history-v1"; const items = JSON.parse(localStorage.getItem(key) || "[]"); items[0].id = "1712345678901"; localStorage.setItem(key, JSON.stringify(items)); });
  await page.reload();
  await page.goto("http://127.0.0.1:4173/chat/");
  await page.getByText("ROCKSOUL browser test").waitFor();
  assert.equal(chatWriteCount, 0, "private chat must not be written to the server");
  await page.evaluate(() => { window.__copiedShareUrl = ""; Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async value => { window.__copiedShareUrl = value; } } }); });
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#share-chat").click();
  await page.getByRole("button", { name: "Link copied" }).waitFor();
  const sharedUrl = await page.evaluate(() => window.__copiedShareUrl);
  assert.match(sharedUrl, /\/chat\/\?chat=[a-f0-9]{32}$/i);
  const sharedSnapshot = await page.evaluate(async url => { const id = new URL(url).searchParams.get("chat"); return fetch("/backend-api/v2/chat/" + id).then(response => response.json()); }, sharedUrl);
  assert.ok(sharedSnapshot.messages.some(message => message.content.includes("Say hello")));
  assert.equal(chatWriteCount, 1, "explicit sharing should create one server snapshot");

  await page.locator("#new-chat").click();
  await page.locator("#prompt").fill("Private followup");
  await page.locator("#send").click();
  await page.getByText("ROCKSOUL browser test").last().waitFor();
  assert.equal(chatWriteCount, 1, "a second private chat must remain local");

  await page.evaluate(() => { window.__copiedShareUrl = ""; return fetch("/__test/fail-share"); });
  await page.once("dialog", dialog => dialog.accept());
  await page.locator("#share-chat").click();
  await page.getByRole("button", { name: "Share failed" }).waitFor();
  assert.equal(await page.evaluate(() => window.__copiedShareUrl), "", "failed share must not copy a dead link");

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
  await page.locator(".markdown-image").last().waitFor();
  await page.locator(".markdown-video[src=\"/media/generated.mp4\"]").waitFor();
  await page.locator(".markdown-audio[src=\"/media/generated.mp3\"]").waitFor();
  await page.locator(".markdown-audio").last().waitFor();
  assert.ok((await page.locator(".markdown-audio").last().getAttribute("src")).startsWith("data:audio/mpeg;base64,"));

  await page.goto("http://127.0.0.1:4173/chat/");
  await page.locator("#attachment-input").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("Document fixture") });
  await page.locator("#prompt").fill("Summarize this document");
  await page.locator("#send").click();
  await page.getByText("ROCKSOUL browser test").last().waitFor();
  assert.ok(documentPromptReceived.includes("Mock document extracted text"), "document extraction should use the existing g4f files API and pass extracted text to chat");
  assert.equal(uploadedBuckets.size, 0, "temporary document buckets should be cleaned up");

  await page.goto("http://127.0.0.1:4173/agent/");
  await page.locator(".tool-runner").waitFor();
  page.once("dialog", dialog => dialog.accept());
  await page.locator(".tool-runner textarea").fill('{"query":"test"}');
  const auditResponse = page.waitForResponse(response => response.url().endsWith("/backend-api/v2/log") && response.request().method() === "POST");
  await page.locator(".tool-runner button[type=submit]").click();
  await page.getByText(/mock tool executed/).waitFor();
  await auditResponse;

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
    if (route === "/providers/DemoProvider") { await page.locator('[data-route="/providers/"].active').waitFor(); await page.getByRole("button", { name: "Check health" }).click(); await page.getByText(/healthy/).waitFor(); await page.getByRole("button", { name: "Check quota" }).click(); await page.getByText(/remaining/).waitFor(); await page.getByRole("button", { name: "Start login" }).click(); await page.getByText("Continue authentication").waitFor(); await page.getByText("GitHub OAuth successful").waitFor(); assert.equal(oauthPollCount, 2, "device OAuth should poll until the provider confirms authorization"); }
    if (route === "/apps/") assert.equal(await page.locator(".workspace-card").first().evaluate(node => node.tagName.toLowerCase()), "article", "an extension with an unsafe URL must be informational, not clickable");
    if (route === "/private/") assert.equal(await page.locator(".upload-form input[type=password]").count(), 0);
  }

  // Responsive and accessibility baseline across the primary workspace routes.
  for (const viewport of [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    for (const route of ["/", "/chat/", "/providers/", "/status/", "/stats/", "/logs/", "/agent/", "/browser/", "/apps/", "/private/", "/playground/"]) {
      await page.goto("http://127.0.0.1:4173" + route);
      await page.waitForTimeout(80);
      const layout = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }));
      assert.ok(layout.document <= layout.viewport + 1, `horizontal document overflow at ${viewport.width}px on ${route}: ${JSON.stringify(layout)}`);
      assert.ok(layout.body <= layout.viewport + 1, `horizontal body overflow at ${viewport.width}px on ${route}: ${JSON.stringify(layout)}`);
      const unnamed = await page.locator("button:visible").evaluateAll(nodes => nodes
        .filter(node => !(node.getAttribute("aria-label") || node.getAttribute("title") || node.innerText || "").trim())
        .map(node => node.outerHTML.slice(0, 180)));
      assert.deepEqual(unnamed, [], `visible buttons must have accessible names on ${route}`);
    }
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  const reducedMotionDuration = await page.locator(".workspace-card").first().evaluate(node => getComputedStyle(node).transitionDuration).catch(() => "0s");
  assert.ok(reducedMotionDuration.split(",").every(value => parseFloat(value) === 0), "reduced-motion preference should disable card transitions");

  // Check representative translated controls, not only the locale selector.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("http://127.0.0.1:4173/");
  await page.locator("#locale-select").selectOption("id");
  await page.getByRole("link", { name: /Ringkasan/ }).waitFor();
  await page.getByRole("link", { name: /Percakapan baru/ }).waitFor();
  await page.getByRole("button", { name: "Bersihkan" }).waitFor();

  const restrictedPage = await browser.newPage();
  const pageErrors = [];
  restrictedPage.on("pageerror", error => pageErrors.push(error.message));
  await restrictedPage.addInitScript(() => Object.defineProperty(window, "localStorage", { get() { throw new DOMException("blocked", "SecurityError"); } }));
  await restrictedPage.goto("http://127.0.0.1:4173/");
  await restrictedPage.locator("#new-chat").click();
  assert.deepEqual(pageErrors, []);
  await restrictedPage.close();

  assert.ok(toolAuditEvents.some(event => event.event === "rocksoul.webmcp.invocation" && event.status === "success"));
  console.log("ROCKSOUL browser smoke passed: unified pages, shared conversations, media attachments, provider login/health/quota, WebMCP confirmation/audit, SSE handling, stop, and restricted-storage resilience.");
} finally {
  if (browser) await browser.close();
  await new Promise((resolveClose) => server.close(resolveClose));
}
