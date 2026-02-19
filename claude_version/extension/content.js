// YT Live Chat Blocker - Content Script
// Injected into YouTube live chat iframe (live_chat* URLs)

(function () {
  "use strict";

  // --- Configuration ---
  const BATCH_FLUSH_INTERVAL = 3000; // 3 seconds
  const BATCH_MAX_SIZE = 15;
  const BLOCK_DELAY = 2000; // 2 seconds between blocks
  const MENU_HOVER_DELAY = 200;
  const SWEEP_INTERVAL = 5000; // 5 seconds between sweeps

  // --- State ---
  const decisionCache = new Map(); // username -> { block: boolean, reason: string }
  const blockedUsers = new Set(); // persistent blocked usernames
  let messageBatch = [];
  let batchTimer = null;
  let blockQueue = [];
  let isProcessingBlockQueue = false;
  let observer = null;
  let sweepTimer = null;

  // --- Persistent blocked users ---
  function loadBlockedUsers() {
    return new Promise((resolve) => {
      chrome.storage.local.get("blockedUsers", (result) => {
        if (!chrome.runtime.lastError) {
          const stored = result.blockedUsers;
          if (Array.isArray(stored)) {
            for (const u of stored) blockedUsers.add(u);
            if (stored.length > 0) {
              console.log(
                `[YT-Blocker] Loaded ${stored.length} blocked users from storage`
              );
            }
          }
        }
        resolve();
      });
    });
  }

  function persistBlockedUsers() {
    chrome.storage.local.set(
      { blockedUsers: Array.from(blockedUsers) },
      () => {
        if (chrome.runtime.lastError) {
          console.warn(
            "[YT-Blocker] Failed to persist blocked users:",
            chrome.runtime.lastError.message
          );
        }
      }
    );
  }

  // --- Utility ---
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function waitForElement(selector, timeout = 10000) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(selector);
      if (existing) {
        resolve(existing);
        return;
      }

      const obs = new MutationObserver(() => {
        const el = document.querySelector(selector);
        if (el) {
          obs.disconnect();
          resolve(el);
        }
      });

      obs.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });

      setTimeout(() => {
        obs.disconnect();
        reject(new Error(`waitForElement timeout: ${selector}`));
      }, timeout);
    });
  }

  // --- Batch message handling ---
  function queueMessage(username, text, messageNode) {
    // Instant hide for known blocked users — no backend round-trip needed
    if (blockedUsers.has(username)) {
      hideMessage(messageNode, username);
      return;
    }

    // Check decision cache
    const cached = decisionCache.get(username);
    if (cached) {
      if (cached.block) {
        enqueueBlock(username, cached.reason, messageNode);
      }
      return; // Skip re-analysis for cached users
    }

    messageBatch.push({ username, text, messageNode });

    if (messageBatch.length >= BATCH_MAX_SIZE) {
      flushBatch();
    } else if (!batchTimer) {
      batchTimer = setTimeout(flushBatch, BATCH_FLUSH_INTERVAL);
    }
  }

  function flushBatch() {
    if (batchTimer) {
      clearTimeout(batchTimer);
      batchTimer = null;
    }

    if (messageBatch.length === 0) return;

    const batch = messageBatch.slice();
    messageBatch = [];

    const payload = batch.map((m) => ({
      username: m.username,
      text: m.text,
    }));

    chrome.runtime.sendMessage(
      { type: "ANALYZE_BATCH", messages: payload },
      (response) => {
        if (chrome.runtime.lastError) {
          console.warn(
            "[YT-Blocker] Failed to send batch:",
            chrome.runtime.lastError.message
          );
          return;
        }

        if (!response || !response.decisions) return;

        for (const decision of response.decisions) {
          decisionCache.set(decision.username, {
            block: decision.decision === "block",
            reason: decision.reason || "",
          });

          if (decision.decision === "block") {
            // Find the corresponding message node from this batch
            const msg = batch.find((m) => m.username === decision.username);
            if (msg && msg.messageNode) {
              enqueueBlock(decision.username, decision.reason, msg.messageNode);
            }
          }
        }
      }
    );
  }

  // --- Block queue ---
  function enqueueBlock(username, reason, messageNode) {
    // Track as blocked immediately and persist
    blockedUsers.add(username);
    persistBlockedUsers();

    blockQueue.push({ username, reason, messageNode });
    if (!isProcessingBlockQueue) {
      processBlockQueue();
    }
  }

  async function processBlockQueue() {
    if (isProcessingBlockQueue) return;
    isProcessingBlockQueue = true;

    while (blockQueue.length > 0) {
      const { username, reason, messageNode } = blockQueue.shift();

      try {
        const success = await performNativeBlock(messageNode, username);
        if (success) {
          chrome.runtime.sendMessage({
            type: "USER_BLOCKED",
            username,
            reason,
          });
          console.log(`[YT-Blocker] Blocked user: ${username} (${reason})`);
        } else {
          // Fallback: hide message
          hideMessage(messageNode, username);
        }
      } catch (err) {
        console.warn(`[YT-Blocker] Block failed for ${username}:`, err);
        hideMessage(messageNode, username);
      }

      if (blockQueue.length > 0) {
        await sleep(BLOCK_DELAY);
      }
    }

    isProcessingBlockQueue = false;
  }

  async function performNativeBlock(messageNode, username) {
    try {
      // Step 1: Hover over message to reveal the menu button
      messageNode.dispatchEvent(
        new MouseEvent("mouseenter", { bubbles: true })
      );
      await sleep(MENU_HOVER_DELAY);

      // Step 2: Click the 3-dot menu button (broadened selectors)
      const menuButton = messageNode.querySelector(
        "#menu-button, yt-icon-button#menu-button, button[aria-label='Chat actions']"
      );
      if (!menuButton) {
        console.warn("[YT-Blocker] Menu button not found for", username);
        return false;
      }

      menuButton.click();

      // Step 3: Wait for menu to appear, then find "Block" option
      let blockItem = null;
      try {
        await waitForElement(
          "yt-live-chat-menu-service-item-renderer, ytd-menu-service-item-renderer, tp-yt-paper-item",
          3000
        );
      } catch {
        console.warn("[YT-Blocker] Menu did not appear for", username);
        document.dispatchEvent(
          new KeyboardEvent("keydown", { key: "Escape" })
        );
        return false;
      }

      const menuItems = document.querySelectorAll(
        "yt-live-chat-menu-service-item-renderer, ytd-menu-service-item-renderer, tp-yt-paper-item"
      );

      for (const item of menuItems) {
        const text = item.textContent.trim().toLowerCase();
        if (text.includes("block")) {
          blockItem = item;
          break;
        }
      }

      if (!blockItem) {
        console.warn("[YT-Blocker] Block menu item not found for", username);
        document.dispatchEvent(
          new KeyboardEvent("keydown", { key: "Escape" })
        );
        return false;
      }

      // Step 4: Click the Block option
      blockItem.click();

      // Step 5: Wait for confirm dialog, then click confirm
      const confirmSelectors = [
        "yt-confirm-dialog-renderer #confirm-button button",
        "tp-yt-paper-dialog #confirm-button button",
        'yt-button-renderer#confirm-button',
        '[aria-label="Block"]',
        "#confirm-button button",
      ].join(", ");

      try {
        const confirmButton = await waitForElement(confirmSelectors, 3000);
        confirmButton.click();
        await sleep(200);
        return true;
      } catch {
        // Fallback: search for text-based confirm buttons
        const paperButtons = document.querySelectorAll(
          "yt-button-renderer, paper-button, tp-yt-paper-button"
        );
        for (const btn of paperButtons) {
          const text = btn.textContent.trim().toLowerCase();
          if (text === "block" || text === "confirm") {
            btn.click();
            await sleep(200);
            return true;
          }
        }
      }

      console.warn("[YT-Blocker] Confirm button not found for", username);
      return false;
    } catch (err) {
      console.error("[YT-Blocker] Native block error:", err);
      return false;
    }
  }

  function hideMessage(messageNode, username) {
    // Skip if already hidden
    if (messageNode.dataset.ytBlockerHidden) return;

    messageNode.style.display = "none";
    messageNode.style.height = "0";
    messageNode.style.overflow = "hidden";
    messageNode.dataset.ytBlockerHidden = "true";

    console.log(`[YT-Blocker] Hid message from ${username} (fallback)`);
    chrome.runtime.sendMessage({
      type: "USER_BLOCKED",
      username,
      reason: "hidden (native block failed)",
    });
  }

  // --- Sweep: catch messages from blocked users that slipped through ---
  function sweepBlockedMessages(container) {
    if (blockedUsers.size === 0) return;

    const items = container.querySelectorAll(
      "yt-live-chat-text-message-renderer:not([data-yt-blocker-hidden])"
    );
    for (const node of items) {
      const authorEl = node.querySelector("#author-name");
      if (!authorEl) continue;
      const username = authorEl.textContent.trim();
      if (blockedUsers.has(username)) {
        hideMessage(node, username);
      }
    }
  }

  // --- Chat observer ---
  function observeChat(itemsContainer) {
    if (observer) observer.disconnect();

    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          const authorEl = node.querySelector("#author-name");
          const messageEl = node.querySelector("#message");

          if (!authorEl || !messageEl) continue;

          const username = authorEl.textContent.trim();
          const text = messageEl.textContent.trim();

          if (!username || !text) continue;

          // Instant hide for known blocked users — no queueing
          if (blockedUsers.has(username)) {
            hideMessage(node, username);
            continue;
          }

          queueMessage(username, text, node);
        }
      }
    });

    observer.observe(itemsContainer, { childList: true });
    console.log("[YT-Blocker] Chat observer started.");

    // Periodic sweep to catch messages from blocked users that slipped through re-renders
    sweepTimer = setInterval(
      () => sweepBlockedMessages(itemsContainer),
      SWEEP_INTERVAL
    );
  }

  // --- Initialize ---
  async function init() {
    console.log("[YT-Blocker] Content script loaded in live chat iframe.");

    // Load persisted blocked users before starting observer
    await loadBlockedUsers();

    try {
      const itemsContainer = await waitForElement(
        "yt-live-chat-item-list-renderer #items",
        30000
      );
      console.log("[YT-Blocker] Chat items container found.");
      observeChat(itemsContainer);
    } catch (err) {
      console.error("[YT-Blocker] Failed to find chat container:", err);
    }
  }

  init();
})();
