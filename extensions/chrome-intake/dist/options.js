"use strict";
(() => {
  // src/options.ts
  var endpointInput = document.getElementById("endpoint");
  var statusEl = document.getElementById("status");
  function setStatus(text, color = "inherit") {
    if (statusEl) {
      statusEl.textContent = text;
      statusEl.style.color = color;
    }
  }
  async function loadSettings() {
    const { ingestEndpoint } = await chrome.storage.sync.get({
      ingestEndpoint: "http://localhost:8000/process/article"
    });
    if (endpointInput) endpointInput.value = ingestEndpoint;
  }
  async function saveSettings() {
    if (!endpointInput) return;
    const value = endpointInput.value.trim();
    await chrome.storage.sync.set({ ingestEndpoint: value });
    setStatus("Saved.", "green");
  }
  document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    const saveBtn = document.getElementById("save");
    if (saveBtn) {
      saveBtn.addEventListener("click", saveSettings);
    }
  });
})();
//# sourceMappingURL=options.js.map
