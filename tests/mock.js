/* Development-only mock of the pywebview bridge. Not included in builds. */
(() => {
  "use strict";
  const presets = [
    { id: "general", name: "General", label: "Универсальный", badge: "Рекомендуется", description: "Fake + multisplit с fooling=ts. Сбалансированная стратегия для большинства домашних провайдеров: TLS/HTTP, QUIC и голосовой UDP Discord.", caution: null },
    { id: "alt1", name: "ALT 1", label: "Badseq / Autottl", badge: "AUTOTTL", description: "Fake + fakedsplit с автоматическим TTL и fooling=badseq. Помогает там, где TTL-фейки не доходят до DPI.", caution: null },
    { id: "alt2", name: "ALT 2", label: "Split2 / MD5Sig", badge: "MD5SIG", description: "Fake + split2 с TCP-опцией MD5 signature. Работает на части DPI, которые пропускают нестандартную TCP-опцию.", caution: "MD5 signature увеличивает TCP-заголовок. На редких провайдерах это может переполнить MTU." },
    { id: "alt3", name: "ALT 3", label: "Syndata / Агрессивный", badge: "MTS / MOBILE", description: "Syndata + fake + multisplit с badseq/autottl и повышенным числом повторов. Для сложных провайдеров и мобильного интернета.", caution: "Syndata работает на этапе SYN и не может учитывать SNI-исключения." },
    { id: "alt4", name: "ALT 4", label: "Без Fake / Только Split", badge: "NO FAKE", description: "Только сегментация и overlap без фейковых TCP-пакетов. QUIC и UDP обрабатываются udplen.", caution: null }
  ];

  const required = [
    { name: "winws.exe", present: true, size: 482304, path: "C:\\ZapretRU\\bin\\winws.exe" },
    { name: "WinDivert.dll", present: true, size: 92160, path: "C:\\ZapretRU\\bin\\WinDivert.dll" },
    { name: "WinDivert64.sys", present: true, size: 139264, path: "C:\\ZapretRU\\bin\\WinDivert64.sys" },
    { name: "cygwin1.dll", present: true, size: 3317760, path: "C:\\ZapretRU\\bin\\cygwin1.dll" }
  ];
  const optional = [
    { name: "quic_initial_www_google_com.bin", present: true, size: 1252, path: "C:\\ZapretRU\\bin\\quic_initial_www_google_com.bin" },
    { name: "tls_clienthello_www_google_com.bin", present: true, size: 517, path: "C:\\ZapretRU\\bin\\tls_clienthello_www_google_com.bin" },
    { name: "ACTIVE_DISCORD_UDP.bin", present: true, size: 97, path: "C:\\ZapretRU\\bin\\ACTIVE_DISCORD_UDP.bin" },
    { name: "ACTIVE_GAME_UDP.bin", present: true, size: 80, path: "C:\\ZapretRU\\bin\\ACTIVE_GAME_UDP.bin" }
  ];

  const env = {
    admin: true,
    frozen: true,
    arch: "AMD64",
    bin_dir: "C:\\ZapretRU\\bin",
    data_dir: "C:\\Users\\demo\\AppData\\Local\\ZapretRU",
    lists_dir: "C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists",
    required,
    optional,
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

  const settings = { preset_id: "general", mode: "list", game_filter: false, minimize_to_tray: true, autostart: false, last_tab: "home" };
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
    command: ["--wf-tcp=80,443", "--wf-udp=443,19294-19344,50000-65535"],
    command_line: "winws.exe --wf-tcp=80,443 --wf-udp=443,19294-19344,50000-65535 --filter-udp=443 --filter-l7=quic --hostlist=lists\\list-general.txt --hostlist-exclude=lists\\list-exclude.txt --dpi-desync=fake --dpi-desync-repeats=8 --new --filter-udp=19294-19344,50000-65535 --filter-l7=discord,stun --dpi-desync=fake --dpi-desync-repeats=6 --new --filter-tcp=80,443 --hostlist=lists\\list-general.txt --hostlist-exclude=lists\\list-exclude.txt --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=6",
    executable: "C:\\ZapretRU\\bin\\winws.exe",
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
    { seq: 1, time: "21:14:02", text: "Запуск winws.exe", kind: "system" },
    { seq: 2, time: "21:14:02", text: "winws.exe --wf-tcp=80,443 --wf-udp=443,19294-19344,50000-65535 --filter-udp=443 --filter-l7=quic --hostlist=list-general.txt", kind: "command" },
    { seq: 3, time: "21:14:03", text: "winws.exe запущен, PID 4821", kind: "system" },
    { seq: 4, time: "21:14:03", text: "Loading hostlist C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-general.txt", kind: "output" },
    { seq: 5, time: "21:14:03", text: "Loading hostlist C:\\Users\\demo\\AppData\\Local\\ZapretRU\\lists\\list-exclude.txt", kind: "output" },
    { seq: 6, time: "21:14:03", text: "windivert: filter initialized, TCP 80,443 / UDP 443", kind: "output" },
    { seq: 7, time: "21:14:04", text: "quic fake payload: quic_initial_www_google_com.bin (1252 bytes)", kind: "output" },
    { seq: 8, time: "21:14:04", text: "tls fake payload: tls_clienthello_www_google_com.bin (517 bytes)", kind: "output" },
    { seq: 9, time: "21:14:04", text: "desync fake,multisplit seqovl=681 split-pos=1 fooling=ts", kind: "output" },
    { seq: 10, time: "21:14:05", text: "strategy started, 4 profiles active", kind: "output" }
  ];

  function commandPreview() {
    return "winws.exe --wf-tcp=80,443 --wf-udp=443,19294-19344,50000-65535 --filter-udp=443 --filter-l7=quic --hostlist=list-general.txt --hostlist-exclude=list-exclude.txt --dpi-desync=fake --dpi-desync-repeats=8 --new --filter-udp=19294-19344,50000-65535 --filter-l7=discord,stun --dpi-desync=fake --dpi-desync-repeats=6 --new --filter-tcp=80,443 --hostlist=list-general.txt --hostlist-exclude=list-exclude.txt --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=6";
  }

  function makeRunning() {
    status.running = true;
    status.pid = 4821;
    status.uptime_seconds = 372;
    status.started_at = Date.now() / 1000 - 372;
    status.active_config = {
      preset_id: settings.preset_id,
      preset_name: "General",
      preset_label: "Универсальный",
      mode: settings.mode,
      game_filter: settings.game_filter,
      wf_tcp: "80,443",
      wf_udp: "443,19294-19344,50000-65535"
    };
    env.session.manager_running = true;
  }

  function makeStopped() {
    status.running = false;
    status.pid = null;
    status.uptime_seconds = 0;
    status.started_at = null;
    status.active_config = {};
    env.session.manager_running = false;
  }

  const api = {
    bootstrap: async () => ({
      ok: true,
      app: { name: "Zapret RU", version: "1.1.0", task_name: "Zapret RU Launcher", task_command: "\"C:\\ZapretRU\\ZapretRU.exe\" --autostart" },
      settings: { ...settings },
      presets,
      presets_updated: "2026-11-25",
      presets_error: null,
      environment: env,
      status: { ...status },
      usage: { ...usage },
      autostart: false,
      autostart_error: null,
      warnings: [],
      paths: {
        bin: "C:\\ZapretRU\\bin",
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
        { id: "cloudflare", label: "Cloudflare", ok: false, status: null, latency_ms: 3000, error: "Таймаут", detail: "Нет ответа за 3 с" }
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
    get_presets: async () => ({ ok: true, presets, updated: "2026-11-25", error: null }),
    reload_presets: async () => ({ ok: true, presets, updated: "2026-11-25", error: null }),
    read_lists: async () => ({ ok: true, lists }),
    save_list: async (key, content) => {
      lists[key].content = content;
      return { ok: true, key, path: lists[key].path, backup: null, entries: content.split(/\r?\n/).filter((line) => line && !line.startsWith("#")).length, saved_at: Date.now() / 1000, message: "Список сохранён." };
    },
    command_preview: async () => ({ ok: true, command_line: commandPreview(), warnings: [], skipped_files: [], wf_tcp: "80,443", wf_udp: "443" }),
    window_minimize: async () => ({ ok: true }),
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
        env.missing_required = ["winws.exe", "WinDivert.dll"];
        env.required[0].present = false;
        env.required[1].present = false;
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
