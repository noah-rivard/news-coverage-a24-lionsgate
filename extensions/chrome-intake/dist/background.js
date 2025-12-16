"use strict";
(() => {
  // src/background.ts
  var DEFAULT_ENDPOINT = "http://localhost:8000/ingest/article";
  var CONTEXT_MENU_ID = "capture-article";
  var CAPTURE_TIMEOUT_MS = 2e4;
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
  async function getEndpoint() {
    const { ingestEndpoint } = await chrome.storage.sync.get({
      ingestEndpoint: DEFAULT_ENDPOINT
    });
    return ingestEndpoint || DEFAULT_ENDPOINT;
  }
  async function ensureHostPermissionForUrl(rawUrl) {
    try {
      const u = new URL(rawUrl);
      const originPattern = `${u.protocol}//${u.host}/*`;
      const alreadyGranted = await chrome.permissions.contains({ origins: [originPattern] });
      if (alreadyGranted) return true;
      return await chrome.permissions.request({ origins: [originPattern] });
    } catch (err) {
      console.warn("ensureHostPermissionForUrl: invalid url", rawUrl, err);
      return false;
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
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "ARTICLE_SCRAPED") {
      const article = {
        ...message.payload,
        scrapedAt: (/* @__PURE__ */ new Date()).toISOString()
      };
      chrome.storage.local.set({ latestArticle: article });
      sendResponse({ status: "stored" });
      return true;
    }
    if (message?.type === "GET_LATEST_ARTICLE") {
      chrome.storage.local.get("latestArticle").then((data) => {
        sendResponse({ article: data.latestArticle });
      });
      return true;
    }
    if (message?.type === "SEND_TO_INGEST") {
      chrome.storage.local.get("latestArticle").then(async (data) => {
        const article = data.latestArticle;
        if (!article) {
          sendResponse({ status: "error", error: "No article scraped yet." });
          return;
        }
        const endpoint = await getEndpoint();
        try {
          const body = {
            company: "Unknown",
            quarter: deriveQuarter(article.published_at, article.scrapedAt),
            section: "Strategy & Miscellaneous News",
            subheading: "General News & Strategy",
            title: article.title,
            source: article.source || "Unknown",
            url: article.url,
            published_at: resolvePublishedDate(article.published_at, article.scrapedAt),
            body: article.content || "",
            ingest_source: "chrome_extension"
          };
          const resp = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          if (!resp.ok) {
            const detail = await resp.text();
            sendResponse({
              status: "error",
              error: `Ingest failed: ${resp.status} ${detail}`
            });
            return;
          }
          sendResponse({ status: "ok" });
        } catch (err) {
          sendResponse({ status: "error", error: err?.message || String(err) });
        }
      });
      return true;
    }
    return void 0;
  });
  chrome.contextMenus.onClicked.addListener((info, tab) => {
    (async () => {
      if (info.menuItemId !== CONTEXT_MENU_ID || !tab?.id) {
        return;
      }
      const frameUrl = info.frameUrl;
      const targetUrl = info.linkUrl || frameUrl || info.pageUrl || tab.url;
      if (!targetUrl) {
        console.warn("No target URL available for capture.");
        notifyCaptureFailure("No URL available to capture.");
        return;
      }
      const useBackgroundTab = Boolean(info.linkUrl);
      const permissionTarget = useBackgroundTab ? targetUrl : frameUrl || targetUrl;
      const granted = await ensureHostPermissionForUrl(permissionTarget);
      if (!granted) {
        console.warn("Capture cancelled: site permission was denied for", permissionTarget);
        notifyCaptureFailure("Site permission was denied.");
        return;
      }
      if (useBackgroundTab) {
        captureInBackgroundTab(targetUrl);
        return;
      }
      const frameId = typeof info.frameId === "number" ? info.frameId : 0;
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id, frameIds: [frameId] },
          files: ["contentScript.js"]
        });
      } catch (err) {
        const message = err?.message || String(err);
        console.warn("Failed to inject content script into frame", permissionTarget, message);
        notifyCaptureFailure("Could not access the embedded article. Please grant frame permission and try again.");
      }
    })().catch((err) => {
      console.warn("Unexpected error handling capture click", err);
      notifyCaptureFailure("Capture failed unexpectedly. Please try again.");
    });
  });
  async function captureInBackgroundTab(url) {
    const tab = await chrome.tabs.create({ url, active: false });
    const tabId = tab.id;
    if (!tabId) return;
    const timeout = setTimeout(() => {
      chrome.tabs.remove(tabId).catch(() => void 0);
    }, CAPTURE_TIMEOUT_MS);
    const injectAndClose = async () => {
      try {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["contentScript.js"]
        });
      } finally {
        clearTimeout(timeout);
        chrome.tabs.remove(tabId).catch(() => void 0);
      }
    };
    const listener = async (updatedTabId, changeInfo) => {
      if (updatedTabId !== tabId || changeInfo.status !== "complete") return;
      chrome.tabs.onUpdated.removeListener(listener);
      await injectAndClose();
    };
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((t) => {
      if (t.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        injectAndClose();
      }
    });
  }
})();
//# sourceMappingURL=background.js.map
