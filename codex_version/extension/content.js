const BLOCK_ATTR = "data-view-filter-blocked";
const SEEN_ATTR = "data-view-filter-seen";
const MAX_TEXT_LEN = 1500;

function hostnameMatches(hostname, patterns) {
  return patterns.some((pattern) => {
    const cleaned = pattern.toLowerCase().replace(/^\*\./, "");
    return hostname === cleaned || hostname.endsWith(`.${cleaned}`);
  });
}

function buildMatcher(keywords) {
  const lowered = keywords.map((k) => k.toLowerCase());
  return (text) => {
    const body = (text || "").toLowerCase();
    return lowered.some((keyword) => body.includes(keyword));
  };
}

function hideElement(el, hideMode) {
  if (el.getAttribute(BLOCK_ATTR) === "1") return;
  el.setAttribute(BLOCK_ATTR, "1");

  if (hideMode === "remove") {
    el.style.display = "none";
    return;
  }

  el.style.opacity = "0.12";
  el.style.filter = "blur(2px)";
  el.style.pointerEvents = "none";
  el.style.maxHeight = "40px";
  el.style.overflow = "hidden";
}

function candidateContainers() {
  return [
    "article",
    "[role='article']",
    "[data-testid='tweet']",
    ".Post",
    ".thing",
    "ytd-rich-item-renderer",
    ".comment",
    ".feed-item"
  ];
}

function collectCandidates(root = document) {
  const selector = candidateContainers().join(",");
  return [...root.querySelectorAll(selector)];
}

function compactText(text) {
  return (text || "").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT_LEN);
}

async function runAgentDecision(settings, text) {
  const payload = {
    content: text,
    page_url: location.href,
    page_title: document.title,
    system_prompt: settings.systemPrompt,
    preferences: settings.userPreferences || [],
    provider: settings.agentProvider || "openai",
    provider_model: settings.agentModel || "gpt-4.1-mini",
    provider_base_url: settings.agentBaseUrl || "",
    api_keys: {
      openai: settings.openaiApiKey || "",
      gemini: settings.geminiApiKey || "",
      groq: settings.groqApiKey || "",
      ollama: settings.ollamaApiKey || ""
    }
  };

  const response = await chrome.runtime.sendMessage({
    type: "RUN_AGENT_FILTER",
    endpoint: settings.agentEndpoint,
    timeoutMs: settings.agentTimeoutMs || 3500,
    payload
  });
  if (!response?.ok) {
    throw new Error(response?.error || "agent unavailable");
  }

  const data = response.data || {};
  return {
    hide: Boolean(data.hide),
    reason: data.reason || "",
    confidence: Number(data.confidence || 0)
  };
}

async function filterDocument(settings) {
  if (!settings?.enabled) return;

  const hostname = location.hostname.toLowerCase();
  const allowed = hostnameMatches(hostname, settings.siteAllowlist || []);
  if (!allowed) return;

  const matchesBlocked = buildMatcher(settings.blockedKeywords || []);
  const nodes = collectCandidates();

  for (const node of nodes) {
    if (node.getAttribute(BLOCK_ATTR) === "1") continue;
    if (node.getAttribute(SEEN_ATTR) === "1") continue;
    node.setAttribute(SEEN_ATTR, "1");

    const text = compactText(node.innerText || node.textContent || "");
    if (!text) continue;

    // Cheap local fallback catches obvious content without API calls.
    if (matchesBlocked(text)) {
      hideElement(node, settings.hideMode || "collapse");
      continue;
    }

    if (!settings.useAgent || !settings.agentEndpoint) continue;

    try {
      const verdict = await runAgentDecision(settings, text);
      if (verdict.hide) {
        hideElement(node, settings.hideMode || "collapse");
        if (verdict.reason) {
          node.title = `Filtered: ${verdict.reason}`;
        }
      }
    } catch {
      // Keep content visible on agent failures.
    }
  }
}

async function getSettings() {
  try {
    const response = await chrome.runtime.sendMessage({ type: "GET_SETTINGS" });
    return response?.settings;
  } catch {
    return null;
  }
}

(async () => {
  let settings = await getSettings();
  await filterDocument(settings);

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync" || !changes.filterSettings) return;
    settings = changes.filterSettings.newValue;
  });

  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type !== "childList" || !record.addedNodes.length) continue;
      filterDocument(settings);
      break;
    }
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
