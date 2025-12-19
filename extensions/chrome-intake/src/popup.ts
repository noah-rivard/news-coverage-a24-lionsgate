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

function renderSendStatus(status?: { status: string; error?: string; duplicate_of?: string }) {
  if (!status) return;
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
      return;
    }
    setText("title", article.title || "(untitled)");
    setText("source", article.source || "Unknown");
    setText("published", article.published_at || "Unknown");
    renderSendStatus(resp?.sendStatus);
    if (!resp?.sendStatus) {
      setStatus("Ready to send.");
    }
  });
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
