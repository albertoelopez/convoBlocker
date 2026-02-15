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
  agentBaseUrl: "",
  openaiApiKey: "",
  geminiApiKey: "",
  groqApiKey: "",
  ollamaApiKey: ""
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

const providerDefaults = {
  openai: { model: "gpt-4.1-mini", baseUrl: "" },
  gemini: { model: "gemini-2.5-flash", baseUrl: "" },
  groq: { model: "llama-3.3-70b-versatile", baseUrl: "" },
  ollama: { model: "llama3.1:8b", baseUrl: "http://127.0.0.1:11434/v1" }
};

function applyProviderDefaults() {
  const provider = document.getElementById("agentProvider").value;
  const defaults = providerDefaults[provider];
  if (!defaults) return;

  const modelInput = document.getElementById("agentModel");
  const baseUrlInput = document.getElementById("agentBaseUrl");
  const ollamaKeyInput = document.getElementById("ollamaApiKey");

  if (!modelInput.value.trim()) {
    modelInput.value = defaults.model;
  }
  if (!baseUrlInput.value.trim()) {
    baseUrlInput.value = defaults.baseUrl;
  }
  if (provider === "ollama" && !ollamaKeyInput.value.trim()) {
    ollamaKeyInput.value = "ollama";
  }
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
  document.getElementById("openaiApiKey").value = settings.openaiApiKey;
  document.getElementById("geminiApiKey").value = settings.geminiApiKey;
  document.getElementById("groqApiKey").value = settings.groqApiKey;
  document.getElementById("ollamaApiKey").value = settings.ollamaApiKey;
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
    openaiApiKey: document.getElementById("openaiApiKey").value.trim(),
    geminiApiKey: document.getElementById("geminiApiKey").value.trim(),
    groqApiKey: document.getElementById("groqApiKey").value.trim(),
    ollamaApiKey: document.getElementById("ollamaApiKey").value.trim(),
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
document.getElementById("agentProvider").addEventListener("change", applyProviderDefaults);
loadSettings();
