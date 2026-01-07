function setText(id: string, text: string) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setStatus(text: string, color = "inherit") {
  const el = document.getElementById("status");
  if (el) {
    el.textContent = text;
    el.style.color = color;
  }
}

type OpenAIResponseIds = Record<string, string[]>;

function isHttpUrl(raw: string): boolean {
  try {
    const u = new URL(raw);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function deriveServerBase(endpoint: string): string | null {
  if (!isHttpUrl(endpoint)) return null;
  const u = new URL(endpoint);
  const suffixes = ["/process/articles", "/process/article", "/ingest/article"];
  let basePath = u.pathname;
  for (const suffix of suffixes) {
    if (basePath.endsWith(suffix)) {
      basePath = basePath.slice(0, -suffix.length);
      break;
    }
  }
  basePath = basePath.replace(/\/+$/, "");
  return u.origin + basePath;
}

function joinUrl(base: string, path: string): string {
  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

async function getEndpoint(): Promise<string> {
  const { ingestEndpoint } = await chrome.storage.sync.get({
    ingestEndpoint: "http://localhost:8000/process/articles",
  });
  return (ingestEndpoint || "").trim() || "http://localhost:8000/process/articles";
}

function openUrl(url: string) {
  chrome.tabs.create({ url }).catch(() => undefined);
}

function formatOpenAIResponseIds(ids?: OpenAIResponseIds): string {
  if (!ids) return "";
  const keys = Object.keys(ids).sort();
  const parts: string[] = [];
  for (const key of keys) {
    const values = Array.isArray(ids[key]) ? ids[key] : [];
    if (values.length) {
      parts.push(`${key}: ${values.join(", ")}`);
    }
  }
  return parts.join("\n");
}

function renderSendStatus(
  status?: { status: string; error?: string; duplicate_of?: string; openai_response_ids?: OpenAIResponseIds },
) {
  if (!status) return;
  setText("openai_response_ids", formatOpenAIResponseIds(status.openai_response_ids));
  if (status.status === "ok") {
    setStatus("Auto-sent to pipeline.", "green");
  } else if (status.status === "duplicate") {
    setStatus("Already processed (duplicate).", "orange");
  } else if (status.status === "error") {
    setStatus(status.error || "Send failed.", "red");
  }
}

function loadLatest() {
  chrome.runtime.sendMessage({ type: "GET_LATEST_ARTICLE" }, (resp) => {
    const article = resp?.article;
    if (!article) {
      setStatus("No article scraped yet. Right-click a page or link and choose Capture.", "red");
      setText("openai_response_ids", "");
      return;
    }
    setText("title", article.title || "(untitled)");
    setText("source", article.source || "Unknown");
    setText("published", article.published_at || "Unknown");
    renderSendStatus(resp?.sendStatus);
    if (!resp?.sendStatus) {
      setStatus("Ready to send.");
      setText("openai_response_ids", "");
    }
  });
}

async function bindLinks() {
  const endpoint = await getEndpoint();
  const serverBase = deriveServerBase(endpoint);
  const meta = serverBase ? `Endpoint: ${endpoint}\nServer base: ${serverBase}` : `Endpoint: ${endpoint}`;
  setText("links_meta", meta);

  const openEndpointBtn = document.getElementById("open_endpoint");
  if (openEndpointBtn) {
    openEndpointBtn.addEventListener("click", () => {
      if (isHttpUrl(endpoint)) openUrl(endpoint);
    });
  }

  const openOptionsBtn = document.getElementById("open_options");
  if (openOptionsBtn) {
    openOptionsBtn.addEventListener("click", () => {
      chrome.runtime.openOptionsPage().catch(() => undefined);
    });
  }

  const openOpenAiBtn = document.getElementById("open_openai_logs");
  if (openOpenAiBtn) {
    openOpenAiBtn.addEventListener("click", () => {
      openUrl("https://platform.openai.com/logs?api=responses");
    });
  }

  const openReviewBtn = document.getElementById("open_review");
  if (openReviewBtn) {
    openReviewBtn.toggleAttribute("disabled", !serverBase);
    openReviewBtn.addEventListener("click", () => {
      if (serverBase) openUrl(joinUrl(serverBase, "/review"));
    });
  }

  const openHealthBtn = document.getElementById("open_health");
  if (openHealthBtn) {
    openHealthBtn.toggleAttribute("disabled", !serverBase);
    openHealthBtn.addEventListener("click", () => {
      if (serverBase) openUrl(joinUrl(serverBase, "/health"));
    });
  }

  const openProcessArticlesBtn = document.getElementById("open_process_articles");
  if (openProcessArticlesBtn) {
    openProcessArticlesBtn.toggleAttribute("disabled", !serverBase);
    openProcessArticlesBtn.addEventListener("click", () => {
      if (serverBase) openUrl(joinUrl(serverBase, "/process/articles"));
    });
  }
}

function bindSend() {
  const btn = document.getElementById("send");
  if (!btn) return;
  btn.addEventListener("click", () => {
    setStatus("Sending...");
    chrome.runtime.sendMessage({ type: "SEND_TO_INGEST" }, (resp) => {
      if (resp?.status === "ok") {
        setStatus("Stored via pipeline.", "green");
      } else if (resp?.status === "duplicate") {
        setStatus("Already processed (duplicate).", "orange");
      } else {
        setStatus(resp?.error || "Send failed.", "red");
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadLatest();
  bindLinks();
  bindSend();
});

// Listen for background capture failures (e.g., permission denied) and surface them.
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "CAPTURE_FAILED") {
    setStatus(message.reason || "Capture failed.", "red");
  }
  if (message?.type === "SEND_RESULT") {
    renderSendStatus(message);
  }
});
