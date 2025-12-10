import { Readability } from "@mozilla/readability";

function getSource(): string {
  const meta =
    document.querySelector("meta[property='og:site_name']") ||
    document.querySelector("meta[name='application-name']");
  return (meta && meta.getAttribute("content")) || window.location.hostname || "Unknown";
}

function getPublished(): string | undefined {
  const candidates = [
    "meta[property='article:published_time']",
    "meta[name='pubdate']",
    "meta[name='date']",
    "time[datetime]",
  ];
  for (const sel of candidates) {
    const el = document.querySelector(sel);
    const val = el?.getAttribute("content") || el?.getAttribute("datetime") || el?.textContent;
    if (val && val.trim()) return val.trim();
  }
  return undefined;
}

function getContent(): string | undefined {
  try {
    const clone = document.cloneNode(true) as Document;
    const article = new Readability(clone).parse();
    return article?.textContent || undefined;
  } catch {
    return undefined;
  }
}

function scrapeArticle() {
  const payload = {
    title: document.title || "",
    source: getSource(),
    url: window.location.href,
    published_at: getPublished(),
    content: getContent(),
  };

  chrome.runtime.sendMessage({ type: "ARTICLE_SCRAPED", payload });
}

scrapeArticle();
