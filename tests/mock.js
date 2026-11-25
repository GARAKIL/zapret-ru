/* Development-only mock of the pywebview bridge. Not included in builds. */
(() => {
  "use strict";
  const presets = [
    { id: "smart", name: "Умный", label: "SNI Split · QUIC → TCP", badge: "Рекомендуется", description: "Разрезает TLS ClientHello внутри имени сайта и отключает QUIC, чтобы браузеры и приложения шли по TCP.", caution: null, split: "sni", block_quic: true },
    { id: "split1", name: "Быстрый", label: "Split 1 · QUIC → TCP", badge: "Лёгкий", description: "Делит первый пакет на 1 байт. Минимальное вмешательство.", caution: null, split: 1, block_quic: true },
    { id: "split2", name: "Ровный", label: "Split 2 · QUIC → TCP", badge: "Баланс", description: "Делит первый пакет на 2 байта.", caution: null, split: 2, block_quic: true },
    { id: "split4", name: "Глубокий", label: "Split 4 · QUIC → TCP", badge: "Сложные сети", description: "Делит первый пакет на 4 байта. Для мобильного интернета.", caution: "Некоторые приложения с обязательным QUIC могут работать медленнее.", split: 4, block_quic: true },
    { id: "tcp_only", name: "Без QUIC-фильтра", label: "SNI Split · QUIC разрешён", badge: "Для приложений", description: "SNI Split без блокировки UDP 443.", caution: "Если провайдер блокирует QUIC, сайты могут не открываться.", split: "sni", block_quic: false }
  ];

  const driverDir = "C:\\Users\\demo\\AppData\\Local\\Temp\\onefile_demo\\pydivert\\windivert_dll";
  const required = [
    { name: "WinDivert64.dll", present: true, size: 47616, path: `${driverDir}\\WinDivert64.dll` },
    { name: "WinDivert64.sys", present: true, size: 94144, path: `${driverDir}\\WinDivert64.sys` }
  ];

  const env = {
    admin: true,
    frozen: true,
    arch: "AMD64",
    engine: "native",
    engine_name: "Zapret RU Engine",
    engine_version: "4.0.1",
    engine_error: null,
    driver_ready: true,
    data_dir: "C:\\Users\\demo\\AppData\\Local\\ZapretRU",
    lists_dir: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists",
    required,
    optional: [],
    missing_required: [],
    missing_optional: [],
    foreign_winws: [],
    lists: {
      general: { path: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-general.txt", present: true, size: 1510, modified: null, entries: 145 },
      exclude: { path: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-exclude.txt", present: true, size: 948, modified: null, entries: 72 }
    },
    ready: true,
    checked_at: Date.now() / 1000,
    session: { admin: true, manager_running: false }
  };

  const settings = { preset_id: "smart", mode: "global", game_filter: false, block_quic: true, minimize_to_tray: true, autostart: false, last_tab: "home" };
  const usage = {
    app_launches: 42,
    bypass_sessions: 18,
    bypass_seconds: 3720,
    launcher_seconds: 5400,
    session_seconds: 128,
    active_bypass_seconds: 0,
    first_seen: Date.now() / 1000 - 86400 * 12,
    last_seen: Date.now() / 1000,
    local_only: true
  };
  const status = {
    running: false,
    pid: null,
    uptime_seconds: 0,
    started_at: null,
    last_exit_code: null,
    last_error: null,
    active_config: {},
    command: ["Умный: split SNI · QUIC → TCP · все программы"],
    command_line: "Умный: split SNI · QUIC → TCP · все программы",
    executable: "встроенный движок",
    engine: "native",
    profile_id: "smart",
    profile_name: "Умный",
    strategy: "sni",
    block_quic: true,
    stats: { packets: 0, split_packets: 0, quic_dropped: 0, passed: 0 },
    log_seq: 0
  };

  const lists = {
    general: {
      content: "youtube.com\nyoutu.be\nwww.youtube.com\ngooglevideo.com\nytimgg.com\ndiscord.com\ndiscord.gg\ndiscordapp.net\ncloudflare.com\ncloudflare-dns.com\nx.com\ntwitter.com\nt.co\ninstagram.com\nfacebook.com\nrutracker.org\nsoundcloud.com\nsndcdn.com\ntwitch.tv\nspotify.com\nsteampowered.com\nepicgames.com\nriotgames.com\n",
      title: "Список обхода",
      filename: "list-general.txt",
      path: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-general.txt",
      missing: false,
      entries: 145
    },
    exclude: {
      content: "ru\nxn--p1ai\ngosuslugi.ru\nnalog.ru\nsberbank.ru\nsber.ru\ntbank.ru\nvtb.ru\ngazprombank.ru\nalfabank.ru\nyandex.ru\nya.ru\nmail.ru\nvk.com\nok.ru\nozon.ru\nwildberries.ru\navito.ru\n",
      title: "Список исключений",
      filename: "list-exclude.txt",
      path: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-exclude.txt",
      missing: false,
      entries: 72
    }
  };

  const logs = [
    { seq: 1, time: "21:14:02", text: "Запуск встроенного движка: Умный: split SNI, QUIC off, global", kind: "system" },
    { seq: 2, time: "21:14:02", text: "WinDivert подключён. Слушаем TCP 80/443 и блокируем QUIC/UDP 443.", kind: "system" },
    { seq: 3, time: "21:14:03", text: "Списки обновлены: 145 доменов в обходе, 72 в исключениях.", kind: "system" },
    { seq: 4, time: "21:14:04", text: "TLS ClientHello: split внутри SNI youtube.com", kind: "output" },
    { seq: 5, time: "21:14:05", text: "Статистика: 214 пакетов, 8 split, 3 QUIC drop", kind: "output" }
  ];

  function commandPreview() {
    return "Умный: split SNI · QUIC → TCP · все программы";
  }

  function makeRunning() {
    status.running = true;
    status.uptime_seconds = 372;
    status.started_at = Date.now() / 1000 - 372;
    status.active_config = {
      preset_id: settings.preset_id,
      preset_name: "Умный",
      preset_label: "SNI Split · QUIC → TCP",
      mode: settings.mode,
      game_filter: settings.game_filter,
      split: "sni",
      block_quic: Boolean(settings.block_quic),
      engine: "native"
    };
    status.profile_id = settings.preset_id;
    status.profile_name = "Умный";
    status.strategy = "sni";
    status.block_quic = Boolean(settings.block_quic);
    status.stats = { packets: 2148, split_packets: 38, quic_dropped: 12, passed: 1917 };
    env.session.manager_running = true;
  }

  function makeStopped() {
    status.running = false;
    status.uptime_seconds = 0;
    status.started_at = null;
    status.active_config = {};
    status.stats = { packets: 0, split_packets: 0, quic_dropped: 0, passed: 0 };
    env.session.manager_running = false;
  }

  const api = {
    bootstrap: async () => ({
      ok: true,
      app: { name: "Zapret RU", version: "1.2.0", task_name: "Zapret RU Launcher", task_command: "\"C:\\ZapretRU\\ZapretRU.exe\" --autostart", engine: "native" },
      settings: { ...settings },
      presets,
      presets_updated: "2026-11-26",
      presets_error: null,
      environment: env,
      status: { ...status },
      usage: { ...usage },
      autostart: false,
      autostart_error: null,
      warnings: [],
      paths: {
        data: "C:\\Users\\demo\\AppData\\Local\\ZapretRU",
        lists: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists",
        presets: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\presets.json",
        general_list: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-general.txt",
        exclude_list: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-exclude.txt"
      }
    }),
    get_status: async () => ({ ok: true, status: { ...status }, settings: { ...settings }, usage: { ...usage } }),
    get_logs: async (after = 0) => ({ ok: true, entries: logs.filter((entry) => entry.seq > after), next_seq: logs.length }),
    clear_logs: async () => ({ ok: true, next_seq: 0 }),
    check_connectivity: async () => ({
      ok: true,
      checked_at: Date.now() / 1000,
      timeout_seconds: 3,
      total: 3,
      reachable: 3,
      services: [
        { id: "youtube", label: "YouTube", ok: true, status: 204, latency_ms: 185, error: null, detail: null },
        { id: "discord", label: "Discord", ok: true, status: 200, latency_ms: 221, error: null, detail: null },
        { id: "cloudflare", label: "Cloudflare", ok: true, status: 200, latency_ms: 203, error: null, detail: null }
      ]
    }),
    refresh_environment: async () => env,
    start_bypass: async () => {
      makeRunning();
      return { ok: true, status: { ...status }, usage: { ...usage }, config: status.active_config, command_line: commandPreview(), warnings: [], skipped_files: [], environment: env };
    },
    stop_bypass: async () => { makeStopped(); return { ok: true, status: { ...status }, usage: { ...usage }, environment: env }; },
    restart_bypass: async () => {
      makeRunning();
      return { ok: true, status: { ...status }, usage: { ...usage }, config: status.active_config, command_line: commandPreview(), warnings: [], skipped_files: [], environment: env };
    },
    update_setting: async (key, value) => { settings[key] = value; return { ok: true, settings: { ...settings } }; },
    set_autostart: async (enabled) => ({ ok: true, autostart: !!enabled, task_name: "Zapret RU Launcher", task_command: "\"C:\\ZapretRU\\ZapretRU.exe\" --autostart" }),
    get_presets: async () => ({ ok: true, presets, updated: "2026-11-26", error: null }),
    reload_presets: async () => ({ ok: true, presets, updated: "2026-11-26", error: null }),
    read_lists: async () => ({ ok: true, lists }),
    save_list: async (key, content) => {
      lists[key].content = content;
      return { ok: true, key, path: lists[key].path, backup: null, entries: content.split(/\r?\n/).filter((line) => line && !line.startsWith("#")).length, saved_at: Date.now() / 1000, message: "Список сохранён." };
    },
    command_preview: async () => ({ ok: true, command_line: commandPreview(), warnings: [], skipped_files: [], split: "sni", block_quic: true }),
    window_minimize: async () => ({ ok: true }),
    window_toggle_maximize: async () => ({ ok: true, maximized: true }),
    window_close: async () => ({ ok: true, action: "tray" }),
    show_window: async () => ({ ok: true }),
    open_folder: async () => ({ ok: true }),
    copy_text: async () => ({ ok: true }),
    open_link: async () => ({ ok: true })
  };

  const frame = document.getElementById("app-frame");
  const params = new URLSearchParams(location.search);
  const inject = () => {
    const win = frame.contentWindow;
    win.pywebview = { api };
    if (params.get("state") === "running") makeRunning();
    win.__zapretPreview = {
      api,
      makeRunning,
      makeStopped,
      env,
      status,
      settings,
      lists,
      logs,
      showWarning() {
        env.engine_error = "Встроенный драйвер WinDivert не загрузился: demo";
        env.ready = false;
        win.dispatchEvent(new Event("pywebviewready"));
      }
    };
    win.dispatchEvent(new Event("pywebviewready"));

    const tab = params.get("tab");
    const action = params.get("action");
    const scroll = params.get("scroll");
    let didTab = false;
    let didAction = false;
    const timer = window.setInterval(() => {
      const doc = frame.contentDocument;
      if (!doc || !doc.getElementById("loading-overlay")?.hidden) return;
      if (tab && !didTab) {
        const button = doc.getElementById(`tab-${tab}`);
        if (button) {
          button.click();
          didTab = true;
        }
      }
      if (scroll === "bottom") {
        const view = doc.querySelector(`.view.active`);
        if (view) view.scrollTop = view.scrollHeight;
      }
      if (action === "autotune" && !didAction) {
        const button = doc.getElementById("btn-autotune");
        if (button && !button.disabled) {
          button.click();
          didAction = true;
        }
      }
      if ((!tab || didTab) && (!action || didAction)) {
        window.setTimeout(() => window.clearInterval(timer), 120);
      }
    }, 80);
  };

  if (frame.contentDocument?.readyState === "complete") inject();
  else frame.addEventListener("load", inject);
})();
