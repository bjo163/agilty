import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "g4f", "gui", "rocksoul");
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
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
  const relative = url.pathname === "/" ? "index.html" : url.pathname.replace(/^\/rocksoul-assets\//, "");
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
  await page.locator("#model-select option[value='browser-test-model']").waitFor();
  assert.equal(await page.locator("#model-select").inputValue(), "auto");

  await page.locator("#prompt").fill("Say hello");
  await page.locator("#send").click();
  await page.getByText("ROCKSOUL browser test").waitFor();

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

  console.log("ROCKSOUL browser smoke passed: shell, model discovery, SSE, provider errors, stop, and persisted local history.");
} finally {
  if (browser) await browser.close();
  await new Promise((resolveClose) => server.close(resolveClose));
}
