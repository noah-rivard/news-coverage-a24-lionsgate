const endpointInput = document.getElementById("endpoint") as HTMLInputElement | null;
const statusEl = document.getElementById("status");

function setStatus(text: string, color = "inherit") {
  if (statusEl) {
    statusEl.textContent = text;
    (statusEl as HTMLElement).style.color = color;
  }
}

async function loadSettings() {
  const { ingestEndpoint } = await chrome.storage.sync.get({
    ingestEndpoint: "http://localhost:8000/process/article",
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
