const endpointInput = document.getElementById("endpoint") as HTMLInputElement | null;
const statusEl = document.getElementById("status");
const linksMetaEl = document.getElementById("links_meta");

function setStatus(text: string, color = "inherit") {
  if (statusEl) {
    statusEl.textContent = text;
    (statusEl as HTMLElement).style.color = color;
  }
}

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

function openUrl(url: string) {
  chrome.tabs.create({ url }).catch(() => undefined);
}

function setDisabled(id: string, disabled: boolean) {
  const el = document.getElementById(id) as HTMLButtonElement | null;
  if (el) el.disabled = disabled;
}

function bindOpen(id: string, urlProvider: () => string | null) {
  const el = document.getElementById(id);
  if (!el) return;
  (el as HTMLButtonElement).onclick = () => {
    const url = urlProvider();
    if (url && isHttpUrl(url)) openUrl(url);
  };
}

function renderLinks(endpoint: string) {
  const serverBase = deriveServerBase(endpoint);
  if (linksMetaEl) {
    linksMetaEl.textContent = serverBase
      ? `Endpoint: ${endpoint}\nServer base: ${serverBase}`
      : `Endpoint: ${endpoint}`;
  }
  setDisabled("open_review", !serverBase);
  setDisabled("open_health", !serverBase);
  setDisabled("open_process_articles", !serverBase);
  setDisabled("open_ingest_article", !serverBase);

  bindOpen("open_endpoint", () => endpoint);
  bindOpen("open_openai_logs", () => "https://platform.openai.com/logs?api=responses");
  bindOpen("open_review", () => (serverBase ? joinUrl(serverBase, "/review") : null));
  bindOpen("open_health", () => (serverBase ? joinUrl(serverBase, "/health") : null));
  bindOpen(
    "open_process_articles",
    () => (serverBase ? joinUrl(serverBase, "/process/articles") : null),
  );
  bindOpen(
    "open_ingest_article",
    () => (serverBase ? joinUrl(serverBase, "/ingest/article") : null),
  );
}

async function loadSettings() {
  const { ingestEndpoint } = await chrome.storage.sync.get({
    ingestEndpoint: "http://localhost:8000/process/articles",
  });
  if (endpointInput) endpointInput.value = ingestEndpoint;
  renderLinks((ingestEndpoint || "").trim() || "http://localhost:8000/process/articles");
}

async function saveSettings() {
  if (!endpointInput) return;
  const value = endpointInput.value.trim();
  await chrome.storage.sync.set({ ingestEndpoint: value });
  setStatus("Saved.", "green");
  renderLinks(value || "http://localhost:8000/process/articles");
}

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  const saveBtn = document.getElementById("save");
  if (saveBtn) {
    saveBtn.addEventListener("click", saveSettings);
  }
});
