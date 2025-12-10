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
          quarter: deriveQuarter(article.published_at, article.scrapedAt),
          section: "Strategy & Miscellaneous News",
          subheading: "General News & Strategy",
          title: article.title,
          source: article.source || "Unknown",
          url: article.url,
          published_at: resolvePublishedDate(article.published_at, article.scrapedAt),
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
