/**
 * Frontend logic for Repost Bot MRIYU.
 * Lightweight Vanilla JS with real-time status polling, config management, diagnostics,
 * and Telethon MTProto client authentication.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const statusBadge = document.getElementById("statusBadge");
  const statusText = document.getElementById("statusText");
  const infoChannel = document.getElementById("infoChannel");
  const infoTarget = document.getElementById("infoTarget");
  const infoLastCheck = document.getElementById("infoLastCheck");
  const infoNextCheck = document.getElementById("infoNextCheck");
  const infoLastError = document.getElementById("infoLastError");

  const btnToggleEngine = document.getElementById("btnToggleEngine");
  const btnTriggerCheck = document.getElementById("btnTriggerCheck");

  const statReposted = document.getElementById("statReposted");
  const statFiltered = document.getElementById("statFiltered");
  const statErrors = document.getElementById("statErrors");
  const statTotal = document.getElementById("statTotal");

  const settingsForm = document.getElementById("settingsForm");
  const tgMode = document.getElementById("tgMode");
  const tgBotTokenGroup = document.getElementById("tgBotTokenGroup");
  const tgTelethonGroup = document.getElementById("tgTelethonGroup");
  const tgApiId = document.getElementById("tgApiId");
  const tgApiHash = document.getElementById("tgApiHash");
  const tgPhone = document.getElementById("tgPhone");
  const telethonStatusBadge = document.getElementById("telethonStatusBadge");
  const telethonStatusText = document.getElementById("telethonStatusText");
  const telethonDeliveryAlert = document.getElementById("telethonDeliveryAlert");
  const btnTelethonSendCode = document.getElementById("btnTelethonSendCode");
  const btnTelethonSignInBot = document.getElementById("btnTelethonSignInBot");
  const btnTelethonCheckStatus = document.getElementById("btnTelethonCheckStatus");
  const btnTelethonLogout = document.getElementById("btnTelethonLogout");
  const telethonCodeGroup = document.getElementById("telethonCodeGroup");
  const tgAuthCode = document.getElementById("tgAuthCode");
  const tgAuthPassword = document.getElementById("tgAuthPassword");
  const btnTelethonSignIn = document.getElementById("btnTelethonSignIn");

  const mriyuAddButton = document.getElementById("mriyuAddButton");
  const buttonSettingsRow = document.getElementById("buttonSettingsRow");

  const btnTestMriyu = document.getElementById("btnTestMriyu");
  const mriyuChannelsDropdownGroup = document.getElementById("mriyuChannelsDropdownGroup");
  const mriyuChannelsSelect = document.getElementById("mriyuChannelsSelect");
  const mriyuTargetId = document.getElementById("mriyuTargetId");

  const replacementsBody = document.getElementById("replacementsBody");
  const btnAddReplacement = document.getElementById("btnAddReplacement");

  const historyList = document.getElementById("historyList");
  const btnRefreshHistory = document.getElementById("btnRefreshHistory");
  const btnClearHistory = document.getElementById("btnClearHistory");

  const logsTerminal = document.getElementById("logsTerminal");
  const logLevelFilter = document.getElementById("logLevelFilter");
  const btnRefreshLogs = document.getElementById("btnRefreshLogs");
  const btnClearLogs = document.getElementById("btnClearLogs");

  const diagTgChannel = document.getElementById("diagTgChannel");
  const btnDiagTestTg = document.getElementById("btnDiagTestTg");
  const diagTgResult = document.getElementById("diagTgResult");

  const diagMriyuToken = document.getElementById("diagMriyuToken");
  const btnDiagTestMriyu = document.getElementById("btnDiagTestMriyu");
  const diagMriyuResult = document.getElementById("diagMriyuResult");

  const toast = document.getElementById("toast");

  let isEngineRunning = false;
  let statusPollTimer = null;
  let logsPollTimer = null;
  let lastPhoneCodeHash = "";

  // ----------------------------------------------------
  // Toast Helper
  // ----------------------------------------------------
  function showToast(message, type = "info") {
    toast.textContent = message;
    toast.className = `toast toast-${type} show`;
    setTimeout(() => {
      toast.className = "toast";
    }, 3500);
  }

  // ----------------------------------------------------
  // Tabs Navigation
  // ----------------------------------------------------
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));

      btn.classList.add("active");
      const targetTabId = btn.getAttribute("data-tab");
      const targetTab = document.getElementById(targetTabId);
      if (targetTab) targetTab.classList.add("active");

      if (targetTabId === "tab-history") loadHistory();
      if (targetTabId === "tab-logs") loadLogs();
    });
  });

  // ----------------------------------------------------
  // Form conditional UI toggles
  // ----------------------------------------------------
  function updateModeVisibility() {
    const mode = tgMode.value;
    tgBotTokenGroup.style.display = mode === "bot_api" ? "block" : "none";
    tgTelethonGroup.style.display = mode === "telethon" ? "block" : "none";
    if (mode === "telethon") {
      checkTelethonStatus();
    }
  }

  tgMode.addEventListener("change", updateModeVisibility);

  mriyuAddButton.addEventListener("change", () => {
    buttonSettingsRow.style.display = mriyuAddButton.checked ? "grid" : "none";
  });

  // ----------------------------------------------------
  // Replacements Table Helper
  // ----------------------------------------------------
  function addReplacementRow(find = "", replace = "") {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="text" class="rep-find" value="${escapeHtml(find)}" placeholder="@old_channel"></td>
      <td><input type="text" class="rep-replace" value="${escapeHtml(replace)}" placeholder="@new_channel"></td>
      <td style="text-align: center;">
        <button type="button" class="btn btn-danger btn-sm btn-del-rep">✕</button>
      </td>
    `;
    tr.querySelector(".btn-del-rep").addEventListener("click", () => tr.remove());
    replacementsBody.appendChild(tr);
  }

  btnAddReplacement.addEventListener("click", () => addReplacementRow());

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ----------------------------------------------------
  // Status Polling
  // ----------------------------------------------------
  async function fetchStatus() {
    try {
      const resp = await fetch("/api/status");
      if (!resp.ok) return;
      const data = await resp.json();

      isEngineRunning = data.running;

      if (data.running) {
        statusBadge.className = "badge badge-running";
        statusText.textContent = "Працює в фоні";
        btnToggleEngine.className = "btn btn-danger";
        btnToggleEngine.innerHTML = "<span>⏹ Зупинити рушій</span>";
      } else {
        statusBadge.className = "badge badge-stopped";
        statusText.textContent = "Зупинено";
        btnToggleEngine.className = "btn btn-success";
        btnToggleEngine.innerHTML = "<span>▶ Запустити рушій</span>";
      }

      infoChannel.textContent = data.channel ? `@${data.channel.replace(/^@/, '')}` : "не налаштовано";
      infoTarget.textContent = data.mriyu_target_id ? `${data.mriyu_target_type}: ${data.mriyu_target_id}` : "не налаштовано";
      infoLastCheck.textContent = data.last_check_time || "—";
      infoNextCheck.textContent = data.next_check_time || "—";

      if (data.last_error) {
        infoLastError.style.display = "block";
        infoLastError.textContent = `⚠️ Помилка: ${data.last_error}`;
      } else {
        infoLastError.style.display = "none";
      }

      if (data.stats) {
        statReposted.textContent = data.stats.reposted || 0;
        statFiltered.textContent = data.stats.filtered || 0;
        statErrors.textContent = data.stats.errors || 0;
        statTotal.textContent = data.stats.total_processed || 0;
      }
    } catch (err) {
      console.warn("Status fetch error:", err);
    }
  }

  // Engine controls
  btnToggleEngine.addEventListener("click", async () => {
    const endpoint = isEngineRunning ? "/api/engine/stop" : "/api/engine/start";
    try {
      const resp = await fetch(endpoint, { method: "POST" });
      const res = await resp.json();
      showToast(res.message || "Статус оновлено", "info");
      fetchStatus();
    } catch (e) {
      showToast("Помилка зв'язку з сервером", "error");
    }
  });

  btnTriggerCheck.addEventListener("click", async () => {
    try {
      const resp = await fetch("/api/engine/trigger", { method: "POST" });
      const res = await resp.json();
      showToast(res.message || "Перевірку запущено", "info");
      fetchStatus();
    } catch (e) {
      showToast("Помилка запиту", "error");
    }
  });

  // ----------------------------------------------------
  // Telethon Client Authentication Handlers
  // ----------------------------------------------------
  async function checkTelethonStatus() {
    const api_id = tgApiId.value.trim();
    const api_hash = tgApiHash.value.trim();
    try {
      const params = new URLSearchParams();
      if (api_id) params.set("api_id", api_id);
      if (api_hash) params.set("api_hash", api_hash);

      const resp = await fetch(`/api/telethon/status?${params.toString()}`);
      if (!resp.ok) return;
      const data = await resp.json();

      if (!data.available) {
        telethonStatusBadge.className = "telethon-status-pill not-auth";
        telethonStatusText.textContent = "Telethon не встановлено в системі";
        return;
      }

      if (data.authorized) {
        telethonStatusBadge.className = "telethon-status-pill auth";
        const u = data.user || {};
        const title = u.first_name ? `${u.first_name} ${u.username ? '(@' + u.username + ')' : ''}` : (u.phone || 'Активна сесія');
        telethonStatusText.textContent = `✅ Авторизовано: ${title}`;
        btnTelethonLogout.style.display = "inline-flex";
        telethonCodeGroup.style.display = "none";
      } else {
        telethonStatusBadge.className = "telethon-status-pill not-auth";
        if (data.configured) {
          telethonStatusText.textContent = "❌ Не авторизовано (потрібен вхід)";
        } else {
          telethonStatusText.textContent = "⚪ Введіть API ID та Hash";
        }
        btnTelethonLogout.style.display = "none";
      }
    } catch (err) {
      console.warn("Telethon status check error:", err);
    }
  }

  btnTelethonCheckStatus.addEventListener("click", () => {
    checkTelethonStatus();
    showToast("Статус Telethon оновлено", "info");
  });

  btnTelethonSendCode.addEventListener("click", async () => {
    const api_id = tgApiId.value.trim();
    const api_hash = tgApiHash.value.trim();
    const phone = tgPhone.value.trim();

    if (!api_id || !api_hash) {
      showToast("Вкажіть Telegram API ID та API Hash", "error");
      return;
    }
    if (!phone) {
      showToast("Вкажіть номер телефону акаунта (+380...)", "error");
      return;
    }

    btnTelethonSendCode.disabled = true;
    btnTelethonSendCode.textContent = "Надсилаємо код...";

    try {
      const resp = await fetch("/api/telethon/send_code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_id, api_hash, phone })
      });
      const data = await resp.json();

      if (data.ok) {
        lastPhoneCodeHash = data.phone_code_hash;
        telethonCodeGroup.style.display = "block";
        if (telethonDeliveryAlert) {
          telethonDeliveryAlert.innerHTML = `<strong>📩 Спосіб доставки:</strong> ${escapeHtml(data.message)}`;
          telethonDeliveryAlert.style.borderColor = "#38bdf8";
          telethonDeliveryAlert.style.color = "#f8fafc";
        }
        showToast(data.message || "Код надіслано в Telegram!", "success");
        tgAuthCode.focus();
      } else {
        if (telethonDeliveryAlert) {
          telethonCodeGroup.style.display = "block";
          telethonDeliveryAlert.innerHTML = `<strong style="color: #f87171;">❌ Помилка Telegram:</strong> ${escapeHtml(data.error || "Не вдалося надіслати код")}`;
          telethonDeliveryAlert.style.borderColor = "#ef4444";
        }
        showToast(data.error || "Не вдалося надіслати код", "error");
      }
    } catch (e) {
      showToast("Помилка зв'язку з сервером", "error");
    } finally {
      btnTelethonSendCode.disabled = false;
      btnTelethonSendCode.textContent = "📲 Надіслати код у Telegram";
    }
  });

  btnTelethonSignIn.addEventListener("click", async () => {
    const api_id = tgApiId.value.trim();
    const api_hash = tgApiHash.value.trim();
    const phone = tgPhone.value.trim();
    const code = tgAuthCode.value.trim();
    const password = tgAuthPassword.value.trim();

    if (!code) {
      showToast("Введіть код підтвердження з Telegram", "error");
      return;
    }

    btnTelethonSignIn.disabled = true;
    btnTelethonSignIn.textContent = "Перевіряємо код...";

    try {
      const resp = await fetch("/api/telethon/sign_in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_id,
          api_hash,
          phone,
          code,
          phone_code_hash: lastPhoneCodeHash,
          password
        })
      });
      const data = await resp.json();

      if (data.ok) {
        showToast(data.message || "Успішно увійшли в Telegram!", "success");
        telethonCodeGroup.style.display = "none";
        tgAuthCode.value = "";
        tgAuthPassword.value = "";
        checkTelethonStatus();
      } else if (data.needs_password) {
        showToast(data.message || "Введіть пароль двофакторної автентифікації 2FA", "error");
        tgAuthPassword.focus();
      } else {
        showToast(data.error || data.message || "Помилка входу", "error");
      }
    } catch (e) {
      showToast("Помилка запиту", "error");
    } finally {
      btnTelethonSignIn.disabled = false;
      btnTelethonSignIn.textContent = "✅ Підтвердити та увійти";
    }
  });

  if (btnTelethonSignInBot) {
    btnTelethonSignInBot.addEventListener("click", async () => {
      const api_id = tgApiId.value.trim();
      const api_hash = tgApiHash.value.trim();
      if (!api_id || !api_hash) {
        showToast("Спочатку вкажіть API ID та API Hash", "error");
        return;
      }
      const bot_token = prompt("Введіть токен Telegram бота з @BotFather:");
      if (!bot_token || !bot_token.trim()) return;

      btnTelethonSignInBot.disabled = true;
      try {
        const resp = await fetch("/api/telethon/sign_in_bot", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_id, api_hash, bot_token: bot_token.trim() })
        });
        const data = await resp.json();
        if (data.ok) {
          showToast(data.message || "Telethon успішно авторизовано як бот!", "success");
          checkTelethonStatus();
        } else {
          showToast(data.error || "Помилка авторизації бота", "error");
        }
      } catch (e) {
        showToast("Помилка зв'язку з сервером", "error");
      } finally {
        btnTelethonSignInBot.disabled = false;
      }
    });
  }

  btnTelethonLogout.addEventListener("click", async () => {
    if (!confirm("Ви дійсно бажаєте вийти із сесії Telethon?")) return;
    try {
      const resp = await fetch("/api/telethon/logout", { method: "POST" });
      const data = await resp.json();
      if (data.ok) {
        showToast("Сесію Telethon завершено", "info");
        checkTelethonStatus();
      } else {
        showToast(data.error || "Помилка виходу", "error");
      }
    } catch (e) {
      showToast("Помилка зв'язку з сервером", "error");
    }
  });

  // ----------------------------------------------------
  // Configuration Load & Save
  // ----------------------------------------------------
  async function loadConfig() {
    try {
      const resp = await fetch("/api/config");
      if (!resp.ok) return;
      const cfg = await resp.json();

      // Telegram
      document.getElementById("tgChannel").value = cfg.telegram.channel || "";
      tgMode.value = cfg.telegram.mode || "scraper";
      document.getElementById("tgBotToken").value = cfg.telegram.bot_token || "";
      document.getElementById("tgPollInterval").value = cfg.telegram.poll_interval || 60;
      document.getElementById("tgSyncCount").value = cfg.telegram.initial_sync_count ?? 3;

      tgApiId.value = cfg.telegram.api_id || "";
      tgApiHash.value = cfg.telegram.api_hash || "";
      tgPhone.value = cfg.telegram.phone || "";

      updateModeVisibility();

      // MRIYU
      document.getElementById("mriyuToken").value = cfg.mriyu.token || "";
      document.getElementById("mriyuTargetType").value = cfg.mriyu.target_type || "chat";
      document.getElementById("mriyuTargetId").value = cfg.mriyu.target_id || "";
      document.getElementById("mriyuSilent").checked = !!cfg.mriyu.silent;
      mriyuAddButton.checked = !!cfg.mriyu.add_button;
      document.getElementById("mriyuButtonText").value = cfg.mriyu.button_text || "Оригінал посту";
      document.getElementById("mriyuButtonUrl").value = cfg.mriyu.button_url || "";
      buttonSettingsRow.style.display = mriyuAddButton.checked ? "grid" : "none";

      // Filters
      document.getElementById("filterBlacklist").value = (cfg.filter.keyword_blacklist || []).join(", ");
      document.getElementById("filterWhitelist").value = (cfg.filter.keyword_whitelist || []).join(", ");
      document.getElementById("filterMinLength").value = cfg.filter.min_length || 0;
      document.getElementById("filterMaxLength").value = cfg.filter.max_length || 0;
      document.getElementById("filterAllowPhotos").checked = cfg.filter.allow_photos ?? true;
      document.getElementById("filterAllowTextOnly").checked = cfg.filter.allow_text_only ?? true;
      document.getElementById("filterIgnoreForwards").checked = !!cfg.filter.ignore_forwards;
      document.getElementById("filterSkipLinks").checked = !!cfg.filter.skip_links;

      // Formatting
      document.getElementById("fmtHeaderPrefix").value = cfg.formatting.header_prefix || "";
      document.getElementById("fmtFooterSuffix").value = cfg.formatting.footer_suffix || "";
      document.getElementById("fmtAddSourceLink").checked = cfg.formatting.add_source_link ?? true;
      document.getElementById("fmtSourceLinkText").value = cfg.formatting.source_link_text || "Джерело в Telegram";
      document.getElementById("fmtConvertMarkdown").checked = cfg.formatting.convert_markdown ?? true;
      document.getElementById("fmtRemoveUrls").checked = !!cfg.formatting.remove_urls;
      document.getElementById("fmtRemoveHashtags").checked = !!cfg.formatting.remove_hashtags;

      // Replacements
      replacementsBody.innerHTML = "";
      if (Array.isArray(cfg.formatting.replacements)) {
        cfg.formatting.replacements.forEach(rep => addReplacementRow(rep.find, rep.replace));
      }
    } catch (e) {
      console.error("Config load error:", e);
      showToast("Помилка завантаження конфігурації", "error");
    }
  }

  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Collect replacements
    const replacements = [];
    replacementsBody.querySelectorAll("tr").forEach(tr => {
      const f = tr.querySelector(".rep-find").value.trim();
      const r = tr.querySelector(".rep-replace").value;
      if (f) replacements.push({ find: f, replace: r });
    });

    const payload = {
      telegram: {
        channel: document.getElementById("tgChannel").value.trim(),
        mode: tgMode.value,
        bot_token: document.getElementById("tgBotToken").value.trim(),
        poll_interval: parseInt(document.getElementById("tgPollInterval").value, 10) || 60,
        initial_sync_count: parseInt(document.getElementById("tgSyncCount").value, 10) || 0,
        api_id: tgApiId.value.trim(),
        api_hash: tgApiHash.value.trim(),
        phone: tgPhone.value.trim(),
      },
      mriyu: {
        token: document.getElementById("mriyuToken").value.trim(),
        target_type: document.getElementById("mriyuTargetType").value,
        target_id: document.getElementById("mriyuTargetId").value.trim(),
        silent: document.getElementById("mriyuSilent").checked,
        add_button: mriyuAddButton.checked,
        button_text: document.getElementById("mriyuButtonText").value.trim(),
        button_url: document.getElementById("mriyuButtonUrl").value.trim(),
      },
      filter: {
        keyword_blacklist: document.getElementById("filterBlacklist").value.split(",").map(s => s.trim()).filter(Boolean),
        keyword_whitelist: document.getElementById("filterWhitelist").value.split(",").map(s => s.trim()).filter(Boolean),
        min_length: parseInt(document.getElementById("filterMinLength").value, 10) || 0,
        max_length: parseInt(document.getElementById("filterMaxLength").value, 10) || 0,
        allow_photos: document.getElementById("filterAllowPhotos").checked,
        allow_text_only: document.getElementById("filterAllowTextOnly").checked,
        ignore_forwards: document.getElementById("filterIgnoreForwards").checked,
        skip_links: document.getElementById("filterSkipLinks").checked,
      },
      formatting: {
        header_prefix: document.getElementById("fmtHeaderPrefix").value,
        footer_suffix: document.getElementById("fmtFooterSuffix").value,
        add_source_link: document.getElementById("fmtAddSourceLink").checked,
        source_link_text: document.getElementById("fmtSourceLinkText").value,
        convert_markdown: document.getElementById("fmtConvertMarkdown").checked,
        remove_urls: document.getElementById("fmtRemoveUrls").checked,
        remove_hashtags: document.getElementById("fmtRemoveHashtags").checked,
        replacements: replacements,
      }
    };

    try {
      const resp = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const res = await resp.json();
      if (res.ok) {
        showToast("✅ Налаштування успішно збережено!", "success");
        fetchStatus();
      } else {
        showToast("Помилка збереження налаштувань", "error");
      }
    } catch (e) {
      showToast("Помилка відправки форми", "error");
    }
  });

  // ----------------------------------------------------
  // Test MRIYU & Load Channels Button
  // ----------------------------------------------------
  btnTestMriyu.addEventListener("click", async () => {
    const token = document.getElementById("mriyuToken").value.trim();
    if (!token) {
      showToast("Спочатку введіть токен бота MRIYU", "error");
      return;
    }

    btnTestMriyu.disabled = true;
    btnTestMriyu.textContent = "Перевіряємо...";

    try {
      const resp = await fetch("/api/test/mriyu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
      const data = await resp.json();

      if (data.ok) {
        showToast(`Бот підключений: @${data.bot?.username || data.bot?.name}`, "success");
        const chats = data.chats || [];
        if (chats.length > 0) {
          mriyuChannelsSelect.innerHTML = '<option value="">-- Оберіть канал зі списку --</option>';
          chats.forEach(ch => {
            const opt = document.createElement("option");
            opt.value = ch.id;
            opt.textContent = `${ch.title} (ID: ${ch.id}, тип: ${ch.type}, роль: ${ch.role || 'bot'})`;
            mriyuChannelsSelect.appendChild(opt);
          });
          mriyuChannelsDropdownGroup.style.display = "block";
        } else {
          showToast("Токен дійсний, але бота ще не додано в жоден канал як адміна", "info");
        }
      } else {
        showToast(`Помилка токена: ${data.error || "Невірний токен"}`, "error");
      }
    } catch (e) {
      showToast("Помилка підключення до API MRIYU", "error");
    } finally {
      btnTestMriyu.disabled = false;
      btnTestMriyu.textContent = "🔍 Завантажити канали";
    }
  });

  mriyuChannelsSelect.addEventListener("change", () => {
    if (mriyuChannelsSelect.value) {
      mriyuTargetId.value = mriyuChannelsSelect.value;
      showToast(`Цільовий ID встановлено: ${mriyuChannelsSelect.value}`, "info");
    }
  });

  // ----------------------------------------------------
  // History Tab
  // ----------------------------------------------------
  async function loadHistory() {
    try {
      const resp = await fetch("/api/posts?limit=50");
      if (!resp.ok) return;
      const posts = await resp.json();

      historyList.innerHTML = "";
      if (posts.length === 0) {
        historyList.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 30px;">Історія поки порожня</div>`;
        return;
      }

      posts.forEach(p => {
        const item = document.createElement("div");
        item.className = "post-card";
        const statusColor = p.status === "reposted" ? "#34d399" : (p.status === "filtered" ? "#fbbf24" : "#f87171");
        const statusTitle = p.status === "reposted" ? "Репостнуто" : (p.status === "filtered" ? "Відфільтровано" : "Помилка");

        item.innerHTML = `
          <div class="post-header">
            <div>
              <strong>${escapeHtml(p.post_id)}</strong> 
              <span style="margin-left: 8px; color: ${statusColor}; font-weight: 600;">● ${statusTitle}</span>
              ${p.mriyu_msg_id ? `<span style="margin-left: 8px; color: var(--accent-cyan);">(MRIYU ID: ${p.mriyu_msg_id})</span>` : ""}
            </div>
            <div>${p.created_at || ""}</div>
          </div>
          <div class="post-body">${escapeHtml(p.text_snippet || "(без тексту)")}</div>
          ${p.error_detail ? `<div style="font-size: 0.8rem; color: #f87171;">Причина / Деталі: ${escapeHtml(p.error_detail)}</div>` : ""}
        `;
        historyList.appendChild(item);
      });
    } catch (e) {
      console.warn("History fetch error:", e);
    }
  }

  btnRefreshHistory.addEventListener("click", loadHistory);

  btnClearHistory.addEventListener("click", async () => {
    if (!confirm("Ви впевнені, що хочете скинути історію постів? Після цього наявні пости можуть бути репостнуті знову.")) return;
    try {
      await fetch("/api/posts/clear", { method: "POST" });
      loadHistory();
      fetchStatus();
      showToast("Історію постів очищено", "info");
    } catch (e) {
      showToast("Помилка", "error");
    }
  });

  // ----------------------------------------------------
  // Logs Tab
  // ----------------------------------------------------
  async function loadLogs() {
    try {
      const level = logLevelFilter.value;
      const url = level ? `/api/logs?level=${level}&limit=100` : "/api/logs?limit=100";
      const resp = await fetch(url);
      if (!resp.ok) return;
      const logs = await resp.json();

      logsTerminal.innerHTML = "";
      if (logs.length === 0) {
        logsTerminal.innerHTML = `<div style="color: var(--text-muted); padding: 10px;">Записів у журналі немає</div>`;
        return;
      }

      const reversed = [...logs].reverse();
      reversed.forEach(l => {
        const row = document.createElement("div");
        row.className = "log-entry";
        row.innerHTML = `
          <span class="log-time">[${l.timestamp.split(" ")[1] || l.timestamp}]</span>
          <span class="log-level ${l.level}">${l.level}</span>
          <span class="log-msg">${escapeHtml(l.message)} ${l.details ? `(${escapeHtml(l.details)})` : ""}</span>
        `;
        logsTerminal.appendChild(row);
      });

      logsTerminal.scrollTop = logsTerminal.scrollHeight;
    } catch (e) {
      console.warn("Logs fetch error:", e);
    }
  }

  btnRefreshLogs.addEventListener("click", loadLogs);
  logLevelFilter.addEventListener("change", loadLogs);

  btnClearLogs.addEventListener("click", async () => {
    try {
      await fetch("/api/logs/clear", { method: "POST" });
      loadLogs();
      showToast("Журнал очищено", "info");
    } catch (e) {
      showToast("Помилка", "error");
    }
  });

  // ----------------------------------------------------
  // Diagnostics Tab
  // ----------------------------------------------------
  btnDiagTestTg.addEventListener("click", async () => {
    const ch = diagTgChannel.value.trim() || document.getElementById("tgChannel").value.trim();
    if (!ch) {
      showToast("Вкажіть назву або посилання на канал Telegram", "error");
      return;
    }

    const mode = tgMode.value;
    const api_id = tgApiId.value.trim();
    const api_hash = tgApiHash.value.trim();

    btnDiagTestTg.disabled = true;
    btnDiagTestTg.textContent = "Перевіряємо...";
    diagTgResult.style.display = "block";
    diagTgResult.innerHTML = `<div style="color: var(--text-muted);">Опитування каналу ${escapeHtml(ch)} (режим: ${mode})...</div>`;

    try {
      const resp = await fetch("/api/test/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: ch, mode, api_id, api_hash })
      });
      const data = await resp.json();

      if (data.ok) {
        let html = `<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 12px; border-radius: 8px; margin-bottom: 12px;">
          <strong style="color: #34d399;">✅ Канал знайдено!</strong> Отримано постів: ${data.count}. Останні пости:
        </div>`;

        (data.posts || []).forEach(p => {
          html += `
            <div class="post-card" style="margin-bottom: 10px;">
              <div class="post-header">
                <strong>${escapeHtml(p.post_id)}</strong> 
                <span>${p.photos?.length ? `📷 Фото (${p.photos.length})` : '📝 Текст'}</span>
              </div>
              <div class="post-body">${escapeHtml(p.raw_text || "(без тексту)")}</div>
              ${p.photos?.length && p.photos[0].startsWith('http') ? `<div style="margin-top: 6px;"><img src="${escapeHtml(p.photos[0])}" style="max-height: 140px; border-radius: 6px;"></div>` : ''}
            </div>
          `;
        });
        diagTgResult.innerHTML = html;
      } else {
        diagTgResult.innerHTML = `<div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 12px; border-radius: 8px; color: #f87171;">
          ❌ Помилка: ${escapeHtml(data.message || "Не вдалося прочитати канал")}
        </div>`;
      }
    } catch (e) {
      diagTgResult.innerHTML = `<div style="color: #f87171;">Помилка запиту до сервера</div>`;
    } finally {
      btnDiagTestTg.disabled = false;
      btnDiagTestTg.textContent = "Перевірити канал";
    }
  });

  btnDiagTestMriyu.addEventListener("click", async () => {
    const token = diagMriyuToken.value.trim() || document.getElementById("mriyuToken").value.trim();
    if (!token) {
      showToast("Введіть токен бота MRIYU", "error");
      return;
    }

    btnDiagTestMriyu.disabled = true;
    btnDiagTestMriyu.textContent = "Тестуємо...";
    diagMriyuResult.style.display = "block";
    diagMriyuResult.innerHTML = `<div style="color: var(--text-muted);">Перевірка токена через getMe та getChats...</div>`;

    try {
      const resp = await fetch("/api/test/mriyu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
      const data = await resp.json();

      if (data.ok) {
        const b = data.bot || {};
        const chats = data.chats || [];
        let html = `
          <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 14px; border-radius: 8px;">
            <h4 style="color: #34d399; margin-bottom: 6px;">✅ Токен валідний! Бот активний</h4>
            <div style="font-size: 0.9rem; line-height: 1.6;">
              <div><strong>ID бота:</strong> ${b.id}</div>
              <div><strong>Ім'я:</strong> ${escapeHtml(b.name || '')} (@${escapeHtml(b.username || '')})</div>
              <div><strong>Опис:</strong> ${escapeHtml(b.about || '—')}</div>
              <div><strong>Підписників:</strong> ${b.subscribers ?? '—'}</div>
              <div><strong>Офіційний:</strong> ${b.verified ? 'Так ✅' : 'Ні'}</div>
            </div>
            <hr style="border: none; border-top: 1px solid var(--border); margin: 12px 0;">
            <h5 style="margin-bottom: 6px;">Канали та групи, де присутній бот (${chats.length}):</h5>
        `;

        if (chats.length > 0) {
          html += '<ul style="padding-left: 20px; font-size: 0.88rem;">';
          chats.forEach(ch => {
            html += `<li><strong>${escapeHtml(ch.title)}</strong> (ID: <code style="color: var(--accent-cyan);">${ch.id}</code>, тип: ${ch.type}, роль: <strong>${ch.role || '—'}</strong>)</li>`;
          });
          html += '</ul>';
        } else {
          html += '<div style="color: var(--text-muted); font-size: 0.85rem;">Бот ще не доданий в жоден канал або групу. Додайте бота в налаштуваннях вашого каналу в MRIYU як адміністратора.</div>';
        }

        html += `</div>`;
        diagMriyuResult.innerHTML = html;
      } else {
        diagMriyuResult.innerHTML = `
          <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 14px; border-radius: 8px; color: #f87171;">
            ❌ Помилка авторизації в MRIYU API: ${escapeHtml(data.error || "Невірний токен")} (код: ${data.error_code || '—'})
          </div>
        `;
      }
    } catch (e) {
      diagMriyuResult.innerHTML = `<div style="color: #f87171;">Помилка запиту до сервера</div>`;
    } finally {
      btnDiagTestMriyu.disabled = false;
      btnDiagTestMriyu.textContent = "Перевірити токен";
    }
  });

  // ----------------------------------------------------
  // Init
  // ----------------------------------------------------
  loadConfig();
  fetchStatus();
  statusPollTimer = setInterval(fetchStatus, 3000);
  logsPollTimer = setInterval(() => {
    const logsTab = document.getElementById("tab-logs");
    if (logsTab && logsTab.classList.contains("active")) {
      loadLogs();
    }
  }, 3500);
});
