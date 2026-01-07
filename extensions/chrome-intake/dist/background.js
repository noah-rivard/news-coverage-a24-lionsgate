"use strict";
(() => {
  // src/background.ts
  var DEFAULT_ENDPOINT = "http://localhost:8000/process/articles";
  var CONTEXT_MENU_ID = "capture-article";
  var CAPTURE_TIMEOUT_MS = 45e3;
  var pendingBackgroundTabs = /* @__PURE__ */ new Map();
  var sending = false;
  function deriveQuarter(publishedAt, scrapedAt) {
    const source = publishedAt || scrapedAt;
    if (source) {
      const datePart = source.split("T")[0];
      const [yearStr, monthStr] = datePart.split("-");
      const year = Number(yearStr);
      const month = Number(monthStr);
      if (Number.isFinite(year) && Number.isFinite(month) && month >= 1 && month <= 12) {
        const quarter2 = Math.floor((month - 1) / 3) + 1;
        return `${year} Q${quarter2}`;
      }
    }
    const now = /* @__PURE__ */ new Date();
    const quarter = Math.floor(now.getMonth() / 3) + 1;
    return `${now.getFullYear()} Q${quarter}`;
  }
  function resolvePublishedDate(publishedAt, scrapedAt) {
    if (publishedAt) {
      return publishedAt;
    }
    if (scrapedAt) {
      const datePart = scrapedAt.split("T")[0];
      if (datePart) {
        return datePart;
      }
    }
    return void 0;
  }
  function buildProcessPayload(article) {
    const publishDate = resolvePublishedDate(article.published_at, article.scrapedAt) || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
    return {
      title: article.title,
      source: article.source || "Unknown",
      url: article.url,
      content: article.content || "",
      published_at: publishDate
    };
  }
  function buildIngestPayload(article) {
    const publishDate = resolvePublishedDate(article.published_at, article.scrapedAt) || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
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
          summary_bullets: [article.title]
        }
      ]
    };
  }
  async function getEndpoint() {
    const { ingestEndpoint } = await chrome.storage.sync.get({
      ingestEndpoint: DEFAULT_ENDPOINT
    });
    return ingestEndpoint || DEFAULT_ENDPOINT;
  }
  async function sendSingle(endpoint, body) {
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const text = await resp.text();
      let parsed = void 0;
      try {
        parsed = text ? JSON.parse(text) : void 0;
      } catch {
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
    } catch (err) {
      return { status: "error", error: err?.message || String(err) };
    }
  }
  async function enqueueArticle(article) {
    await chrome.storage.local.set({ latestArticle: article, pendingArticles: [article] });
  }
  async function updatePendingArticles(pending) {
    await chrome.storage.local.set({ pendingArticles: pending });
  }
  function isSameStoredArticle(a, b) {
    return a.url === b.url && a.scrapedAt === b.scrapedAt;
  }
  async function clearPendingIfSame(article) {
    const stored = await chrome.storage.local.get({ pendingArticles: [] });
    const pending = Array.isArray(stored.pendingArticles) ? stored.pendingArticles : [];
    if (pending.length && isSameStoredArticle(pending[0], article)) {
      await updatePendingArticles([]);
    }
  }
  async function sendProcessBatchSingle(endpoint, article) {
    const body = [buildProcessPayload(article)];
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const text = await resp.text();
      let parsed = void 0;
      try {
        parsed = text ? JSON.parse(text) : void 0;
      } catch {
      }
      if (!resp.ok) {
        const detail = parsed?.detail || text || resp.statusText;
        return { status: "error", error: detail };
      }
      const results = Array.isArray(parsed?.results) ? parsed.results : [];
      if (!results.length) {
        return { status: "error", error: "Batch response missing per-article results." };
      }
      const item = results.find((r) => Number(r?.index) === 0) ?? results[0];
      const status = item?.status;
      if (status === "processed" || status === "duplicate") {
        const duplicate_of = typeof item?.duplicate_of === "string" ? item.duplicate_of : void 0;
        if (duplicate_of) {
          return { status: "duplicate", duplicate_of };
        }
        return { status: "ok" };
      }
      if (status === "invalid") {
        return { status: "error", error: item?.error || "Article payload was invalid." };
      }
      return { status: "error", error: item?.error || "Batch processing failed." };
    } catch (err) {
      return { status: "error", error: err?.message || String(err) };
    }
  }
  async function sendArticleOnce(article) {
    const endpoint = await getEndpoint();
    if (endpoint.includes("/ingest/")) {
      return sendSingle(endpoint, buildIngestPayload(article));
    }
    if (endpoint.includes("/process/articles")) {
      return sendProcessBatchSingle(endpoint, article);
    }
    return sendSingle(endpoint, buildProcessPayload(article));
  }
  async function sendPendingLoop() {
    while (true) {
      const stored = await chrome.storage.local.get({ pendingArticles: [] });
      const pending = Array.isArray(stored.pendingArticles) ? stored.pendingArticles : [];
      const article = pending[0];
      if (!article) return;
      const result = await sendArticleOnce(article);
      await recordSendResult(result);
      if (result.status === "error") return;
      await clearPendingIfSame(article);
    }
  }
  async function sendLatestOnce() {
    const stored = await chrome.storage.local.get({ latestArticle: null });
    if (!stored.latestArticle) {
      return { status: "error", error: "No article scraped yet." };
    }
    const result = await sendArticleOnce(stored.latestArticle);
    await recordSendResult(result);
    if (result.status !== "error") {
      await clearPendingIfSame(stored.latestArticle);
    }
    return result;
  }
  async function recordSendResult(result) {
    await chrome.storage.local.set({ lastSendStatus: result });
    chrome.runtime.sendMessage({ type: "SEND_RESULT", ...result }).catch(() => void 0);
  }
  function toOriginPattern(rawUrl) {
    try {
      const u = new URL(rawUrl);
      if (u.protocol !== "http:" && u.protocol !== "https:") return null;
      return `${u.protocol}//${u.host}/*`;
    } catch {
      return null;
    }
  }
  function notifyCaptureFailure(reason) {
    chrome.runtime.sendMessage({ type: "CAPTURE_FAILED", reason }).catch(() => {
    });
  }
  function ensureContextMenu() {
    chrome.contextMenus.removeAll(() => {
      chrome.contextMenus.create(
        {
          id: CONTEXT_MENU_ID,
          title: "Capture article for ingest",
          contexts: ["page", "frame", "link"]
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
      if (info.linkUrl) {
        captureInBackgroundTab(info.linkUrl);
        return;
      }
      const frameId = typeof info.frameId === "number" ? info.frameId : void 0;
      chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: frameId !== void 0 ? [frameId] : void 0 },
        files: ["contentScript.js"]
      });
    });
  });
  async function captureInBackgroundTab(url) {
    const tab = await chrome.tabs.create({ url, active: false });
    const tabId = tab.id;
    if (!tabId) return;
    let listenerRef = null;
    let finished = false;
    const finish = async (reason) => {
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
      chrome.tabs.remove(tabId).catch(() => void 0);
    };
    const timeout = setTimeout(() => {
      finish(
        `Capture timed out after ${Math.round(CAPTURE_TIMEOUT_MS / 1e3)}s. Try capturing from the article page (not a link), or retry.`
      );
    }, CAPTURE_TIMEOUT_MS);
    pendingBackgroundTabs.set(tabId, timeout);
    const injectAndClose = async () => {
      try {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["contentScript.js"]
        });
        await finish();
      } catch (err) {
        await finish(err?.message ? `Capture failed: ${err.message}` : "Capture failed.");
      }
    };
    const listener = async (updatedTabId, changeInfo) => {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      await injectAndClose();
    };
    listenerRef = listener;
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((t) => {
      if (t.status === "complete") {
        injectAndClose();
      }
    });
  }
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "ARTICLE_SCRAPED") {
      const article = {
        ...message.payload,
        scrapedAt: (/* @__PURE__ */ new Date()).toISOString()
      };
      void (async () => {
        await enqueueArticle(article);
        if (sending) return;
        sending = true;
        try {
          await sendPendingLoop();
        } finally {
          sending = false;
        }
      })();
      const tabId = sender?.tab?.id;
      if (typeof tabId === "number" && pendingBackgroundTabs.has(tabId)) {
        const timeoutId = pendingBackgroundTabs.get(tabId);
        if (timeoutId) clearTimeout(timeoutId);
        pendingBackgroundTabs.delete(tabId);
        chrome.tabs.remove(tabId).catch(() => void 0);
      }
      sendResponse({ status: "stored" });
      return true;
    }
    if (message?.type === "GET_LATEST_ARTICLE") {
      chrome.storage.local.get(["latestArticle", "lastSendStatus", "pendingArticles"]).then((data) => {
        sendResponse({
          article: data.latestArticle,
          sendStatus: data.lastSendStatus,
          pendingCount: Array.isArray(data.pendingArticles) ? data.pendingArticles.length : 0
        });
      });
      return true;
    }
    if (message?.type === "SEND_TO_INGEST") {
      if (sending) {
        sendResponse({ status: "error", error: "Send already in progress." });
        return true;
      }
      sending = true;
      void (async () => {
        try {
          const result = await sendLatestOnce();
          sendResponse(result);
        } finally {
          sending = false;
        }
      })();
      return true;
    }
    return void 0;
  });
})();
//# sourceMappingURL=background.js.map
