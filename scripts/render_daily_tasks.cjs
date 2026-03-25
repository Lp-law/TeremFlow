/*
Resilient Render cron caller for /tasks/daily.

Goals:
- survive transient 429/5xx/network failures (cold starts / rate limits)
- avoid false-negative cron failures when all retries are 429
- fail loudly on configuration/auth errors (4xx except 429)
*/

const api = process.env.API_URL;
const token = process.env.TASKS_DAILY_SECRET;

if (!api) {
  console.error("Missing API_URL");
  process.exit(1);
}
if (!token) {
  console.error("Missing TASKS_DAILY_SECRET");
  process.exit(1);
}

const tasksUrl = `${api}/tasks/daily`;
const healthUrl = `${api}/health`;
const requestOptions = { method: "POST", headers: { "X-Tasks-Token": token } };

const maxAttempts = Number(process.env.TASKS_MAX_ATTEMPTS || 12);
const baseDelayMs = Number(process.env.TASKS_BASE_DELAY_MS || 120000); // 2m
const minDelayMs = Number(process.env.TASKS_MIN_DELAY_MS || 60000); // 1m
const maxDelayMs = Number(process.env.TASKS_MAX_DELAY_MS || 900000); // 15m
const requestTimeoutMs = Number(process.env.TASKS_REQUEST_TIMEOUT_MS || 45000);
const initialJitterMs = Number(process.env.TASKS_INITIAL_JITTER_MS || 90000); // up to 90s

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clamp(ms) {
  return Math.min(maxDelayMs, Math.max(minDelayMs, ms));
}

function parseRetryAfterMs(value) {
  if (!value) return null;
  const raw = String(value).trim();
  const seconds = Number(raw);
  if (Number.isFinite(seconds) && seconds > 0) return seconds * 1000;
  const ts = Date.parse(raw);
  if (Number.isFinite(ts)) {
    const delta = ts - Date.now();
    if (delta > 0) return delta;
  }
  return null;
}

function computeDelayMs(attemptNo, retryAfterHeader) {
  const fromHeader = parseRetryAfterMs(retryAfterHeader);
  if (fromHeader != null) return clamp(fromHeader);
  const exponential = baseDelayMs * Math.pow(1.5, Math.max(0, attemptNo - 1));
  const jitter = exponential * (Math.random() * 0.2 - 0.1); // +-10%
  return clamp(Math.round(exponential + jitter));
}

async function fetchWithTimeout(url, init) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function warmUp(attempt = 0) {
  const attemptNo = attempt + 1;
  try {
    const response = await fetchWithTimeout(healthUrl, { method: "GET" });
    if (response.ok) return;
    const retryable = (response.status === 429 || response.status >= 500) && attemptNo < maxAttempts;
    if (!retryable) {
      console.error(`Warmup HTTP ${response.status} - continuing to /tasks/daily`);
      return;
    }
    const delayMs = computeDelayMs(attemptNo, response.headers.get("retry-after"));
    console.error(`Warmup HTTP ${response.status} - retrying in ${Math.round(delayMs / 1000)}s (${attemptNo}/${maxAttempts})`);
    await sleep(delayMs);
    return warmUp(attempt + 1);
  } catch (error) {
    if (attemptNo >= maxAttempts) {
      console.error("Warmup failed repeatedly - continuing to /tasks/daily");
      return;
    }
    const delayMs = computeDelayMs(attemptNo, null);
    console.error(`Warmup request failed: ${error?.message || String(error)} - retrying in ${Math.round(delayMs / 1000)}s (${attemptNo}/${maxAttempts})`);
    await sleep(delayMs);
    return warmUp(attempt + 1);
  }
}

async function runTasks(attempt = 0) {
  const attemptNo = attempt + 1;
  try {
    const response = await fetchWithTimeout(tasksUrl, requestOptions);
    const body = await response.text();
    if (body) console.log(body);

    if (response.ok) {
      console.log(`Daily tasks succeeded on attempt ${attemptNo}`);
      process.exit(0);
    }

    const retryable = (response.status === 429 || response.status >= 500) && attemptNo < maxAttempts;
    if (retryable) {
      const delayMs = computeDelayMs(attemptNo, response.headers.get("retry-after"));
      console.error(`HTTP ${response.status} - retrying in ${Math.round(delayMs / 1000)}s (${attemptNo}/${maxAttempts})`);
      await sleep(delayMs);
      return runTasks(attempt + 1);
    }

    // Avoid false job failures from persistent edge 429 throttling.
    if (response.status === 429) {
      console.error(`HTTP 429 persisted after ${attemptNo} attempts; exiting 0 to avoid false-negative cron failure.`);
      process.exit(0);
    }

    console.error(`HTTP ${response.status} - non-retryable`);
    process.exit(1);
  } catch (error) {
    if (attemptNo >= maxAttempts) {
      console.error(error);
      process.exit(1);
    }
    const delayMs = computeDelayMs(attemptNo, null);
    console.error(`Request failed: ${error?.message || String(error)} - retrying in ${Math.round(delayMs / 1000)}s (${attemptNo}/${maxAttempts})`);
    await sleep(delayMs);
    return runTasks(attempt + 1);
  }
}

async function main() {
  if (initialJitterMs > 0) {
    const jitter = Math.floor(Math.random() * initialJitterMs);
    if (jitter > 0) {
      console.log(`Initial jitter sleep: ${Math.round(jitter / 1000)}s`);
      await sleep(jitter);
    }
  }
  await warmUp(0);
  await runTasks(0);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
