(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const MODE_LABELS = { list: "По списку", global: "Всё" };
  const MODE_NOTES = {
    list: "Системный обход доменов из списка — работает во всех браузерах и приложениях.",
    global: "Системный обход TCP 80/443 и UDP 443 — для всех программ, кроме list-exclude.txt.",
  };
  const LIST_META = {
    general: { title: "Список обхода", filename: "list-general.txt" },
    exclude: { title: "Список исключений", filename: "list-exclude.txt" },
  };
  const SERVICE_IDS = ["youtube", "discord", "cloudflare"];

  const state = {
    api: null,
    ready: false,
    bootInFlight: false,
    wired: false,
    data: null,
    settings: {},
    presets: [],
    presetsError: null,
    presetsUpdated: "",
    environment: null,
    status: null,
    usage: null,
    autostart: false,
    activeTab: "home",
    operation: null,
    autotuneStep: "",
    previousRunning: null,
    pollTimer: null,
    pollInFlight: false,
    logInFlight: false,
    logCursor: 0,
    logEntries: [],
    logPinned: true,
    testing: false,
    listsLoaded: false,
    listsLoading: false,
    listKey: "general",
    lists: { general: null, exclude: null },
    drafts: { general: "", exclude: "" },
    originals: { general: "", exclude: "" },
    listsDirty: { general: false, exclude: false },
    previewCommand: "",
    previewError: null,
    currentCommand: "",
    previewTimer: null,
    envBusy: false,
    autostartBusy: false,
    bannerActions: { primary: null, secondary: null },
    uiStarted: false,
  };

  // --------------------------------------------------------------- utilities
  function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value == null ? "" : String(value);
  }

  function setHidden(element, hidden) {
    if (!element) return;
    element.hidden = Boolean(hidden);
  }

  function makeIcon(name, className = "icon") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#i-${name}`);
    svg.appendChild(use);
    return svg;
  }

  function setUseIcon(svgElement, name) {
    if (!svgElement) return;
    const use = svgElement.querySelector("use");
    if (use) use.setAttribute("href", `#i-${name}`);
  }

  function formatUptime(totalSeconds) {
    const seconds = Math.max(0, Number(totalSeconds) || 0);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }

  function formatSize(bytes) {
    const n = Number(bytes) || 0;
    if (n < 1024) return `${n} Б`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(n >= 100 * 1024 ? 0 : 1)} КБ`;
    return `${(n / (1024 * 1024)).toFixed(1)} МБ`;
  }

  function formatCheckTime(timestamp) {
    try {
      return new Date(timestamp * 1000).toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "—";
    }
  }

  function formatDuration(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (hours > 0) return `${hours} ч ${String(minutes).padStart(2, "0")} м`;
    if (minutes > 0) return `${minutes} м`;
    return `${total} с`;
  }

  function formatLocalDate(timestamp) {
    if (!timestamp) return "—";
    try {
      return new Date(timestamp * 1000).toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch {
      return "—";
    }
  }

  function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function plural(count, one, few, many) {
    const n = Math.abs(count) % 100;
    const n1 = n % 10;
    if (n >= 11 && n <= 19) return many;
    if (n1 === 1) return one;
    if (n1 >= 2 && n1 <= 4) return few;
    return many;
  }

  function countDomains(text) {
    if (typeof text !== "string") return 0;
    let count = 0;
    for (const rawLine of text.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line) continue;
      if (line.startsWith("#") || line.startsWith(";") || line.startsWith("/")) continue;
      count += 1;
    }
    return count;
  }

  function presetById(id) {
    return state.presets.find((preset) => preset.id === id) || null;
  }

  function selectedPreset() {
    return presetById(state.settings.preset_id) || state.presets[0] || null;
  }

  function isRunning() {
    return Boolean(state.status && state.status.running);
  }

  function modeLabel(mode) {
    return MODE_LABELS[mode] || mode || "—";
  }

  function setSwitchBusy(input, busy) {
    if (!input) return;
    input.disabled = Boolean(busy);
    const holder = input.closest(".switch");
    if (holder) holder.classList.toggle("is-busy", Boolean(busy));
  }

  function truncate(text, length = 360) {
    const value = String(text || "");
    return value.length > length ? `${value.slice(0, length - 1)}…` : value;
  }

  // ------------------------------------------------------------------- toasts
  function showToast(message, type = "info", title = null) {
    const stack = $("toast-stack");
    if (!stack) return;
    const safeType = ["success", "error", "warning", "info"].includes(type) ? type : "info";
    const iconName = safeType === "success" ? "check" : safeType === "info" ? "info" : "alert";
    const defaults = { success: "Готово", error: "Ошибка", warning: "Внимание", info: "Информация" };

    while (stack.children.length >= 3) {
      stack.firstElementChild?.remove();
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${safeType}`;
    toast.appendChild(makeIcon(iconName, "icon toast-icon"));

    const copy = document.createElement("div");
    copy.className = "toast-copy";
    const strong = document.createElement("strong");
    strong.textContent = title || defaults[safeType];
    const body = document.createElement("span");
    body.textContent = truncate(message, 500);
    copy.append(strong, body);
    toast.appendChild(copy);
    stack.appendChild(toast);

    const timeout = safeType === "error" ? 6500 : 4200;
    window.setTimeout(() => {
      toast.classList.add("is-leaving");
      window.setTimeout(() => toast.remove(), 220);
    }, timeout);
  }

  // --------------------------------------------------------------- API bridge
  async function invoke(method, ...args) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== "function") {
      throw new Error("Мост PyWebView недоступен. Запустите приложение через main.py.");
    }
    const result = await api[method](...args);
    if (result === undefined || result === null) {
      throw new Error("Пустой ответ от локального движка");
    }
    return result;
  }

  function ensureOk(result) {
    if (result && result.ok === false) {
      const error = new Error(result.error || "Операция не выполнена");
      error.payload = result;
      throw error;
    }
    return result;
  }

  // ------------------------------------------------------------------ overlays
  function showLoading() {
    const overlay = $("loading-overlay");
    if (!overlay) return;
    overlay.hidden = false;
    overlay.classList.remove("is-dismissed");
  }

  function hideLoading() {
    const overlay = $("loading-overlay");
    if (!overlay || overlay.hidden) return;
    overlay.classList.add("is-dismissed");
    window.setTimeout(() => {
      overlay.hidden = true;
    }, 240);
  }

  function showFatal(message) {
    hideLoading();
    setText("fatal-message", message || "Проверьте журнал launcher.log и повторите попытку.");
    const fatal = $("fatal-overlay");
    if (fatal) fatal.hidden = false;
    state.ready = false;
  }

  function hideFatal() {
    const fatal = $("fatal-overlay");
    if (fatal) fatal.hidden = true;
  }

  // ------------------------------------------------------------------ bootstrap
  async function beginBootstrap() {
    if (state.bootInFlight) return;
    state.bootInFlight = true;
    showLoading();
    hideFatal();

    try {
      const result = await invoke("bootstrap");
      if (!result || result.ok === false) {
        throw new Error(result?.error || "Локальный API вернул ошибку");
      }
      hydrate(result);
    } catch (error) {
      showFatal(error?.message || String(error));
      console.error("Bootstrap failed", error);
    } finally {
      state.bootInFlight = false;
    }
  }

  function tryBridge() {
    if (state.api) return;
    const api = window.pywebview && window.pywebview.api;
    if (api && typeof api.bootstrap === "function") {
      state.api = api;
      beginBootstrap();
    }
  }

  function hydrate(data) {
    state.data = data;
    state.settings = { ...(data.settings || {}) };
    state.presets = Array.isArray(data.presets) ? data.presets.slice() : [];
    state.presetsError = data.presets_error || null;
    state.presetsUpdated = data.presets_updated || "";
    state.environment = data.environment || null;
    state.status = data.status || null;
    state.usage = data.usage || null;
    state.autostart = Boolean(data.autostart);
    state.listsLoaded = false;
    state.listsLoading = false;
    state.lists = { general: null, exclude: null };
    state.drafts = { general: "", exclude: "" };
    state.originals = { general: "", exclude: "" };
    state.listsDirty = { general: false, exclude: false };
    state.logEntries = [];
    state.logCursor = 0;
    state.logPinned = true;
    state.previewCommand = "";
    state.previewError = null;
    state.operation = null;
    state.autotuneStep = "";
    state.ready = true;
    state.previousRunning = Boolean(state.status?.running);

    renderVersion();
    renderUsage();
    renderStatusline();
    populatePresetSelect();
    applySettingsToControls();
    renderEnvironment();
    renderStatus();
    renderListCountsFromEnvironment();
    renderCheckNeutral();
    hideFatal();
    hideLoading();

    const validTab = ["home", "lists", "logs", "settings"].includes(state.settings.last_tab)
      ? state.settings.last_tab
      : "home";
    switchTab(validTab, { persist: false });
    scheduleCommandPreview();
    startPolling();

    const warnings = Array.isArray(data.warnings) ? data.warnings.filter(Boolean) : [];
    window.setTimeout(() => {
      if (warnings.length) {
        showToast(warnings[0], "warning", "Примечание");
        if (warnings.length > 1) {
          window.setTimeout(() => showToast(warnings[1], "warning", "Примечание"), 400);
        }
      }
      if (data.autostart_error) {
        showToast(data.autostart_error, "warning", "Автозапуск");
      }
    }, 350);
  }

  // ---------------------------------------------------------------- navigation
  function switchTab(tab, options = {}) {
    const { persist = true } = options;
    if (!["home", "lists", "logs", "settings"].includes(tab)) return;
    state.activeTab = tab;
    if (persist) state.settings.last_tab = tab;

    const tabs = $$(".tab");
    for (const button of tabs) {
      const isActive = button.dataset.tab === tab;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-selected", String(isActive));
      button.tabIndex = isActive ? 0 : -1;
    }

    for (const view of $$(".view")) {
      const isActive = view.id === `view-${tab}`;
      view.classList.toggle("active", isActive);
      view.setAttribute("aria-hidden", String(!isActive));
      if (isActive) view.scrollTop = 0;
    }

    if (tab === "lists") {
      void ensureListsLoaded();
    }
    if (tab === "logs") {
      state.logPinned = true;
      void fetchLogs();
      window.setTimeout(() => scrollLogsToBottom(false), 60);
    }

    if (persist && state.api) {
      void invoke("update_setting", "last_tab", tab).catch(() => {});
    }
  }

  function handleTabKeys(event) {
    const tabs = $$(".tab");
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex === -1) return;
    let nextIndex = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex == null) return;
    event.preventDefault();
    tabs[nextIndex].focus();
    switchTab(tabs[nextIndex].dataset.tab);
  }

  // -------------------------------------------------------------------- status
  function applyStatus(status, options = {}) {
    const { detect = true } = options;
    if (!status) return;
    const wasRunning = state.previousRunning === true;
    state.status = status;
    renderStatus();

    if (
      detect &&
      wasRunning &&
      !status.running &&
      status.last_error &&
      !state.operation
    ) {
      showToast(status.last_error, "error", "Обход остановлен");
    }
    state.previousRunning = Boolean(status.running);
    updatePendingIndicator();
  }

  function renderStatus() {
    const status = state.status || {};
    const running = Boolean(status.running);
    const operation = state.operation;
    const shell = $("app");
    const hasPresets = state.presets.length > 0;
    const preset = selectedPreset();

    shell.classList.toggle("engine-on", running && !operation);
    shell.classList.toggle(
      "engine-starting",
      operation === "start" ||
        operation === "stop" ||
        operation === "restart" ||
        operation === "autotune"
    );

    const eyebrow = $("status-eyebrow");
    const title = $("status-title");
    const subtitle = $("status-sub");
    const foot = $("hero-foot");

    if (operation === "start") {
      eyebrow.textContent = "ПОДКЛЮЧЕНИЕ";
      title.textContent = "Запускаем WinDivert";
      subtitle.textContent = "Проверяем параметры стратегии и поднимаем фильтры…";
    } else if (operation === "stop") {
      eyebrow.textContent = "ОСТАНОВКА";
      title.textContent = "Завершаем процесс";
      subtitle.textContent = "winws.exe аккуратно останавливается…";
    } else if (operation === "restart") {
      eyebrow.textContent = "ПЕРЕЗАПУСК";
      title.textContent = "Применяем настройки";
      subtitle.textContent = "winws.exe перезапускается с новой стратегией…";
    } else if (operation === "autotune") {
      eyebrow.textContent = "АВТОПОДБОР";
      title.textContent = "Ищем рабочую стратегию";
      subtitle.textContent =
        state.autotuneStep || "Проверяем доступность YouTube, Discord и Cloudflare…";
    } else if (running) {
      const active = status.active_config || {};
      eyebrow.textContent = "ОБХОД АКТИВЕН";
      title.textContent = "Трафик защищён";
      const presetName = active.preset_name || preset?.name || "Стратегия";
      subtitle.textContent = `${presetName} · ${modeLabel(active.mode || state.settings.mode)}. WinDivert фильтрует выбранный трафик.`;
    } else if (status.last_error) {
      eyebrow.textContent = "ОСТАНОВЛЕН";
      title.textContent = "winws завершился";
      subtitle.textContent = truncate(status.last_error, 150);
    } else {
      eyebrow.textContent = "ОБХОД ВЫКЛЮЧЕН";
      title.textContent = "Защита не запущена";
      if (preset) {
        subtitle.textContent = `Стратегия: ${preset.name} · ${preset.label}. Нажмите «Запустить обход».`;
      } else {
        subtitle.textContent = "Загрузите корректный presets.json, чтобы выбрать стратегию.";
      }
    }

    const showFoot = running && !operation;
    setHidden(foot, !showFoot);
    if (showFoot) {
      setText("uptime", formatUptime(status.uptime_seconds));
      setText("pid", status.pid ?? "—");
      const activeMode = status.active_config?.mode || state.settings.mode;
      const game = status.active_config?.game_filter;
      setText("active-mode", `${modeLabel(activeMode)}${game ? " · Game" : ""}`);
    }

    const toggle = $("btn-toggle");
    const toggleLabel = $("toggle-label");
    const toggleIcon = $("toggle-icon");
    const busy = Boolean(operation);
    toggle.disabled = busy || !hasPresets;
    toggle.classList.toggle("is-loading", busy);
    toggle.classList.toggle("is-running", busy ? operation !== "start" : running);

    if (operation === "start") {
      toggleLabel.textContent = "Запуск…";
      setUseIcon(toggleIcon, "play");
    } else if (operation === "stop") {
      toggleLabel.textContent = "Остановка…";
      setUseIcon(toggleIcon, "stop");
    } else if (operation === "restart") {
      toggleLabel.textContent = "Перезапуск…";
      setUseIcon(toggleIcon, "refresh");
    } else if (operation === "autotune") {
      toggleLabel.textContent = "Автоподбор…";
      setUseIcon(toggleIcon, "refresh");
    } else if (running) {
      toggleLabel.textContent = "Остановить обход";
      setUseIcon(toggleIcon, "stop");
    } else {
      toggleLabel.textContent = "Запустить обход";
      setUseIcon(toggleIcon, "play");
    }
    toggle.dataset.state = running ? "on" : "off";

    const autotuneButton = $("btn-autotune");
    const autotuneLabel = $("btn-autotune-label");
    if (autotuneButton) {
      autotuneButton.disabled = Boolean(operation) || state.testing;
      autotuneButton.classList.toggle("is-loading", operation === "autotune");
      if (autotuneLabel) {
        autotuneLabel.textContent =
          operation === "autotune" && state.autotuneStep
            ? state.autotuneStep.split(" ")[0]
            : "Подбор";
      }
    }
    const testButton = $("btn-test");
    if (testButton) testButton.disabled = state.testing || operation === "autotune";
    const lockConfig = operation === "autotune";
    const presetSelect = $("preset-select");
    if (presetSelect) presetSelect.disabled = lockConfig || !hasPresets;
    for (const button of $$("#mode-seg .seg-btn")) button.disabled = lockConfig;
    const gameToggle = $("game-filter");
    if (gameToggle) gameToggle.disabled = lockConfig;

    setHidden($("tab-log-live"), !running);
    document.title = running ? "Zapret RU — обход активен" : "Zapret RU";
    renderLogState();
    updatePendingIndicator();
    renderCommand();
    renderReapplyState();
    renderHeroAccessibility();
    renderStatusline();
  }

  function renderHeroAccessibility() {
    const hero = $("hero");
    if (!hero) return;
    const title = $("status-title")?.textContent || "";
    const subtitle = $("status-sub")?.textContent || "";
    hero.setAttribute("aria-label", `${title}. ${subtitle}`);
  }

  function renderLogState() {
    const holder = $("log-state-text")?.closest(".log-state");
    if (!holder) return;
    const status = state.status || {};
    const dotLine = $("log-dot");
    holder.classList.remove("is-running", "is-error");
    if (dotLine) dotLine.className = "status-dot";
    if (status.running) {
      holder.classList.add("is-running");
      setText("log-state-text", "winws работает");
    } else if (status.last_error) {
      holder.classList.add("is-error");
      setText("log-state-text", "Остановлен с ошибкой");
    } else if (status.last_exit_code != null) {
      setText("log-state-text", "Остановлен");
    } else {
      setText("log-state-text", "Ожидание запуска");
    }
  }

  function updatePendingIndicator() {
    const bar = $("reapply-bar");
    if (!bar) return;
    const active = state.status?.active_config || {};
    const running = isRunning();
    const changed =
      running &&
      Boolean(active.preset_id) &&
      (active.preset_id !== state.settings.preset_id ||
        active.mode !== state.settings.mode ||
        Boolean(active.game_filter) !== Boolean(state.settings.game_filter));
    setHidden(bar, !changed);
  }

  function renderReapplyState() {
    const button = $("btn-reapply");
    if (!button) return;
    button.disabled = Boolean(state.operation);
  }

  // ------------------------------------------------------------------- presets
  function populatePresetSelect() {
    const select = $("preset-select");
    if (!select) return;
    select.replaceChildren();
    if (!state.presets.length) {
      const option = new Option("Пресеты недоступны", "");
      select.appendChild(option);
      select.disabled = true;
      return;
    }
    select.disabled = false;
    for (const preset of state.presets) {
      const label = `${preset.name} · ${preset.label}`;
      select.appendChild(new Option(label, preset.id));
    }
    if (presetById(state.settings.preset_id)) {
      select.value = state.settings.preset_id;
    } else if (state.presets[0]) {
      select.value = state.presets[0].id;
    }
  }

  function renderPresetInfo() {
    const preset = selectedPreset();
    const badge = $("preset-badge");
    const description = $("preset-desc");
    const caution = $("preset-caution");
    const select = $("preset-select");

    if (!preset) {
      if (badge) badge.hidden = true;
      description.textContent = state.presetsError || "Пресеты не загружены. Проверьте presets.json.";
      caution.hidden = true;
      if (select) select.disabled = true;
      return;
    }

    if (select && select.value !== preset.id) select.value = preset.id;
    if (badge) {
      badge.hidden = !preset.badge;
      badge.textContent = preset.badge || "";
      badge.classList.toggle("is-accent", Boolean(preset.caution));
    }
    description.textContent = preset.description || "";
    if (preset.caution) {
      caution.hidden = false;
      caution.textContent = preset.caution;
    } else {
      caution.hidden = true;
      caution.textContent = "";
    }
    if (select) select.disabled = false;
  }

  function applySettingsToControls() {
    const select = $("preset-select");
    if (select && presetById(state.settings.preset_id)) select.value = state.settings.preset_id;
    renderPresetInfo();

    for (const button of $$("#mode-seg .seg-btn")) {
      const active = button.dataset.mode === state.settings.mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    setText("mode-note", MODE_NOTES[state.settings.mode] || "");

    const game = $("game-filter");
    if (game) game.checked = Boolean(state.settings.game_filter);

    const tray = $("tray-toggle");
    if (tray) tray.checked = Boolean(state.settings.minimize_to_tray);
    const auto = $("autostart-toggle");
    if (auto) auto.checked = Boolean(state.autostart);

    updatePendingIndicator();
    renderStatus();
  }

  async function persistSetting(key, value, options = {}) {
    const { onError = null } = options;
    const previous = state.settings[key];
    state.settings[key] = value;
    renderPresetInfo();
    if (key === "preset_id") {
      renderStatus();
      scheduleCommandPreview();
    }
    if (key === "mode" || key === "game_filter") {
      setText("mode-note", MODE_NOTES[state.settings.mode] || "");
      updatePendingIndicator();
      scheduleCommandPreview();
    }
    if (key === "minimize_to_tray") {
      // Saved immediately; closing behavior is handled by Python.
    }

    try {
      const result = await invoke("update_setting", key, value);
      if (result.ok === false) throw new Error(result.error || "Настройка не сохранена");
      state.settings = { ...(result.settings || state.settings) };
      applySettingsToControls();
      return true;
    } catch (error) {
      state.settings[key] = previous;
      applySettingsToControls();
      if (onError) onError(error);
      showToast(error.message || String(error), "error", "Настройки");
      return false;
    }
  }

  async function onPresetChanged() {
    const select = $("preset-select");
    const value = select?.value;
    if (!value || value === state.settings.preset_id) return;
    await persistSetting("preset_id", value);
    renderStatus();
    scheduleCommandPreview();
  }

  async function onModeClicked(button) {
    const mode = button?.dataset?.mode;
    if (!mode || mode === state.settings.mode) return;
    await persistSetting("mode", mode);
    renderStatus();
  }

  async function onGameChanged(event) {
    await persistSetting("game_filter", Boolean(event.target.checked));
    renderStatus();
  }

  // -------------------------------------------------------------------- engine
  async function toggleBypass() {
    if (!state.ready || state.operation) return;
    if (!state.presets.length) {
      showToast("Нет доступных стратегий. Проверьте presets.json.", "error", "Запуск");
      return;
    }
    const wasRunning = isRunning();
    state.operation = wasRunning ? "stop" : "start";
    renderStatus();
    renderReapplyState();

    try {
      const result = wasRunning
        ? await invoke("stop_bypass")
        : await invoke(
            "start_bypass",
            state.settings.preset_id,
            state.settings.mode,
            Boolean(state.settings.game_filter)
          );

      if (result.status) state.status = result.status;
      if (result.usage) applyUsage(result.usage);
      if (result.environment && state.environment !== result.environment) {
        updateEnvironment(result.environment, { render: false });
      }

      if (result.ok === false) {
        showToast(result.error || "Не удалось выполнить операцию", "error", wasRunning ? "Остановка" : "Запуск");
      } else if (wasRunning) {
        showToast("winws.exe остановлен, фильтры WinDivert сняты.", "success", "Обход остановлен");
      } else {
        const preset = selectedPreset();
        showToast(
          `Стратегия ${preset ? `${preset.name} · ${preset.label}` : state.settings.preset_id} активна.`,
          "success",
          "Обход запущен"
        );
      }
    } catch (error) {
      showToast(error.message || String(error), "error", wasRunning ? "Остановка" : "Запуск");
      await refreshStatusQuiet();
    } finally {
      state.operation = null;
      state.previousRunning = isRunning();
      renderStatus();
      renderEnvironment();
      renderReapplyState();
      if (state.activeTab === "logs") {
        void fetchLogs();
      }
    }
  }

  async function reapplySettings() {
    if (!state.ready || state.operation || !isRunning()) return;
    state.operation = "restart";
    renderStatus();
    renderReapplyState();
    try {
      const result = await invoke(
        "restart_bypass",
        state.settings.preset_id,
        state.settings.mode,
        Boolean(state.settings.game_filter)
      );
      if (result.status) state.status = result.status;
      if (result.usage) applyUsage(result.usage);
      if (result.environment) updateEnvironment(result.environment, { render: false });
      if (result.ok === false) {
        showToast(result.error || "Не удалось перезапустить winws.exe", "error", "Перезапуск");
      } else {
        showToast("winws.exe перезапущен с новыми параметрами.", "success", "Настройки применены");
      }
    } catch (error) {
      showToast(error.message || String(error), "error", "Перезапуск");
      await refreshStatusQuiet();
    } finally {
      state.operation = null;
      state.previousRunning = isRunning();
      renderStatus();
      renderEnvironment();
      renderReapplyState();
      if (state.activeTab === "logs") void fetchLogs();
    }
  }

  async function refreshStatusQuiet() {
    if (!state.api) return;
    try {
      const result = await invoke("get_status");
      if (result.ok !== false) {
        if (result.status) applyStatus(result.status, { detect: false });
        if (result.usage) applyUsage(result.usage);
      }
    } catch {
      // The normal polling loop will retry.
    }
  }

  function applyUsage(usage) {
    if (!usage) return;
    state.usage = usage;
    renderUsage();
    renderStatusline();
  }

  function renderUsage() {
    const usage = state.usage;
    if (!usage) return;
    setText("usage-launches", usage.app_launches ?? "—");
    setText("usage-bypass", usage.bypass_sessions ?? "—");
    setText("usage-bypass-time", formatDuration(usage.bypass_seconds));
    setText("usage-session-time", formatDuration(usage.launcher_seconds));
    const since = usage.first_seen
      ? `Локально с ${formatLocalDate(usage.first_seen)} · данные не покидают этот ПК`
      : "Локальный счётчик. Данные не отправляются в сеть.";
    setText("usage-since", since);
  }

  function renderStatusline() {
    const status = state.status || {};
    const env = state.environment || {};
    const usage = state.usage || {};
    const led = $("statusline-led");
    if (led) {
      led.classList.toggle("is-on", Boolean(status.running));
      led.classList.toggle("is-error", Boolean(status.last_error) && !status.running);
    }
    setText("statusline-engine", status.running ? "engine:on" : "engine:off");
    setText(
      "statusline-mode",
      `mode:${status.active_config?.mode || state.settings.mode || "list"}${
        status.active_config?.game_filter || state.settings.game_filter ? "+game" : ""
      }`
    );
    setText(
      "statusline-session",
      `session:${formatUptime(usage.session_seconds || status.uptime_seconds || 0)}`
    );
    setText("statusline-admin", `root:${env.admin ? "yes" : "no"}`);
  }

  // --------------------------------------------------------------- environment
  function updateEnvironment(environment, options = {}) {
    const { render = true } = options;
    if (!environment) return;
    state.environment = environment;
    if (render) renderEnvironment();
  }

  function renderEnvironment() {
    renderBanner();
    renderAdmin();
    renderFileList();
    renderDataPaths();
    renderListCountsFromEnvironment();
    renderStatusline();
  }

  function renderVersion() {
    const version = state.data?.app?.version || "1.1.0";
    setText("app-version", `[v${version}]`);
    setText("settings-version", `v${version}`);
    for (const element of $$(".about-version")) element.textContent = `v${version}`;
    const auto = $("autostart-toggle");
    if (auto && state.data?.app?.task_name) {
      auto.title = `Задача: ${state.data.app.task_name}`;
    }
  }

  function renderAdmin() {
    const env = state.environment;
    const admin = Boolean(env?.admin);
    const pill = $("admin-pill");
    if (pill) {
      pill.textContent = admin ? "ADMIN" : "НЕТ";
      pill.classList.toggle("is-ok", admin);
      pill.classList.toggle("is-fail", !admin);
    }
    setText(
      "admin-note",
      admin ? "Повышенные права получены" : "Нужны права администратора — перезапустите приложение"
    );
    const auto = $("autostart-toggle");
    if (auto) auto.disabled = state.autostartBusy || !admin;
  }

  function renderBanner() {
    const banner = $("engine-banner");
    if (!banner) return;
    const env = state.environment;
    const missingRequired = env?.missing_required || [];
    const missingOptional = env?.missing_optional || [];
    const foreign = env?.foreign_winws || [];
    const lists = env?.lists || {};
    const presetsError = state.presetsError || env?.presets_error;

    let issue = null;
    if (presetsError) {
      issue = {
        danger: true,
        title: "Ошибка в presets.json",
        text: presetsError,
        primary: { label: "Повторить", action: "reload_presets" },
        secondary: { label: "Открыть файл", action: "open_presets" },
      };
    } else if (!env) {
      issue = {
        danger: false,
        title: "Проверка окружения",
        text: "Не удалось получить состояние файлов.",
        primary: { label: "Проверить снова", action: "refresh_env" },
        secondary: null,
      };
    } else if (!env.admin) {
      issue = {
        danger: true,
        title: "Нет прав администратора",
        text: "winws.exe не сможет подключиться к WinDivert. Перезапустите приложение и разрешите UAC.",
        primary: { label: "Настройки", action: "open_settings" },
        secondary: null,
      };
    } else if (missingRequired.length) {
      issue = {
        danger: true,
        title: "Не хватает файлов zapret",
        text: `В папке bin нет: ${missingRequired.join(", ")}. Скопируйте компоненты оригинального zapret.`,
        primary: { label: "Открыть bin", action: "open_bin" },
        secondary: { label: "Проверить снова", action: "refresh_env" },
      };
    } else if (foreign.length) {
      const pids = foreign.map((item) => item.pid).join(", ");
      issue = {
        danger: true,
        title: "Найден другой winws.exe",
        text: `PID ${pids}. Остановите его вручную, чтобы фильтры WinDivert не конфликтовали.`,
        primary: { label: "Проверить снова", action: "refresh_env" },
        secondary: { label: "Открыть bin", action: "open_bin" },
      };
    } else if (lists.general?.present === false || lists.exclude?.present === false) {
      issue = {
        danger: true,
        title: "Не найден файл списка",
        text: "Файлы list-general.txt и list-exclude.txt должны существовать в папке lists.",
        primary: { label: "Открыть lists", action: "open_lists" },
        secondary: { label: "Проверить снова", action: "refresh_env" },
      };
    } else if (missingOptional.length) {
      issue = {
        danger: false,
        title: "Неполный набор .bin",
        text: `Не найдены: ${missingOptional.join(", ")}. Будут использованы встроенные фейки zapret.`,
        primary: { label: "Открыть bin", action: "open_bin" },
        secondary: { label: "Проверить снова", action: "refresh_env" },
      };
    }

    if (!issue) {
      banner.hidden = true;
      state.bannerActions = { primary: null, secondary: null };
      return;
    }

    banner.hidden = false;
    banner.classList.toggle("banner-danger", Boolean(issue.danger));
    setText("banner-title", issue.title);
    setText("banner-text", issue.text);

    const primary = $("banner-check");
    const secondary = $("banner-open");
    state.bannerActions.primary = issue.primary?.action || null;
    state.bannerActions.secondary = issue.secondary?.action || null;

    if (issue.primary) {
      primary.hidden = false;
      primary.textContent = issue.primary.label;
    } else {
      primary.hidden = true;
    }
    if (issue.secondary) {
      secondary.hidden = false;
      secondary.textContent = issue.secondary.label;
    } else {
      secondary.hidden = true;
    }
  }

  function renderFileList() {
    const container = $("file-list");
    if (!container) return;
    container.replaceChildren();
    const env = state.environment;
    if (!env) {
      const empty = document.createElement("p");
      empty.className = "path-note";
      empty.textContent = "Нет данных о файлах.";
      container.appendChild(empty);
      setText("engine-summary", "Проверка недоступна");
      return;
    }

    function addGroup(label, files, optional) {
      if (!files || !files.length) return;
      const group = document.createElement("div");
      group.className = "file-group-label";
      group.textContent = label;
      container.appendChild(group);
      for (const file of files) {
        const row = document.createElement("div");
        row.className = "file-row";
        row.title = file.path || file.name;
        const dot = document.createElement("span");
        dot.className = "file-dot";
        if (file.present) dot.classList.add(optional ? "is-optional" : "is-present");
        if (!file.present) dot.classList.add("is-missing");
        const name = document.createElement("span");
        name.className = "file-name";
        name.textContent = file.name;
        const size = document.createElement("span");
        size.className = "file-size";
        size.textContent = file.present ? formatSize(file.size) : "нет";
        if (!file.present) size.classList.add("is-missing");
        row.append(dot, name, size);
        container.appendChild(row);
      }
    }

    addGroup("Обязательные", env.required || [], false);
    addGroup("Фейковые пакеты · .bin", env.optional || [], true);

    const requiredTotal = (env.required || []).length;
    const requiredPresent = (env.required || []).filter((file) => file.present).length;
    const optionalPresent = (env.optional || []).filter((file) => file.present).length;
    if (requiredPresent === requiredTotal) {
      setText("engine-summary", `Готов к запуску · ${optionalPresent} / ${(env.optional || []).length} .bin`);
    } else {
      setText("engine-summary", `Не хватает ${requiredTotal - requiredPresent} обязательных файлов`);
    }
  }

  function renderDataPaths() {
    const note = $("data-path");
    if (note) {
      note.textContent = state.data?.paths?.data || state.environment?.data_dir || "—";
      note.title = note.textContent;
    }
  }

  function renderListCountsFromEnvironment() {
    if (state.listsLoaded) {
      updateListCountPills();
      return;
    }
    const lists = state.environment?.lists || {};
    setText("count-general-pill", lists.general?.entries ?? 0);
    setText("count-exclude-pill", lists.exclude?.entries ?? 0);
  }

  async function refreshEnvironment(showSuccess = true) {
    if (!state.api || state.envBusy) return;
    state.envBusy = true;
    const button = $("btn-refresh-engine");
    const label = $("btn-refresh-engine-label");
    if (button) button.disabled = true;
    if (label) label.textContent = "Проверка…";
    try {
      const result = await invoke("refresh_environment");
      if (result.ok === false) throw new Error(result.error || "Проверка не удалась");
      state.environment = result;
      renderEnvironment();
      if (showSuccess) showToast("Состояние файлов и процессов обновлено.", "success", "Проверка");
    } catch (error) {
      showToast(error.message || String(error), "error", "Проверка файлов");
    } finally {
      state.envBusy = false;
      if (button) button.disabled = false;
      if (label) label.textContent = "Проверить";
    }
  }

  async function handleBannerAction(which) {
    const action = state.bannerActions[which];
    if (!action) return;
    if (action === "refresh_env") {
      await refreshEnvironment();
    } else if (action === "open_bin") {
      await openFolder("bin");
    } else if (action === "open_lists") {
      await openFolder("lists");
    } else if (action === "open_presets") {
      await openFolder("presets");
    } else if (action === "open_settings") {
      switchTab("settings");
    } else if (action === "reload_presets") {
      await reloadPresets();
    }
  }

  async function openFolder(kind) {
    try {
      const result = await invoke("open_folder", kind);
      if (result.ok === false) throw new Error(result.error || "Не удалось открыть папку");
    } catch (error) {
      showToast(error.message || String(error), "error", "Проводник");
    }
  }

  async function reloadPresets() {
    const button = $("btn-reload-presets");
    if (button) {
      button.disabled = true;
      button.textContent = "Загрузка…";
    }
    try {
      const result = await invoke("reload_presets");
      if (result.ok === false) {
        state.presetsError = result.error || "Не удалось загрузить presets.json";
        state.data.presets_error = state.presetsError;
        renderBanner();
        showToast(state.presetsError, "error", "Пресеты");
        return;
      }
      state.presets = Array.isArray(result.presets) ? result.presets : [];
      state.presetsError = null;
      if (state.data) state.data.presets_error = null;
      state.presetsUpdated = result.updated || "";
      const statusResult = await invoke("get_status");
      if (statusResult.ok !== false) {
        state.settings = { ...(statusResult.settings || state.settings) };
        if (statusResult.status) state.status = statusResult.status;
        if (statusResult.usage) applyUsage(statusResult.usage);
      }
      populatePresetSelect();
      applySettingsToControls();
      renderBanner();
      renderStatus();
      scheduleCommandPreview();
      showToast(`Загружено стратегий: ${state.presets.length}.`, "success", "Пресеты обновлены");
    } catch (error) {
      showToast(error.message || String(error), "error", "Пресеты");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "Обновить presets";
      }
    }
  }

  // --------------------------------------------------------------- diagnostics
  function setServiceState(service, status, meta, tooltip) {
    const item = document.querySelector(`.service-item[data-service="${service}"]`);
    if (!item) return;
    item.classList.remove("state-ok", "state-fail", "state-busy");
    const metaElement = item.querySelector(".service-meta");
    if (status) item.classList.add(`state-${status}`);
    if (metaElement) metaElement.textContent = meta || "—";
    const dot = item.querySelector(".status-dot");
    if (dot) dot.className = "status-dot";
    item.title = tooltip || "";
  }

  function renderCheckNeutral() {
    for (const id of SERVICE_IDS) setServiceState(id, null, "—", "");
    setText("diag-foot", "Проверка выполняется напрямую, без системного прокси.");
    $("diag-foot")?.classList.remove("is-warning", "is-success");
    setText("btn-test-label", "Тест");
    setText("btn-autotune-label", "Подбор");
    $("btn-test")?.classList.remove("is-loading");
    $("btn-test")?.removeAttribute("aria-busy");
    $("btn-autotune")?.classList.remove("is-loading");
    $("btn-autotune")?.removeAttribute("aria-busy");
  }

  function renderServiceResults(result, wasRunning, footerOverride = null) {
    const services = Array.isArray(result.services) ? result.services : [];
    for (const service of services) {
      const ok = Boolean(service.ok);
      const meta =
        ok && service.latency_ms != null ? `${service.latency_ms} мс` : service.error || "Ошибка";
      const detail = service.detail ? ` — ${service.detail}` : "";
      const http = service.status ? `HTTP ${service.status}` : "";
      setServiceState(service.id, ok ? "ok" : "fail", meta, `${http}${detail}`.trim());
    }

    const total = services.length || result.total || SERVICE_IDS.length;
    const reachable = services.filter((service) => service.ok).length;
    const latencies = services
      .filter((service) => service.ok && Number.isFinite(Number(service.latency_ms)))
      .map((service) => Number(service.latency_ms));
    const averageLatency = latencies.length
      ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length)
      : null;

    const foot = $("diag-foot");
    if (foot) {
      foot.classList.remove("is-warning", "is-success");
      if (footerOverride) {
        foot.textContent = footerOverride;
        if (reachable === total && reachable > 0) foot.classList.add("is-success");
        else foot.classList.add("is-warning");
      } else {
        const suffix = wasRunning ? "" : " Обход был выключен.";
        if (reachable === total && total > 0) {
          foot.classList.add("is-success");
          foot.textContent = `Доступны все сервисы · ${formatCheckTime(result.checked_at)}.${suffix}`;
        } else if (reachable > 0) {
          foot.classList.add("is-warning");
          foot.textContent = `Доступно ${reachable} из ${total}. Попробуйте другой пресет.`;
        } else {
          foot.classList.add("is-warning");
          foot.textContent = "Сервисы недоступны. Проверьте соединение и выбранную стратегию.";
        }
      }
    }
    return { total, reachable, averageLatency };
  }

  async function runConnectivityCheck() {
    if (state.testing || state.operation || !state.api) return;
    state.testing = true;
    const button = $("btn-test");
    const wasRunning = isRunning();
    button.disabled = true;
    button.classList.add("is-loading");
    button.setAttribute("aria-busy", "true");
    setText("btn-test-label", "Тест…");
    for (const id of SERVICE_IDS) setServiceState(id, "busy", "…", "");
    setText("diag-foot", "Проверяем HTTPS-ответы, таймаут 3 с…");
    $("diag-foot")?.classList.remove("is-warning", "is-success");
    renderStatus();

    try {
      const result = await invoke("check_connectivity");
      if (result.ok === false) throw new Error(result.error || "Проверка не удалась");
      const summary = renderServiceResults(result, wasRunning);

      if (summary.reachable === 0) {
        showToast("Ни один тестовый сервис не ответил.", "warning", "Проверка доступа");
      } else if (summary.reachable < summary.total) {
        showToast(
          "Часть сервисов недоступна — возможно, DPI блокирует соединение.",
          "warning",
          "Проверка доступа"
        );
      }
    } catch (error) {
      showToast(error.message || String(error), "error", "Проверка доступа");
      for (const id of SERVICE_IDS) setServiceState(id, "fail", "Ошибка", "");
      setText("diag-foot", "Не удалось выполнить проверку.");
    } finally {
      state.testing = false;
      button.classList.remove("is-loading");
      button.removeAttribute("aria-busy");
      setText("btn-test-label", "Тест");
      renderStatus();
    }
  }

  function environmentReadyForAuto() {
    const env = state.environment;
    if (!env) {
      showToast("Окружение ещё не проверено.", "warning", "Автоподбор");
      return false;
    }
    if (!env.admin) {
      showToast("Для запуска winws нужны права администратора.", "error", "Автоподбор");
      return false;
    }
    const missing = env.missing_required || [];
    if (missing.length) {
      showToast(`Нет файлов: ${missing.join(", ")}. Откройте папку bin.`, "error", "Автоподбор");
      return false;
    }
    if (env.foreign_winws?.length) {
      showToast("Остановите другой процесс winws.exe и повторите.", "error", "Автоподбор");
      return false;
    }
    return true;
  }

  async function runAutotune() {
    if (state.testing || state.operation || !state.api) return;
    if (!environmentReadyForAuto()) return;
    if (!state.presets.length) {
      showToast("Нет доступных стратегий. Проверьте presets.json.", "error", "Автоподбор");
      return;
    }

    const mode = state.settings.mode;
    const gameFilter = Boolean(state.settings.game_filter);
    const originalPreset = state.settings.preset_id;
    const results = [];
    const total = state.presets.length;

    state.operation = "autotune";
    state.autotuneStep = "";
    renderStatus();
    setText("diag-foot", "Автоподбор: проверяем стратегии по очереди…");
    $("diag-foot")?.classList.remove("is-warning", "is-success");

    try {
      for (let index = 0; index < total; index += 1) {
        const preset = state.presets[index];
        state.autotuneStep = `${index + 1}/${total} · ${preset.name}`;
        renderStatus();
        setText(
          "diag-foot",
          `Автоподбор ${index + 1}/${total}: ${preset.name} — запускаем и проверяем…`
        );
        for (const id of SERVICE_IDS) setServiceState(id, "busy", "…", "");

        let checkResult = null;
        try {
          const startResult = await invoke("restart_bypass", preset.id, mode, gameFilter);
          if (startResult.status) state.status = startResult.status;
          if (startResult.usage) applyUsage(startResult.usage);
          if (startResult.environment) updateEnvironment(startResult.environment, { render: false });
          if (!startResult.ok) {
            throw new Error(startResult.error || "winws не запустился");
          }
          await delay(1500);
          checkResult = await invoke("check_connectivity");
          if (checkResult.ok === false) {
            throw new Error(checkResult.error || "Проверка не удалась");
          }
          const summary = renderServiceResults(checkResult, true);
          const latency = summary.averageLatency != null ? `${summary.averageLatency} мс` : "—";
          setText(
            "diag-foot",
            `Автоподбор ${index + 1}/${total}: ${preset.name} · ${summary.reachable}/${summary.total} · ${latency}`
          );
          results.push({
            preset,
            reachable: summary.reachable,
            total: summary.total,
            averageLatency: summary.averageLatency,
            check: checkResult,
            error: null,
          });
        } catch (error) {
          results.push({
            preset,
            reachable: -1,
            total: SERVICE_IDS.length,
            averageLatency: null,
            check: null,
            error: error.message || String(error),
          });
          setText(
            "diag-foot",
            `Автоподбор ${index + 1}/${total}: ${preset.name} — ошибка запуска`
          );
        }
      }

      const ranked = results
        .filter((item) => item.reachable >= 0)
        .sort(
          (a, b) =>
            b.reachable - a.reachable ||
            (a.averageLatency ?? Number.MAX_SAFE_INTEGER) -
              (b.averageLatency ?? Number.MAX_SAFE_INTEGER)
        );
      const best = ranked[0] || null;
      state.autotuneStep = "";

      if (best && best.reachable > 0) {
        try {
          const update = await invoke("update_setting", "preset_id", best.preset.id);
          if (update.ok !== false) state.settings = { ...(update.settings || state.settings) };
        } catch {
          // Continue: restart_bypass also stores the selected preset.
        }
        const finalResult = await invoke("restart_bypass", best.preset.id, mode, gameFilter);
        if (finalResult.status) state.status = finalResult.status;
        if (finalResult.usage) applyUsage(finalResult.usage);
        if (finalResult.environment) {
          updateEnvironment(finalResult.environment, { render: false });
        }
        if (finalResult.ok === false) {
          throw new Error(finalResult.error || "Лучший пресет не запустился повторно");
        }
        state.settings.preset_id = best.preset.id;
        const latency =
          best.averageLatency != null ? `${best.averageLatency} мс` : "нет данных";
        renderServiceResults(
          best.check,
          true,
          `Лучшая стратегия: ${best.preset.name} · ${best.reachable}/${best.total} · ${latency}`
        );
        showToast(
          `Выбрана ${best.preset.name} · ${best.preset.label}: ${best.reachable}/${best.total}, ${latency}.`,
          "success",
          "Автоподбор завершён"
        );
      } else {
        const stopped = await invoke("stop_bypass");
        if (stopped.status) state.status = stopped.status;
        if (stopped.usage) applyUsage(stopped.usage);
        if (stopped.environment) {
          updateEnvironment(stopped.environment, { render: false });
        }
        try {
          const restore = await invoke("update_setting", "preset_id", originalPreset);
          if (restore.ok !== false) state.settings = { ...(restore.settings || state.settings) };
          else state.settings.preset_id = originalPreset;
        } catch {
          state.settings.preset_id = originalPreset;
        }
        for (const id of SERVICE_IDS) setServiceState(id, "fail", "Ошибка", "");
        setText(
          "diag-foot",
          "Автоподбор не нашёл рабочую стратегию. Проверьте DNS, bin и доступность сети."
        );
        $("diag-foot")?.classList.add("is-warning");
        showToast(
          "Ни одна стратегия не дала доступ к тестовым сервисам.",
          "warning",
          "Автоподбор"
        );
      }
    } catch (error) {
      showToast(error.message || String(error), "error", "Автоподбор");
      try {
        const stopped = await invoke("stop_bypass");
        if (stopped.status) state.status = stopped.status;
        if (stopped.usage) applyUsage(stopped.usage);
      } catch {
        // Ignore cleanup errors; the manager still owns the lifecycle.
      }
      try {
        const restore = await invoke("update_setting", "preset_id", originalPreset);
        if (restore.ok !== false) state.settings = { ...(restore.settings || state.settings) };
        else state.settings.preset_id = originalPreset;
      } catch {
        state.settings.preset_id = originalPreset;
      }
      setText("diag-foot", "Автоподбор прерван из-за ошибки.");
      $("diag-foot")?.classList.add("is-warning");
    } finally {
      state.operation = null;
      state.autotuneStep = "";
      state.previousRunning = isRunning();
      applySettingsToControls();
      renderEnvironment();
      renderStatus();
      scheduleCommandPreview();
      if (state.activeTab === "logs") void fetchLogs();
    }
  }

  // ----------------------------------------------------------------- builtins
  async function copyText(text, title = "Скопировано") {
    if (!text) {
      showToast("Копировать нечего.", "info", "Буфер обмена");
      return;
    }
    try {
      const result = await invoke("copy_text", text);
      if (result.ok === false) throw new Error(result.error || "Буфер обмена недоступен");
      showToast("Текст помещён в буфер обмена.", "success", title);
      return;
    } catch (error) {
      try {
        await navigator.clipboard.writeText(text);
        showToast("Текст помещён в буфер обмена.", "success", title);
        return;
      } catch {
        showToast(error.message || String(error), "error", "Буфер обмена");
      }
    }
  }

  // --------------------------------------------------------------------- lists
  async function ensureListsLoaded(force = false) {
    if (!state.api) return;
    if (state.listsLoaded && !force) return;
    if (state.listsLoading) return;
    state.listsLoading = true;
    const saveState = $("list-save-state");
    if (saveState) {
      saveState.textContent = "Загрузка…";
      saveState.className = "save-state";
    }
    try {
      const result = await invoke("read_lists");
      if (!result || !result.lists) throw new Error(result?.error || "Не удалось прочитать списки");
      state.lists = result.lists;
      for (const key of ["general", "exclude"]) {
        const entry = result.lists[key] || { content: "" };
        state.drafts[key] = entry.content || "";
        state.originals[key] = entry.content || "";
        state.listsDirty[key] = false;
      }
      state.listsLoaded = true;
      renderListEditor();
      updateListCountPills();
      if (result.ok === false) {
        showToast("Некоторые списки не удалось прочитать. Подробности показаны в редакторе.", "warning", "Списки");
      }
    } catch (error) {
      showToast(error.message || String(error), "error", "Списки");
      if (saveState) {
        saveState.textContent = "Ошибка";
        saveState.className = "save-state is-error";
      }
    } finally {
      state.listsLoading = false;
    }
  }

  function storeEditorDraft() {
    const editor = $("list-editor");
    if (!editor || !state.listsLoaded) return;
    state.drafts[state.listKey] = editor.value;
    state.listsDirty[state.listKey] = editor.value !== state.originals[state.listKey];
  }

  function switchListTab(key, options = {}) {
    const { focus = false } = options;
    if (!["general", "exclude"].includes(key)) return;
    storeEditorDraft();
    state.listKey = key;
    for (const button of $$(".mini-tab")) {
      const active = button.dataset.list === key;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    }
    renderListEditor();
    if (focus) $("list-editor")?.focus();
  }

  function renderListEditor() {
    const editor = $("list-editor");
    if (!editor) return;
    const meta = LIST_META[state.listKey];
    const entry = state.lists[state.listKey] || {};
    const content = state.drafts[state.listKey] || "";
    setText("list-title", meta.title);
    setText("list-filename", entry.filename || meta.filename);
    setText(
      "list-hint-text",
      state.listKey === "exclude"
        ? "Строка ru исключает всю зону .ru, xn--p1ai — .рф. Исключения действуют по SNI/Host. Список перечитывается автоматически."
        : "По одному домену на строку. Строки с # — комментарии. Список перечитывается winws автоматически."
    );
    const fileLabel = $("list-filename");
    if (fileLabel) fileLabel.title = entry.path || "";
    editor.value = content;
    editor.disabled = !state.listsLoaded;
    editor.placeholder =
      state.listKey === "exclude"
        ? "ru\nxn--p1ai\ngosuslugi.ru\nsberbank.ru"
        : "youtube.com\ndiscord.com\ngooglevideo.com\ncloudflare.com";
    updateListMetaUI();
    const saveState = $("list-save-state");
    if (saveState) {
      saveState.textContent = state.listsLoaded ? (state.listsDirty[state.listKey] ? "Не сохранено" : "Сохранено") : "Загрузка…";
      saveState.className = "save-state";
      if (state.listsDirty[state.listKey]) saveState.classList.add("is-dirty");
      else if (state.listsLoaded) saveState.classList.add("is-saved");
    }
    setHidden($("btn-save-list"), false);
    const saveButton = $("btn-save-list");
    if (saveButton) saveButton.disabled = !state.listsLoaded || !state.listsDirty[state.listKey];
  }

  function updateListMetaUI() {
    const current = state.drafts[state.listKey] || "";
    const count = countDomains(current);
    const lines = current ? current.split(/\r?\n/).length : 0;
    setText(
      "list-stats",
      `${count} ${plural(count, "домен", "домена", "доменов")} · ${lines} ${plural(lines, "строка", "строки", "строк")}`
    );
    updateListCountPills();
  }

  function updateListCountPills() {
    const general = state.listsLoaded
      ? countDomains(state.drafts.general)
      : state.environment?.lists?.general?.entries || 0;
    const exclude = state.listsLoaded
      ? countDomains(state.drafts.exclude)
      : state.environment?.lists?.exclude?.entries || 0;
    setText("count-general-pill", general);
    setText("count-exclude-pill", exclude);
  }

  function onListInput() {
    if (!state.listsLoaded) return;
    const editor = $("list-editor");
    if (!editor) return;
    state.drafts[state.listKey] = editor.value;
    state.listsDirty[state.listKey] = editor.value !== state.originals[state.listKey];
    updateListMetaUI();
    const saveState = $("list-save-state");
    if (saveState) {
      saveState.textContent = state.listsDirty[state.listKey] ? "Не сохранено" : "Сохранено";
      saveState.className = "save-state";
      saveState.classList.add(state.listsDirty[state.listKey] ? "is-dirty" : "is-saved");
    }
    const saveButton = $("btn-save-list");
    if (saveButton) saveButton.disabled = !state.listsDirty[state.listKey];
  }

  async function saveCurrentList() {
    if (!state.listsLoaded) return;
    const key = state.listKey;
    storeEditorDraft();
    if (!state.listsDirty[key]) return;
    let text = state.drafts[key].replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    if (text && !text.endsWith("\n")) text += "\n";
    const button = $("btn-save-list");
    if (button) {
      button.disabled = true;
      button.classList.add("is-loading");
    }
    try {
      const result = await invoke("save_list", key, text);
      if (result.ok === false) throw new Error(result.error || "Не удалось сохранить список");
      state.drafts[key] = text;
      state.originals[key] = text;
      state.listsDirty[key] = false;
      const editor = $("list-editor");
      if (editor && state.listKey === key) editor.value = text;
      renderListEditor();
      updateListCountPills();
      const count = result.entries ?? countDomains(text);
      showToast(
        `Сохранено ${count} ${plural(count, "домен", "домена", "доменов")}. winws перечитает файл автоматически.`,
        "success",
        "Список сохранён"
      );
      if (state.environment?.lists?.[key]) {
        state.environment.lists[key].entries = count;
      }
    } catch (error) {
      showToast(error.message || String(error), "error", "Сохранение списка");
      const saveState = $("list-save-state");
      if (saveState) {
        saveState.textContent = "Ошибка";
        saveState.className = "save-state is-error";
      }
    } finally {
      if (button) button.classList.remove("is-loading");
      renderListEditor();
    }
  }

  function handleListTabKeys(event) {
    const tabs = $$(".mini-tab");
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex === -1) return;
    let nextIndex = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (nextIndex == null) return;
    event.preventDefault();
    tabs[nextIndex].focus();
    switchListTab(tabs[nextIndex].dataset.list);
  }

  // ---------------------------------------------------------------------- logs
  async function fetchLogs() {
    if (!state.api || state.logInFlight) return;
    state.logInFlight = true;
    try {
      const result = await invoke("get_logs", state.logCursor);
      if (!result || result.ok === false) return;
      const entries = Array.isArray(result.entries) ? result.entries : [];
      if (entries.length) appendLogEntries(entries);
      if (typeof result.next_seq === "number") {
        state.logCursor = result.next_seq;
      }
    } catch {
      // Logs are best-effort; the next poll retries.
    } finally {
      state.logInFlight = false;
    }
  }

  function appendLogEntries(entries) {
    const view = $("log-view");
    const lines = $("log-lines");
    if (!view || !lines) return;
    const atBottom =
      state.logEntries.length === 0 ||
      view.scrollHeight - view.scrollTop - view.clientHeight < 36;
    const fragment = document.createDocumentFragment();

    for (const entry of entries) {
      state.logEntries.push(entry);
      const row = document.createElement("div");
      const kind = ["system", "command", "error"].includes(entry.kind) ? entry.kind : "output";
      row.className = `log-line kind-${kind}`;
      const time = document.createElement("span");
      time.className = "log-time";
      time.textContent = entry.time || "";
      const text = document.createElement("span");
      text.className = "log-msg";
      text.textContent = entry.text || "";
      row.append(time, text);
      fragment.appendChild(row);
    }

    if (state.logEntries.length > 2500) {
      state.logEntries = state.logEntries.slice(-2500);
      while (lines.children.length + fragment.children.length > 2500) {
        lines.firstElementChild?.remove();
      }
    }
    lines.appendChild(fragment);

    const empty = $("log-empty");
    if (empty) empty.hidden = state.logEntries.length > 0;
    updateLogCounter();
    if (atBottom) scrollLogsToBottom(false);
    else updateScrollLatestVisibility();
  }

  function updateLogCounter() {
    const count = state.logEntries.length;
    setText("log-count", `${count} ${plural(count, "строка", "строки", "строк")}`);
  }

  function scrollLogsToBottom(smooth = true) {
    const view = $("log-view");
    if (!view) return;
    view.scrollTo({ top: view.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    state.logPinned = true;
    const latest = $("btn-scroll-latest");
    if (latest) latest.hidden = true;
  }

  function updateScrollLatestVisibility() {
    const latest = $("btn-scroll-latest");
    const view = $("log-view");
    if (!latest || !view) return;
    const away = view.scrollHeight - view.scrollTop - view.clientHeight > 42;
    latest.hidden = !away;
    state.logPinned = !away;
  }

  function clearLogViewLocal() {
    const lines = $("log-lines");
    if (lines) lines.replaceChildren();
    state.logEntries = [];
    state.logsCursor = 0;
    updateLogCounter();
    const empty = $("log-empty");
    if (empty) empty.hidden = false;
    const latest = $("btn-scroll-latest");
    if (latest) latest.hidden = true;
  }

  async function clearLogs() {
    try {
      const result = await invoke("clear_logs");
      if (result.ok === false) throw new Error(result.error || "Не удалось очистить логи");
      clearLogViewLocal();
      showToast("Журнал интерфейса очищен. winws продолжает работу.", "success", "Логи");
    } catch (error) {
      showToast(error.message || String(error), "error", "Логи");
    }
  }

  async function copyLogs() {
    if (!state.logEntries.length) {
      showToast("Журнал пуст.", "info", "Логи");
      return;
    }
    const text = state.logEntries
      .slice(-2500)
      .map((entry) => `${entry.time || ""}  ${entry.text || ""}`)
      .join("\n");
    await copyText(text, "Логи скопированы");
  }

  function renderCommand() {
    const pre = $("command-line");
    if (!pre) return;
    const status = state.status || {};
    let text = "";
    if (isRunning() && status.command_line) {
      text = status.command_line;
    } else if (state.previewCommand) {
      text = state.previewCommand;
    } else if (status.command_line && status.last_exit_code != null) {
      text = status.command_line;
    }

    state.currentCommand = text || "";
    pre.textContent =
      state.currentCommand ||
      (state.previewError
        ? `Предпросмотр недоступен: ${state.previewError}`
        : "Запустите обход, чтобы увидеть команду winws.exe.");
    const button = $("btn-copy-command");
    if (button) button.disabled = !state.currentCommand;
  }

  function scheduleCommandPreview() {
    if (!state.api || !state.presets.length) return;
    if (state.previewTimer) window.clearTimeout(state.previewTimer);
    state.previewTimer = window.setTimeout(async () => {
      try {
        const result = await invoke(
          "command_preview",
          state.settings.preset_id,
          state.settings.mode,
          Boolean(state.settings.game_filter)
        );
        if (result.ok === false) {
          state.previewError = result.error || "Неизвестная ошибка";
          state.previewCommand = "";
        } else {
          state.previewError = null;
          state.previewCommand = result.command_line || "";
        }
      } catch (error) {
        state.previewError = error.message || String(error);
        state.previewCommand = "";
      }
      renderCommand();
    }, 180);
  }

  // ------------------------------------------------------------------- polling
  function startPolling() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = window.setTimeout(pollTick, 1100);
  }

  function schedulePoll(delay = 1200) {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = window.setTimeout(pollTick, delay);
  }

  async function pollTick() {
    if (!state.ready || !state.api) return;
    if (document.hidden) {
      schedulePoll(3000);
      return;
    }
    if (state.pollInFlight) {
      schedulePoll(1200);
      return;
    }
    state.pollInFlight = true;
    try {
      if (!state.operation) {
        const result = await invoke("get_status");
        if (result.ok !== false) {
          if (result.status) applyStatus(result.status);
          if (result.usage) applyUsage(result.usage);
        }
      }
      if (state.activeTab === "logs" && !state.logInFlight) {
        await fetchLogs();
      }
    } catch {
      // Keep the UI responsive if the bridge or engine is briefly unavailable.
    } finally {
      state.pollInFlight = false;
      schedulePoll(1200);
    }
  }

  // ------------------------------------------------------------------ controls
  function wireEvents() {
    $("#btn-minimize")?.addEventListener("click", () => {
      void invoke("window_minimize").catch((error) =>
        showToast(error.message || String(error), "error", "Окно")
      );
    });

    $("#btn-window-close")?.addEventListener("click", () => {
      void invoke("window_close").catch((error) =>
        showToast(error.message || String(error), "error", "Окно")
      );
    });

    const tablist = document.querySelector(".tabs");
    tablist?.addEventListener("keydown", handleTabKeys);
    for (const tab of $$(".tab")) {
      tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    }

    $("preset-select")?.addEventListener("change", () => void onPresetChanged());
    for (const button of $$("#mode-seg .seg-btn")) {
      button.addEventListener("click", () => void onModeClicked(button));
    }
    $("game-filter")?.addEventListener("change", (event) => void onGameChanged(event));
    $("btn-toggle")?.addEventListener("click", () => void toggleBypass());
    $("btn-reapply")?.addEventListener("click", () => void reapplySettings());
    $("btn-test")?.addEventListener("click", () => void runConnectivityCheck());
    $("btn-autotune")?.addEventListener("click", () => void runAutotune());

    $("banner-check")?.addEventListener("click", () => void handleBannerAction("primary"));
    $("banner-open")?.addEventListener("click", () => void handleBannerAction("secondary"));

    $("btn-open-lists-folder")?.addEventListener("click", () => void openFolder("lists"));
    $("btn-open-bin")?.addEventListener("click", () => void openFolder("bin"));
    $("btn-open-data")?.addEventListener("click", () => void openFolder("data"));
    $("btn-open-presets-file")?.addEventListener("click", () => void openFolder("presets"));
    $("btn-refresh-engine")?.addEventListener("click", () => void refreshEnvironment());
    $("btn-reload-presets")?.addEventListener("click", () => void reloadPresets());
    $("btn-link-zapret")?.addEventListener("click", () => void openExternal("zapret"));
    $("btn-link-bundle")?.addEventListener("click", () => void openExternal("bundle"));

    const autostart = $("autostart-toggle");
    autostart?.addEventListener("change", (event) => void onAutostartChanged(event));
    const tray = $("tray-toggle");
    tray?.addEventListener("change", (event) => void onTraySettingChanged(event));

    for (const button of $$(".mini-tab")) {
      button.addEventListener("click", () => switchListTab(button.dataset.list));
    }
    document.querySelector(".mini-tabs")?.addEventListener("keydown", handleListTabKeys);
    $("list-editor")?.addEventListener("input", onListInput);
    $("btn-save-list")?.addEventListener("click", () => void saveCurrentList());

    $("btn-copy-logs")?.addEventListener("click", () => void copyLogs());
    $("btn-clear-logs")?.addEventListener("click", () => void clearLogs());
    $("btn-scroll-latest")?.addEventListener("click", () => scrollLogsToBottom(true));
    $("btn-copy-command")?.addEventListener("click", () => {
      if (state.currentCommand) void copyText(state.currentCommand, "Команда скопирована");
    });

    const logView = $("log-view");
    logView?.addEventListener("scroll", updateScrollLatestVisibility, { passive: true });

    $("btn-retry-bootstrap")?.addEventListener("click", () => {
      if (!state.api) tryBridge();
      else void beginBootstrap();
    });

    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        if (state.activeTab !== "lists") return;
        event.preventDefault();
        void saveCurrentList();
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        schedulePoll(150);
        if (state.activeTab === "logs") void fetchLogs();
      }
    });

    window.zapretOnShow = () => {
      if (!state.ready) return;
      schedulePoll(80);
      if (state.activeTab === "logs") void fetchLogs();
    };
  }

  async function onAutostartChanged(event) {
    const input = event.target;
    const desired = Boolean(input.checked);
    if (state.autostartBusy) return;
    state.autostartBusy = true;
    setSwitchBusy(input, true);
    try {
      const result = await invoke("set_autostart", desired);
      if (result.ok === false) {
        state.autostart = Boolean(result.autostart);
        input.checked = state.autostart;
        showToast(result.error || "Не удалось изменить автозапуск", "error", "Автозапуск");
      } else {
        state.autostart = Boolean(result.autostart);
        input.checked = state.autostart;
        if (state.autostart) {
          showToast("Задача планировщика создана. Приложение будет запускаться при входе в Windows.", "success", "Автозапуск включён");
        } else {
          showToast("Задача автозапуска удалена.", "success", "Автозапуск выключен");
        }
      }
    } catch (error) {
      input.checked = state.autostart;
      showToast(error.message || String(error), "error", "Автозапуск");
    } finally {
      state.autostartBusy = false;
      setSwitchBusy(input, false);
    }
  }

  async function onTraySettingChanged(event) {
    const input = event.target;
    const previous = Boolean(state.settings.minimize_to_tray);
    const desired = Boolean(input.checked);
    input.disabled = true;
    state.settings.minimize_to_tray = desired;
    try {
      const result = await invoke("update_setting", "minimize_to_tray", desired);
      if (result.ok === false) throw new Error(result.error || "Настройка не сохранена");
      state.settings = { ...(result.settings || state.settings) };
    } catch (error) {
      state.settings.minimize_to_tray = previous;
      input.checked = previous;
      showToast(error.message || String(error), "error", "Настройки");
    } finally {
      input.disabled = false;
    }
  }

  async function openExternal(key) {
    try {
      const result = await invoke("open_link", key);
      if (result.ok === false) throw new Error(result.error || "Ссылка недоступна");
    } catch (error) {
      showToast(error.message || String(error), "error", "Ссылка");
    }
  }

  // --------------------------------------------------------------------- boot
  function boot() {
    const firstRun = !state.wired;
    if (firstRun) {
      state.wired = true;
      wireEvents();
    }
    if (document.readyState === "loading") {
      if (firstRun) document.addEventListener("DOMContentLoaded", boot, { once: true });
      return;
    }
    if (state.uiStarted) return;
    state.uiStarted = true;
    tryBridge();
    window.setTimeout(() => {
      const fatalVisible = !$("fatal-overlay")?.hidden;
      if (!state.ready && !state.bootInFlight && !fatalVisible) {
        showFatal(
          "Интерфейс загружен, но локальный API не отвечает. Запустите Zapret RU через main.py или собранный exe."
        );
      }
    }, 6500);
  }

  window.addEventListener("pywebviewready", tryBridge);
  boot();
})();
