const DEFAULT_SETTINGS = {
  enabled: true,
  blockedKeywords: ["flat earth", "scam crypto", "hate speech"],
  siteAllowlist: ["x.com", "twitter.com", "reddit.com", "youtube.com"],
  hideMode: "collapse",
  systemPrompt:
    "You are a strict personal feed-filtering agent. Decide if content should be hidden based on user preferences.",
  userPreferences: [
    "Hide rage bait and low-signal arguments.",
    "Hide personal attacks or dehumanizing language.",
    "Hide repetitive conspiracy or misinformation talking points."
  ],
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

chrome.runtime.onInstalled.addListener(async () => {
  const { filterSettings } = await chrome.storage.sync.get("filterSettings");
  if (!filterSettings) {
    await chrome.storage.sync.set({ filterSettings: DEFAULT_SETTINGS });
    return;
  }

  const merged = { ...DEFAULT_SETTINGS, ...filterSettings };
  await chrome.storage.sync.set({ filterSettings: merged });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "GET_SETTINGS") {
    chrome.storage.sync.get("filterSettings").then(({ filterSettings }) => {
      sendResponse({ settings: filterSettings || DEFAULT_SETTINGS });
    });
    return true;
  }

  if (msg?.type === "SAVE_SETTINGS") {
    chrome.storage.sync.set({ filterSettings: msg.settings }).then(() => {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (msg?.type === "RUN_AGENT_FILTER") {
    const timeoutMs = Number(msg.timeoutMs) || 3500;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    fetch(msg.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
      signal: controller.signal
    })
      .then(async (response) => {
        clearTimeout(timer);
        if (!response.ok) {
          sendResponse({ ok: false, error: `agent http ${response.status}` });
          return;
        }
        const data = await response.json();
        sendResponse({ ok: true, data });
      })
      .catch((error) => {
        clearTimeout(timer);
        sendResponse({ ok: false, error: error?.message || "agent request failed" });
      });
    return true;
  }
});
