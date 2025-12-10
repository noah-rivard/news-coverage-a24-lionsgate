import { Readability } from "@mozilla/readability";

function getSource(): string {
  const meta =
    document.querySelector("meta[property='og:site_name']") ||
    document.querySelector("meta[name='application-name']");
  return (meta && meta.getAttribute("content")) || window.location.hostname || "Unknown";
}

function normalizePublishedDate(raw?: string | null): string | undefined {
  if (!raw) return undefined;
  const trimmed = raw.trim();

  const dateMatch = trimmed.match(/(\d{4}-\d{2}-\d{2})/);
  if (dateMatch) return dateMatch[1];

  const parsed = Date.parse(trimmed);
  if (Number.isNaN(parsed)) return undefined;

  return new Date(parsed).toISOString().slice(0, 10);
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
    const normalized = normalizePublishedDate(val);
    if (normalized) return normalized;
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
