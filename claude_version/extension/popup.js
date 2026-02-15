// YT Live Chat Blocker - Popup Script

(function () {
  "use strict";

  // --- DOM refs ---
  const tabs = document.querySelectorAll(".tab");
  const tabContents = document.querySelectorAll(".tab-content");

  const statusBadge = document.getElementById("status-badge");

  // Categories
  const catSpam = document.getElementById("cat-spam");
  const catTrolls = document.getElementById("cat-trolls");
  const catOffTopic = document.getElementById("cat-off_topic");
  const catHateSpeech = document.getElementById("cat-hate_speech");
  const catSelfPromo = document.getElementById("cat-self_promo");
  const customPrompt = document.getElementById("custom-prompt");

  // Settings
  const aiProvider = document.getElementById("ai-provider");
  const geminiSettings = document.getElementById("gemini-settings");
  const ollamaSettings = document.getElementById("ollama-settings");
  const geminiApiKey = document.getElementById("gemini-api-key");
  const ollamaEndpoint = document.getElementById("ollama-endpoint");
  const ollamaModel = document.getElementById("ollama-model");
  const backendUrl = document.getElementById("backend-url");
  const saveSettingsBtn = document.getElementById("save-settings");
  const settingsStatus = document.getElementById("settings-status");

  // Block log
  const blocklogEmpty = document.getElementById("blocklog-empty");
  const blocklogList = document.getElementById("blocklog-list");

  // Stats
  const statsAnalyzed = document.getElementById("stats-analyzed");
  const statsBlocked = document.getElementById("stats-blocked");

  // --- Tab switching ---
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tabContents.forEach((tc) => tc.classList.remove("active"));

      tab.classList.add("active");
      const targetId = `tab-${tab.dataset.tab}`;
      document.getElementById(targetId).classList.add("active");

      // Refresh block log when switching to that tab
      if (tab.dataset.tab === "blocklog") {
        loadBlockLog();
      }
    });
  });

  // Ollama model UI
  const refreshOllamaBtn = document.getElementById("refresh-ollama-models");
  const ollamaModelStatus = document.getElementById("ollama-model-status");

  // --- Provider toggle ---
  aiProvider.addEventListener("change", () => {
    if (aiProvider.value === "gemini") {
      geminiSettings.style.display = "block";
      ollamaSettings.style.display = "none";
    } else {
      geminiSettings.style.display = "none";
      ollamaSettings.style.display = "block";
      refreshOllamaModels();
    }
  });

  // --- Ollama model discovery ---
  let _pendingOllamaModel = null; // model to select after list loads

  function refreshOllamaModels() {
    const previousValue = ollamaModel.value;
    ollamaModelStatus.textContent = "Loading models...";
    ollamaModelStatus.style.color = "#fff176";
    refreshOllamaBtn.classList.add("spinning");

    chrome.runtime.sendMessage({ type: "GET_OLLAMA_MODELS" }, (response) => {
      refreshOllamaBtn.classList.remove("spinning");

      if (chrome.runtime.lastError) {
        ollamaModelStatus.textContent = "Backend unreachable";
        ollamaModelStatus.style.color = "#ff8a80";
        return;
      }
      if (!response || response.error) {
        const detail = response && response.error ? response.error : "Unknown error";
        ollamaModelStatus.textContent = detail;
        ollamaModelStatus.style.color = "#ff8a80";
        return;
      }

      const models = response.models || [];
      // Clear existing options
      ollamaModel.innerHTML = "";

      if (models.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.disabled = true;
        opt.selected = true;
        opt.textContent = "No models found — run: ollama pull llama3.2";
        ollamaModel.appendChild(opt);
        ollamaModelStatus.textContent = "No models installed";
        ollamaModelStatus.style.color = "#ff8a80";
        return;
      }

      models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.name;
        const sizeStr = m.parameter_size ? ` (${m.parameter_size})` : m.size ? ` (${m.size})` : "";
        opt.textContent = `${m.name}${sizeStr}`;
        ollamaModel.appendChild(opt);
      });

      // Restore selection: prefer pending model, then previous value, then first
      const toSelect = _pendingOllamaModel || previousValue;
      _pendingOllamaModel = null;
      if (toSelect) {
        const exists = Array.from(ollamaModel.options).some((o) => o.value === toSelect);
        if (exists) {
          ollamaModel.value = toSelect;
        }
      }

      ollamaModelStatus.textContent = `${models.length} model${models.length !== 1 ? "s" : ""} found`;
      ollamaModelStatus.style.color = "#69f0ae";
      setTimeout(() => { ollamaModelStatus.textContent = ""; }, 3000);
    });
  }

  refreshOllamaBtn.addEventListener("click", refreshOllamaModels);

  // Also refresh when endpoint field changes (debounced)
  let endpointRefreshTimer = null;
  ollamaEndpoint.addEventListener("input", () => {
    if (endpointRefreshTimer) clearTimeout(endpointRefreshTimer);
    endpointRefreshTimer = setTimeout(refreshOllamaModels, 1000);
  });

  // --- Auto-save categories on change ---
  const categoryCheckboxes = [catSpam, catTrolls, catOffTopic, catHateSpeech, catSelfPromo];

  function getCategories() {
    return {
      spam: catSpam.checked,
      trolls: catTrolls.checked,
      off_topic: catOffTopic.checked,
      hate_speech: catHateSpeech.checked,
      self_promo: catSelfPromo.checked,
    };
  }

  function saveCategories() {
    const categories = getCategories();
    const prompt = customPrompt.value.trim();

    chrome.storage.local.set({ categories, customPrompt: prompt });

    // Fetch current settings from backend, merge categories/custom_prompt, then POST full settings
    chrome.runtime.sendMessage({ type: "GET_SETTINGS" }, (current) => {
      if (chrome.runtime.lastError || !current || current.error) {
        console.warn("[YT-Blocker] Failed to fetch current settings for merge:", chrome.runtime.lastError);
        return;
      }

      const merged = Object.assign({}, current, {
        categories,
        custom_prompt: prompt,
      });

      chrome.runtime.sendMessage({
        type: "SAVE_SETTINGS",
        settings: merged,
      });
    });
  }

  categoryCheckboxes.forEach((cb) => {
    cb.addEventListener("change", saveCategories);
  });

  let promptSaveTimer = null;
  customPrompt.addEventListener("input", () => {
    if (promptSaveTimer) clearTimeout(promptSaveTimer);
    promptSaveTimer = setTimeout(saveCategories, 800);
  });

  // --- Show/hide API key toggle ---
  const toggleGeminiKey = document.getElementById("toggle-gemini-key");
  if (toggleGeminiKey) {
    toggleGeminiKey.addEventListener("click", () => {
      const isPassword = geminiApiKey.type === "password";
      geminiApiKey.type = isPassword ? "text" : "password";
      toggleGeminiKey.title = isPassword ? "Hide key" : "Show key";
    });
  }

  // --- Open Gemini link in new tab ---
  const geminiLink = document.getElementById("gemini-link");
  if (geminiLink) {
    geminiLink.addEventListener("click", (e) => {
      e.preventDefault();
      chrome.tabs.create({ url: "https://aistudio.google.com/apikey" });
    });
  }

  // --- Save settings button ---
  saveSettingsBtn.addEventListener("click", async () => {
    const localBackendUrl = backendUrl.value.trim();

    // Save backendUrl only to local storage (not a backend field)
    chrome.storage.local.set({
      settings: {
        ai_provider: aiProvider.value,
        gemini_api_key: geminiApiKey.value.trim(),
        ollama_endpoint: ollamaEndpoint.value.trim(),
        ollama_model: ollamaModel.value.trim(),
        backendUrl: localBackendUrl,
      },
    });

    // Fetch current backend settings, merge in AI fields, then POST
    try {
      const current = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "GET_SETTINGS" }, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else if (response && response.error) {
            reject(new Error(response.error));
          } else {
            resolve(response || {});
          }
        });
      });

      const merged = Object.assign({}, current, {
        ai_provider: aiProvider.value,
        gemini_api_key: geminiApiKey.value.trim(),
        ollama_endpoint: ollamaEndpoint.value.trim(),
        ollama_model: ollamaModel.value.trim(),
      });
      // Remove backendUrl if it leaked in — not a backend field
      delete merged.backendUrl;

      await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          { type: "SAVE_SETTINGS", settings: merged },
          (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (response && response.error) {
              reject(new Error(response.error));
            } else {
              resolve(response);
            }
          }
        );
      });

      showSettingsStatus("Settings saved!", "success");

      // Re-check backend health
      chrome.runtime.sendMessage({ type: "HEALTH_CHECK" });
      setTimeout(checkHealth, 1500);
    } catch (err) {
      showSettingsStatus(`Save failed: ${err.message}`, "error");
    }
  });

  function showSettingsStatus(text, type) {
    settingsStatus.textContent = text;
    settingsStatus.className = `settings-status ${type}`;
    setTimeout(() => {
      settingsStatus.textContent = "";
      settingsStatus.className = "settings-status";
    }, 3000);
  }

  // --- Load saved state ---
  async function loadSavedState() {
    try {
      const result = await chrome.storage.local.get(["categories", "customPrompt", "settings"]);

      if (result.categories) {
        catSpam.checked = result.categories.spam !== false;
        catTrolls.checked = result.categories.trolls !== false;
        catOffTopic.checked = result.categories.off_topic === true;
        catHateSpeech.checked = result.categories.hate_speech !== false;
        catSelfPromo.checked = result.categories.self_promo === true;
      }

      if (result.customPrompt) {
        customPrompt.value = result.customPrompt;
      }

      if (result.settings) {
        if (result.settings.ai_provider) {
          aiProvider.value = result.settings.ai_provider;
          aiProvider.dispatchEvent(new Event("change"));
        }
        if (result.settings.gemini_api_key) {
          geminiApiKey.value = result.settings.gemini_api_key;
        }
        if (result.settings.ollama_endpoint) {
          ollamaEndpoint.value = result.settings.ollama_endpoint;
        }
        if (result.settings.ollama_model) {
          _pendingOllamaModel = result.settings.ollama_model;
        }
        if (result.settings.backendUrl) {
          backendUrl.value = result.settings.backendUrl;
        }
      }
    } catch (err) {
      console.warn("[YT-Blocker] Failed to load saved state:", err);
    }
  }

  // --- Health check ---
  function checkHealth() {
    chrome.runtime.sendMessage({ type: "HEALTH_CHECK" }, () => {
      // Read badge to determine status
      chrome.action.getBadgeText({}, (text) => {
        if (text === "ON") {
          statusBadge.textContent = "Online";
          statusBadge.className = "status-badge status-online";
        } else {
          statusBadge.textContent = "Offline";
          statusBadge.className = "status-badge status-offline";
        }
      });
    });

    // Fallback: read badge after delay
    setTimeout(() => {
      chrome.action.getBadgeText({}, (text) => {
        if (text === "ON") {
          statusBadge.textContent = "Online";
          statusBadge.className = "status-badge status-online";
        } else if (text === "OFF") {
          statusBadge.textContent = "Offline";
          statusBadge.className = "status-badge status-offline";
        }
      });
    }, 2000);
  }

  // --- Load stats ---
  function loadStats() {
    chrome.runtime.sendMessage({ type: "GET_STATS" }, (response) => {
      if (chrome.runtime.lastError || !response) return;
      if (response.error) return;

      statsAnalyzed.textContent = `${response.messages_analyzed || 0} analyzed`;
      statsBlocked.textContent = `${response.users_blocked || 0} blocked`;
    });
  }

  // --- Load block log ---
  function loadBlockLog() {
    chrome.runtime.sendMessage({ type: "GET_BLOCK_LOG" }, (response) => {
      if (chrome.runtime.lastError || !response) return;
      if (response.error) return;

      const entries = Array.isArray(response) ? response : (response.entries || response.log || []);

      if (entries.length === 0) {
        blocklogEmpty.style.display = "block";
        blocklogList.innerHTML = "";
        return;
      }

      blocklogEmpty.style.display = "none";
      blocklogList.innerHTML = "";

      // Show most recent first
      const sorted = entries.slice().reverse();

      for (const entry of sorted) {
        const el = document.createElement("div");
        el.className = "blocklog-entry";

        const timeStr = entry.timestamp
          ? new Date(entry.timestamp).toLocaleTimeString()
          : "";

        el.innerHTML = `
          <div class="blocklog-info">
            <div class="blocklog-username">${escapeHtml(entry.username)}</div>
            <div class="blocklog-meta">${escapeHtml(entry.reason || "")}${timeStr ? " &middot; " + timeStr : ""}</div>
          </div>
          <button class="btn btn-sm btn-ghost unblock-btn" data-username="${escapeAttr(entry.username)}">Unblock</button>
        `;

        blocklogList.appendChild(el);
      }

      // Unblock button handlers
      blocklogList.querySelectorAll(".unblock-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const username = btn.dataset.username;
          chrome.runtime.sendMessage({ type: "UNBLOCK_USER", username }, () => {
            loadBlockLog();
          });
        });
      });
    });
  }

  // --- Helpers ---
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return str.replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // --- Init ---
  loadSavedState().then(() => {
    // If Ollama is selected, fetch models after state is loaded
    if (aiProvider.value === "ollama") {
      refreshOllamaModels();
    }
  });
  checkHealth();
  loadStats();
})();
