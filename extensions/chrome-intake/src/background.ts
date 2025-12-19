// Service worker: stores the latest scraped article and sends to ingest or processing API.

const DEFAULT_ENDPOINT = "http://localhost:8000/process/articles";
const CONTEXT_MENU_ID = "capture-article";
const CAPTURE_TIMEOUT_MS = 45000; // fail fast if a background tab hangs
const pendingBackgroundTabs = new Map<number, number>(); // tabId -> timeoutId
let sending = false;

type ArticlePayload = {
  title: string;
  source: string;
  url: string;
  published_at?: string;
  content?: string;
};

type StoredArticle = ArticlePayload & { scrapedAt: string };
type SendResult =
  | { status: "ok"; duplicate_of?: string }
  | { status: "duplicate"; duplicate_of: string }
  | { status: "error"; error: string };

function deriveQuarter(publishedAt?: string, scrapedAt?: string): string {
  const source = publishedAt || scrapedAt;
  if (source) {
    const datePart = source.split("T")[0];
    const [yearStr, monthStr] = datePart.split("-");
    const year = Number(yearStr);
    const month = Number(monthStr);
    if (Number.isFinite(year) && Number.isFinite(month) && month >= 1 && month <= 12) {
      const quarter = Math.floor((month - 1) / 3) + 1;
      return `${year} Q${quarter}`;
    }
  }

  const now = new Date();
  const quarter = Math.floor(now.getMonth() / 3) + 1;
  return `${now.getFullYear()} Q${quarter}`;
}

function resolvePublishedDate(publishedAt?: string, scrapedAt?: string): string | undefined {
  if (publishedAt) {
    return publishedAt;
  }

  if (scrapedAt) {
    const datePart = scrapedAt.split("T")[0];
    if (datePart) {
      return datePart;
    }
  }

  return undefined;
}

function buildProcessPayload(article: StoredArticle) {
  const publishDate = resolvePublishedDate(article.published_at, article.scrapedAt) ||
    new Date().toISOString().slice(0, 10);
  return {
    title: article.title,
    source: article.source || "Unknown",
    url: article.url,
    content: article.content || "",
    published_at: publishDate,
  };
}

function buildIngestPayload(article: StoredArticle) {
  const publishDate = resolvePublishedDate(article.published_at, article.scrapedAt) ||
    new Date().toISOString().slice(0, 10);
  return {
    company: "Unknown",
    quarter: deriveQuarter(publishDate, article.scrapedAt),
    title: article.title,
    source: article.source || "Unknown",
    url: article.url,
    published_at: publishDate,
    body: article.content || "",
    ingest_source: "chrome_extension",
    facts: [
      {
        fact_id: "fact-1",
        category_path: "Strategy & Miscellaneous News -> General News & Strategy",
        section: "Strategy & Miscellaneous News",
        subheading: "General News & Strategy",
        company: "Unknown",
        quarter: deriveQuarter(publishDate, article.scrapedAt),
        published_at: publishDate,
        content_line: article.title,
        summary_bullets: [article.title],
      },
    ],
  };
}

async function getEndpoint(): Promise<string> {
  const { ingestEndpoint } = await chrome.storage.sync.get({
    ingestEndpoint: DEFAULT_ENDPOINT,
  });
  return ingestEndpoint || DEFAULT_ENDPOINT;
}

async function sendSingle(endpoint: string, body: Record<string, unknown>): Promise<SendResult> {
  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await resp.text();
    let parsed: any = undefined;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      /* ignore parse errors; fallback to raw text */
    }
    if (!resp.ok) {
      const detail = parsed?.detail || text || resp.statusText;
      return { status: "error", error: detail };
    }
    const duplicate_of = parsed?.duplicate_of;
    if (duplicate_of) {
      return { status: "duplicate", duplicate_of };
    }
    return { status: "ok", duplicate_of };
  } catch (err: any) {
    return { status: "error", error: err?.message || String(err) };
  }
}

async function enqueueArticle(article: StoredArticle) {
  const stored = await chrome.storage.local.get({ pendingArticles: [] as StoredArticle[] });
  const pending = [...stored.pendingArticles, article];
  await chrome.storage.local.set({ latestArticle: article, pendingArticles: pending });
  return pending;
}

async function updatePendingArticles(pending: StoredArticle[]) {
  await chrome.storage.local.set({ pendingArticles: pending });
}

async function sendSequential(
  endpoint: string,
  pending: StoredArticle[],
  buildPayload: (article: StoredArticle) => Record<string, unknown>
): Promise<SendResult> {
  let processed = 0;
  const failed: StoredArticle[] = [];

  for (const article of pending) {
    const result = await sendSingle(endpoint, buildPayload(article));
    if (result.status === "error") {
      failed.push(article);
      continue;
    }
    processed += 1;
  }

  await updatePendingArticles(failed);
  if (failed.length) {
    return {
      status: "error",
      error: `Processed ${processed}, failed ${failed.length}.`,
    };
  }
  return { status: "ok" };
}

async function sendProcessBatch(
  endpoint: string,
  pending: StoredArticle[]
): Promise<SendResult> {
  const body = pending.map((article) => buildProcessPayload(article));
  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await resp.text();
    let parsed: any = undefined;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      /* ignore parse errors; fallback to raw text */
    }
    if (!resp.ok) {
      const detail = parsed?.detail || text || resp.statusText;
      return { status: "error", error: detail };
    }

    const results = Array.isArray(parsed?.results) ? parsed.results : [];
    const failed: StoredArticle[] = [];
    let processed = 0;
    let invalid = 0;

    for (const item of results) {
      const idx = Number(item?.index);
      if (!Number.isFinite(idx) || idx < 0 || idx >= pending.length) {
        continue;
      }
      const status = item?.status;
      if (status === "processed" || status === "duplicate") {
        processed += 1;
      } else if (status === "invalid") {
        invalid += 1;
      } else {
        failed.push(pending[idx]);
      }
    }

    // If the server did not return per-item results, keep the queue intact.
    if (!results.length) {
      return { status: "error", error: "Batch response missing per-article results." };
    }

    await updatePendingArticles(failed);
    if (failed.length || invalid) {
      return {
        status: "error",
        error: `Processed ${processed}, failed ${failed.length}, invalid ${invalid}.`,
      };
    }
    return { status: "ok" };
  } catch (err: any) {
    return { status: "error", error: err?.message || String(err) };
  }
}

async function sendPendingArticles(): Promise<SendResult> {
  const endpoint = await getEndpoint();
  const stored = await chrome.storage.local.get({ pendingArticles: [] as StoredArticle[] });
  const pending = stored.pendingArticles as StoredArticle[];
  if (!pending.length) {
    return { status: "error", error: "No articles queued yet." };
  }

  if (endpoint.includes("/ingest/")) {
    return sendSequential(endpoint, pending, buildIngestPayload);
  }
  if (endpoint.includes("/process/articles")) {
    return sendProcessBatch(endpoint, pending);
  }
  return sendSequential(endpoint, pending, buildProcessPayload);
}

async function recordSendResult(result: SendResult) {
  await chrome.storage.local.set({ lastSendStatus: result });
  chrome.runtime.sendMessage({ type: "SEND_RESULT", ...result }).catch(() => undefined);
}

function toOriginPattern(rawUrl: string): string | null {
  try {
    const u = new URL(rawUrl);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return `${u.protocol}//${u.host}/*`;
  } catch {
    return null;
  }
}

function notifyCaptureFailure(reason: string) {
  chrome.runtime.sendMessage({ type: "CAPTURE_FAILED", reason }).catch(() => {
    /* no listeners; best-effort */
  });
}

function ensureContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create(
      {
        id: CONTEXT_MENU_ID,
        title: "Capture article for ingest",
        contexts: ["page", "frame", "link"],
      },
      () => {
        const err = chrome.runtime.lastError;
        if (err && !err.message.includes("duplicate id")) {
          console.warn("Failed to create context menu", err.message);
        }
      }
    );
  });
}

ensureContextMenu();
chrome.runtime.onInstalled.addListener(ensureContextMenu);
chrome.runtime.onStartup.addListener(ensureContextMenu);

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== CONTEXT_MENU_ID || !tab?.id) {
    return;
  }

  const frameUrl = info.frameUrl;
  const targetUrl = info.linkUrl || frameUrl || info.pageUrl || tab.url;
  if (!targetUrl) {
    notifyCaptureFailure("No URL available to capture.");
    return;
  }

  const originPattern = toOriginPattern(targetUrl);
  if (!originPattern) {
    notifyCaptureFailure("Unsupported URL scheme.");
    return;
  }

  // Request must be synchronous on the user-gesture stack; no awaits before this.
  chrome.permissions.request({ origins: [originPattern] }, (granted) => {
    if (chrome.runtime.lastError) {
      console.warn("permissions.request failed:", chrome.runtime.lastError.message);
      notifyCaptureFailure(chrome.runtime.lastError.message);
      return;
    }
    if (!granted) {
      notifyCaptureFailure("Site permission was denied.");
      return;
    }

    // Link capture -> background tab to avoid stealing focus.
    if (info.linkUrl) {
      captureInBackgroundTab(info.linkUrl);
      return;
    }

    // Page/frame capture -> inject into the current tab/frame.
    const frameId = typeof info.frameId === "number" ? info.frameId : undefined;
    chrome.scripting.executeScript({
      target: { tabId: tab.id!, frameIds: frameId !== undefined ? [frameId] : undefined },
      files: ["contentScript.js"],
    });
  });
});

async function captureInBackgroundTab(url: string) {
  const tab = await chrome.tabs.create({ url, active: false });
  const tabId = tab.id;
  if (!tabId) return;

  let listenerRef:
    | ((updatedTabId: number, changeInfo: chrome.tabs.TabChangeInfo) => void)
    | null = null;
  let finished = false;
  const finish = async (reason?: string) => {
    if (finished) return;
    finished = true;
    if (reason) {
      notifyCaptureFailure(reason);
    }
    const timeoutId = pendingBackgroundTabs.get(tabId);
    if (timeoutId) clearTimeout(timeoutId);
    pendingBackgroundTabs.delete(tabId);
    if (listenerRef) {
      chrome.tabs.onUpdated.removeListener(listenerRef);
    }
    chrome.tabs.remove(tabId).catch(() => undefined);
  };

  const timeout = setTimeout(() => {
    finish(
      `Capture timed out after ${Math.round(CAPTURE_TIMEOUT_MS / 1000)}s. Try capturing from the article page (not a link), or retry.`
    );
  }, CAPTURE_TIMEOUT_MS);
  pendingBackgroundTabs.set(tabId, timeout);

  // Wait briefly for load; MV3 does not allow synchronous tab load waits, so use onUpdated listener.
  const injectAndClose = async () => {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["contentScript.js"],
      });
      await finish();
    } catch (err: any) {
      await finish(err?.message ? `Capture failed: ${err.message}` : "Capture failed.");
    }
  };

  const listener = async (
    updatedTabId: number,
    changeInfo: chrome.tabs.TabChangeInfo
  ) => {
    if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
    await injectAndClose();
  };

  listenerRef = listener;
  chrome.tabs.onUpdated.addListener(listener);

  // If the tab is already complete (rare but possible), inject immediately.
  chrome.tabs.get(tabId).then((t) => {
    if (t.status === "complete") {
      injectAndClose();
    }
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "ARTICLE_SCRAPED") {
    const article: StoredArticle = {
      ...message.payload,
      scrapedAt: new Date().toISOString(),
    };
    enqueueArticle(article);

    // Close background capture tabs immediately on success.
    const tabId = sender?.tab?.id;
    if (typeof tabId === "number" && pendingBackgroundTabs.has(tabId)) {
      const timeoutId = pendingBackgroundTabs.get(tabId);
      if (timeoutId) clearTimeout(timeoutId);
      pendingBackgroundTabs.delete(tabId);
      chrome.tabs.remove(tabId).catch(() => undefined);
    }
    sendResponse({ status: "stored" });
    // Fire-and-forget auto-send to pipeline/ingest.
    if (!sending) {
      sending = true;
      sendPendingArticles()
        .then(recordSendResult)
        .finally(() => {
          sending = false;
        });
    }
    return true;
  }

  if (message?.type === "GET_LATEST_ARTICLE") {
    chrome.storage.local.get(["latestArticle", "lastSendStatus", "pendingArticles"]).then((data) => {
      sendResponse({
        article: data.latestArticle,
        sendStatus: data.lastSendStatus,
        pendingCount: Array.isArray(data.pendingArticles) ? data.pendingArticles.length : 0,
      });
    });
    return true;
  }

  if (message?.type === "SEND_TO_INGEST") {
    chrome.storage.local.get("pendingArticles").then(async (data) => {
      const pending = Array.isArray(data.pendingArticles) ? data.pendingArticles : [];
      if (!pending.length) {
        sendResponse({ status: "error", error: "No article scraped yet." });
        return;
      }
      const result = await sendPendingArticles();
      await recordSendResult(result);
      sendResponse(result);
    });
    return true;
  }

  return undefined;
});
