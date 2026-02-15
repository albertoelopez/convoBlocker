// YT Live Chat Blocker - Background Service Worker

const DEFAULT_BACKEND_URL = "http://localhost:8000";

// --- Helpers ---
async function getBackendUrl() {
  try {
    const result = await chrome.storage.local.get("settings");
    return (result.settings && result.settings.backendUrl) || DEFAULT_BACKEND_URL;
  } catch {
    return DEFAULT_BACKEND_URL;
  }
}

async function fetchWithRetry(url, options, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      if (attempt === retries) throw err;
      await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
    }
  }
}

// --- Health check on startup ---
async function checkBackendHealth() {
  const backendUrl = await getBackendUrl();
  try {
    const response = await fetch(`${backendUrl}/health`, { method: "GET" });
    if (response.ok) {
      chrome.action.setBadgeText({ text: "ON" });
      chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
      console.log("[YT-Blocker] Backend is reachable.");
    } else {
      throw new Error("Not OK");
    }
  } catch {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#F44336" });
    console.warn("[YT-Blocker] Backend is unreachable.");
  }
}

chrome.runtime.onInstalled.addListener(() => {
  checkBackendHealth();
});

chrome.runtime.onStartup.addListener(() => {
  checkBackendHealth();
});

// Also check on service worker activation
checkBackendHealth();

// --- Message handler ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message)
    .then(sendResponse)
    .catch((err) => {
      console.error("[YT-Blocker] Message handler error:", err);
      sendResponse({ error: err.message });
    });

  return true; // Keep the message channel open for async response
});

async function handleMessage(message) {
  const backendUrl = await getBackendUrl();

  switch (message.type) {
    case "ANALYZE_BATCH":
      return await analyzeBatch(backendUrl, message.messages);

    case "GET_STATS":
      return await fetchWithRetry(`${backendUrl}/stats`);

    case "GET_BLOCK_LOG":
      return await fetchWithRetry(`${backendUrl}/block-log`);

    case "SAVE_SETTINGS":
      return await fetchWithRetry(`${backendUrl}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(message.settings),
      });

    case "GET_SETTINGS":
      return await fetchWithRetry(`${backendUrl}/settings`);

    case "USER_BLOCKED":
      // Block decisions are already stored server-side by the /analyze endpoint
      return { ok: true };

    case "HEALTH_CHECK":
      await checkBackendHealth();
      return { ok: true };

    case "UNBLOCK_USER":
      return await fetchWithRetry(`${backendUrl}/unblock/${encodeURIComponent(message.username)}`, {
        method: "POST",
      });

    default:
      return { error: "Unknown message type" };
  }
}

async function analyzeBatch(backendUrl, messages) {
  try {
    const result = await fetchWithRetry(`${backendUrl}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    return result;
  } catch (err) {
    console.error("[YT-Blocker] Analyze batch failed:", err);
    // Return no-block decisions on failure so chat isn't disrupted
    return {
      decisions: messages.map((m) => ({
        username: m.username,
        block: false,
        reason: "analysis_error",
      })),
    };
  }
}

