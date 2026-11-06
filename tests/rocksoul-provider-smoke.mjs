#!/usr/bin/env node
/**
 * Opt-in live compatibility smoke for the existing g4f Python runtime.
 * No credentials are required or permitted in CI. Set ROCKSOUL_SMOKE=1 locally.
 */
const base = (process.env.ROCKSOUL_BASE_URL || "http://127.0.0.1:8080").replace(/\/$/, "");
const model = process.env.ROCKSOUL_SMOKE_MODEL || "";
const timeoutMs = Math.max(10_000, Math.min(120_000, Number(process.env.ROCKSOUL_SMOKE_TIMEOUT_MS || 45_000)));
const apiKey = process.env.G4F_API_KEY || "";
const displayBase = (() => { try { const url = new URL(base); return url.origin + url.pathname.replace(/\/$/, ""); } catch { return "[configured endpoint]"; } })();
const headers = { "content-type": "application/json", accept: "application/json" };
if (apiKey) headers.authorization = "Bearer " + apiKey;

if (process.env.ROCKSOUL_SMOKE !== "1") {
  process.stdout.write(JSON.stringify({ status: "skipped", reason: "Set ROCKSOUL_SMOKE=1 to opt in." }) + "\n");
  process.exit(0);
}
if (!model) {
  process.stderr.write("ROCKSOUL_SMOKE_MODEL must name a model already exposed by GET /v1/models.\n");
  process.exit(2);
}

const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(new Error("Smoke request timed out")), timeoutMs);
const report = { status: "passed", base_url: displayBase, model, checks: {} };
const safeError = error => error?.name === "AbortError" ? "request aborted or timed out" : String(error?.message || error).slice(0, 240);

try {
  const modelsResponse = await fetch(base + "/v1/models", { headers, signal: controller.signal });
  if (!modelsResponse.ok) throw new Error("Model discovery returned HTTP " + modelsResponse.status);
  const modelPayload = await modelsResponse.json();
  const models = Array.isArray(modelPayload.data) ? modelPayload.data : Array.isArray(modelPayload) ? modelPayload : [];
  const found = models.some(item => (typeof item === "string" ? item : item?.id || item?.name) === model);
  if (!found) throw new Error("Configured model is not present in the current g4f model catalog");
  report.checks.model_discovery = "passed";

  const prompt = "Reply with exactly: ROCKSOUL LIVE SMOKE OK";
  const completionResponse = await fetch(base + "/v1/chat/completions", {
    method: "POST", headers,
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], stream: false }),
    signal: controller.signal,
  });
  if (!completionResponse.ok) throw new Error("Non-streaming completion returned HTTP " + completionResponse.status);
  const completion = await completionResponse.json();
  const answer = completion.choices?.[0]?.message?.content;
  if (typeof answer !== "string" || !answer.trim()) throw new Error("Non-streaming completion returned no message content");
  report.checks.non_streaming = "passed";

  const streamResponse = await fetch(base + "/v1/chat/completions", {
    method: "POST", headers: { ...headers, accept: "text/event-stream" },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], stream: true }),
    signal: controller.signal,
  });
  if (!streamResponse.ok) throw new Error("Streaming completion returned HTTP " + streamResponse.status);
  if (!streamResponse.body) throw new Error("Streaming response body is unavailable");
  const reader = streamResponse.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", streamedText = "", finished = false;
  while (!finished) {
    const part = await reader.read();
    finished = part.done;
    buffer += decoder.decode(part.value || new Uint8Array(), { stream: !finished });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") { finished = true; break; }
      try {
        const event = JSON.parse(payload);
        const delta = event.choices?.[0]?.delta?.content ?? event.content ?? "";
        if (typeof delta === "string") streamedText += delta;
      } catch { /* Ignore non-JSON provider event frames. */ }
    }
  }
  if (buffer.startsWith("data:")) {
    const payload = buffer.slice(5).trim();
    if (payload && payload !== "[DONE]") {
      try { streamedText += JSON.parse(payload).choices?.[0]?.delta?.content || ""; } catch {}
    }
  }
  if (!streamedText.trim()) throw new Error("Streaming completion returned no text deltas");
  report.checks.streaming = "passed";
  report.checks.client_disconnect = "not_run";
  if (process.env.ROCKSOUL_SMOKE_CANCEL === "1") {
    const cancelController = new AbortController();
    const cancelResponse = await fetch(base + "/v1/chat/completions", {
      method: "POST", headers: { ...headers, accept: "text/event-stream" },
      body: JSON.stringify({ model, messages: [{ role: "user", content: "Write a long detailed essay." }], stream: true }),
      signal: cancelController.signal,
    });
    if (!cancelResponse.ok || !cancelResponse.body) throw new Error("Cancellation probe could not open a streaming response");
    const cancelReader = cancelResponse.body.getReader();
    await cancelReader.read();
    cancelController.abort();
    try { await cancelReader.read(); } catch {}
    report.checks.client_disconnect = "abort signal sent; upstream cancellation semantics remain provider-dependent";
  }
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
} catch (error) {
  report.status = "failed";
  report.error = safeError(error);
  process.stderr.write(JSON.stringify(report, null, 2) + "\n");
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
}
