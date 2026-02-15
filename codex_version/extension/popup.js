async function load() {
  const { filterSettings } = await chrome.storage.sync.get("filterSettings");
  document.getElementById("enabled").checked = filterSettings?.enabled ?? true;
}

async function setEnabled(value) {
  const { filterSettings } = await chrome.storage.sync.get("filterSettings");
  const next = { ...(filterSettings || {}), enabled: value };
  await chrome.storage.sync.set({ filterSettings: next });
}

document.getElementById("enabled").addEventListener("change", (event) => {
  setEnabled(event.target.checked);
});

document.getElementById("openOptions").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

load();
