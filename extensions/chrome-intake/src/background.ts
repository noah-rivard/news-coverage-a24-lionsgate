// Service worker: stores the latest scraped article and sends to ingest API.

const DEFAULT_ENDPOINT = "http://localhost:8000/ingest/article";

type ArticlePayload = {
  title: string;
  source: string;
  url: string;
  published_at?: string;
  content?: string;
};

type StoredArticle = ArticlePayload & { scrapedAt: string };

async function getEndpoint(): Promise<string> {
  const { ingestEndpoint } = await chrome.storage.sync.get({
    ingestEndpoint: DEFAULT_ENDPOINT,
  });
  return ingestEndpoint || DEFAULT_ENDPOINT;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "ARTICLE_SCRAPED") {
    const article: StoredArticle = {
      ...message.payload,
      scrapedAt: new Date().toISOString(),
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
      const article: StoredArticle | undefined = data.latestArticle;
      if (!article) {
        sendResponse({ status: "error", error: "No article scraped yet." });
        return;
      }
      const endpoint = await getEndpoint();
      try {
        const body = {
          company: "Unknown",
          quarter: "2025 Q4",
          section: "Strategy & Miscellaneous News",
          subheading: "General News & Strategy",
          title: article.title,
          source: article.source || "Unknown",
          url: article.url,
          published_at: article.published_at || undefined,
          body: article.content || "",
          ingest_source: "chrome_extension",
        };
        const resp = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!resp.ok) {
          const detail = await resp.text();
          sendResponse({
            status: "error",
            error: `Ingest failed: ${resp.status} ${detail}`,
          });
          return;
        }
        sendResponse({ status: "ok" });
      } catch (err: any) {
        sendResponse({ status: "error", error: err?.message || String(err) });
      }
    });
    return true;
  }

  return undefined;
});
