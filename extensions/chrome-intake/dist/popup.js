"use strict";
(() => {
  // src/popup.ts
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  function setStatus(text, color = "inherit") {
    const el = document.getElementById("status");
    if (el) {
      el.textContent = text;
      el.style.color = color;
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
      setStatus("Ready to send.");
    });
  }
  function bindSend() {
    const btn = document.getElementById("send");
    if (!btn) return;
    btn.addEventListener("click", () => {
      setStatus("Sending...");
      chrome.runtime.sendMessage({ type: "SEND_TO_INGEST" }, (resp) => {
        if (resp?.status === "ok") {
          setStatus("Stored!", "green");
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
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "CAPTURE_FAILED") {
      setStatus(message.reason || "Capture failed.", "red");
    }
  });
})();
//# sourceMappingURL=popup.js.map
