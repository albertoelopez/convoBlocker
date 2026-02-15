const defaults = {
  enabled: true,
  blockedKeywords: [],
  siteAllowlist: [],
  hideMode: "collapse",
  systemPrompt: "",
  userPreferences: [],
  agentEndpoint: "http://127.0.0.1:8000/filter",
  agentTimeoutMs: 3500,
  useAgent: true,
  agentProvider: "openai",
  agentModel: "gpt-4.1-mini",
  agentBaseUrl: ""
};

function toLines(arr = []) {
  return arr.join("\n");
}

function fromLines(text = "") {
  return text
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
}

async function loadSettings() {
  const { filterSettings } = await chrome.storage.sync.get("filterSettings");
  const settings = { ...defaults, ...(filterSettings || {}) };

  document.getElementById("enabled").checked = settings.enabled;
  document.getElementById("blockedKeywords").value = toLines(settings.blockedKeywords);
  document.getElementById("useAgent").checked = settings.useAgent;
  document.getElementById("agentEndpoint").value = settings.agentEndpoint;
  document.getElementById("agentProvider").value = settings.agentProvider;
  document.getElementById("agentModel").value = settings.agentModel;
  document.getElementById("agentBaseUrl").value = settings.agentBaseUrl;
  document.getElementById("agentTimeoutMs").value = settings.agentTimeoutMs;
  document.getElementById("systemPrompt").value = settings.systemPrompt;
  document.getElementById("userPreferences").value = toLines(settings.userPreferences);
  document.getElementById("siteAllowlist").value = toLines(settings.siteAllowlist);
  document.getElementById("hideMode").value = settings.hideMode;
}

async function saveSettings() {
  const settings = {
    enabled: document.getElementById("enabled").checked,
    blockedKeywords: fromLines(document.getElementById("blockedKeywords").value),
    useAgent: document.getElementById("useAgent").checked,
    agentEndpoint: document.getElementById("agentEndpoint").value.trim(),
    agentProvider: document.getElementById("agentProvider").value,
    agentModel: document.getElementById("agentModel").value.trim(),
    agentBaseUrl: document.getElementById("agentBaseUrl").value.trim(),
    agentTimeoutMs: Number(document.getElementById("agentTimeoutMs").value) || 3500,
    systemPrompt: document.getElementById("systemPrompt").value.trim(),
    userPreferences: fromLines(document.getElementById("userPreferences").value),
    siteAllowlist: fromLines(document.getElementById("siteAllowlist").value),
    hideMode: document.getElementById("hideMode").value
  };

  await chrome.storage.sync.set({ filterSettings: settings });
  const status = document.getElementById("status");
  status.textContent = "Saved.";
  setTimeout(() => {
    status.textContent = "";
  }, 1000);
}

document.getElementById("saveBtn").addEventListener("click", saveSettings);
loadSettings();
