"use strict";
(() => {
  // src/background.ts
  var DEFAULT_ENDPOINT = "http://localhost:8000/ingest/article";
  var CONTEXT_MENU_ID = "capture-article";
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
  function ensureContextMenu() {
    chrome.contextMenus.create(
      {
        id: CONTEXT_MENU_ID,
        title: "Capture article for ingest",
        contexts: ["page", "frame"]
      },
      () => {
        const err = chrome.runtime.lastError;
        if (err && !err.message.includes("duplicate id")) {
          console.warn("Failed to create context menu", err.message);
        }
      }
    );
  }
  ensureContextMenu();
  chrome.runtime.onInstalled.addListener(ensureContextMenu);
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
    if (info.menuItemId !== CONTEXT_MENU_ID || !tab?.id) {
      return;
    }
    const frameId = typeof info.frameId === "number" ? info.frameId : 0;
    chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [frameId] },
      files: ["contentScript.js"]
    });
  });
})();
//# sourceMappingURL=background.js.map
