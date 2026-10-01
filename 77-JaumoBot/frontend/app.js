"use strict";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const lines = (text) => String(text || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
const ACTIVE = new Set(["queued", "running"]);

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (opts.body instanceof FormData) {
    init.body = opts.body;
  } else if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  const resp = await fetch(path, init);
  if (resp.status === 401 && path !== "/api/login") {
    showLogin();
    throw new Error("Not authenticated");
  }
  const ct = resp.headers.get("content-type") || "";
  const data = ct.includes("json") ? await resp.json() : await resp.text();
  if (!resp.ok) {
    let msg = data && data.detail !== undefined ? data.detail : data;
    const where = `${init.method} ${path.split("?")[0]}`;
    if (Array.isArray(msg)) {
      msg = msg.map((e) => (e.loc && e.loc[0] === "path"
        ? `Invalid ${e.loc.slice(1).join(".")} in ${where}`
        : `${(e.loc || []).slice(1).join(".")}: ${e.msg}`)).join("; ");
    } else if (resp.status === 404 && msg === "Not Found") {
      msg = `Not found: ${where} — if the panel was just updated, restart the server`;
      checkServerVersion();
    }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function toast(msg, isErr = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isErr ? " err" : "");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), isErr ? 7000 : 3500);
}

const guard = (fn) => async (...args) => {
  try { await fn(...args); } catch (e) { if (e.message !== "Not authenticated") toast(e.message, true); }
};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "2-digit", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function fmtTime(iso) {
  return iso ? new Date(iso).toLocaleTimeString(undefined, { hour12: false }) : "";
}
function duration(run) {
  if (!run.started_at) return "";
  const end = run.finished_at ? new Date(run.finished_at) : new Date();
  const s = Math.max(0, Math.round((end - new Date(run.started_at)) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`;
}
const badge = (status) => `<span class="badge ${esc(status)}">${esc(status)}</span>`;

// ---------------------------------------------------------------------------
// Language (DE default) and theme (dark default)
// ---------------------------------------------------------------------------

const I18N = {
  de: {
    "brand.sub": "Accountverwaltung & Automatisierung",
    "sec.overview": "Übersicht", "sec.automation": "Automatisierung", "sec.data": "Daten", "sec.system": "System",
    "nav.dashboard": "Dashboard", "nav.accounts": "Jaumo Accounts", "nav.logs": "Logs", "nav.configs": "Konfigurationen",
    "nav.proxies": "Proxys", "nav.photos": "Fotos", "nav.settings": "Einstellungen",
    "sys.online": "System online", "sys.offline": "Verbindung wird hergestellt…", "sys.version": "Version 1.0",
    "top.online": "Online", "top.offline": "Offline", "top.admin": "Administrator", "top.logout": "Abmelden",
    "top.theme": "Hell / Dunkel", "top.lang": "English", "top.notifications": "Benachrichtigungen", "top.noNotif": "Keine neuen Benachrichtigungen",
    "top.search": "Accounts suchen (ID, Name, Jaumo-ID, Worker, …)",
    "acc.title": "Jaumo Accounts", "acc.sub": "Verwalte und überwache alle Jaumo Accounts",
    "acc.allStatus": "Alle Status", "acc.allWorkers": "Alle Worker", "acc.filter": "Filter", "acc.new": "Neuer Account",
    "kpi.total": "Gesamt Accounts", "kpi.likes": "Likes", "kpi.matches": "Matches", "kpi.messages": "Nachrichten",
    "kpi.actions": "Aktionen", "kpi.today": "+{n} heute", "kpi.notSynced": "Postfach noch nicht synchronisiert",
    "col.account": "Account", "col.stats": "Statistiken", "col.status": "Status", "col.worker": "Worker",
    "col.last": "Letzte Aktivität", "col.actions": "Aktionen",
    "st.likes": "Likes", "st.dislikes": "Dislikes", "st.matches": "Matches", "st.messages": "Nachrichten",
    "st.visits": "Besuche", "st.actions": "Aktionen",
    "st.likesIn": "Likes", "st.likesInTip": "Erhaltene Likes, die unser Profil geliked haben",
    "st.visitsIn": "Besucher", "st.visitsInTip": "Erhaltene Besucher, die unser Profil besucht haben",
    "st.messagesIn": "Nachrichten", "st.messagesInTip": "Erhaltene Nachrichten, die dem Profil geschrieben wurden",
    "st.matchesTip": "Übereinstimmung im Matchgame mit anderen Profilen durch Liken",
    "st.likesOut": "Gesendete Likes", "st.likesOutTip": "Likes, die wir gesendet haben",
    "st.dislikesTip": "Profile, die wir als nicht-Like markiert haben",
    "st.messagesOut": "Nachrichten gesendet", "st.messagesOutLong": "Nachrichten gesendet", "st.messagesOutTip": "Nachrichten, die wir mit unserem Profil an User gesendet haben",
    "sync.never": "Noch nicht synchronisiert", "sync.at": "Synchronisiert {t}", "sync.refresh": "Stats aktualisieren",
    "sync.refreshOne": "Aktualisieren", "sync.running": "Wird aktualisiert …", "sync.wait": "Bitte {s} s warten",
    "sync.error": "Letzte Aktualisierung fehlgeschlagen: {e}", "sync.title": "Stats von Jaumo aktualisieren",
    "sync.text": "Liest Likes, Besucher, Nachrichten und Matches direkt von Jaumo (nur lesen — es wird nichts gesendet). Jeder Account kann nur einmal gleichzeitig aktualisiert werden (15 s Pause danach).",
    "sync.selected": "Ausgewählte Accounts ({n})", "sync.all": "Alle Accounts ({n})",
    "sync.cost": "{n} Account(s) · ca. {r} Anfragen über den Proxy · nacheinander mit {d} s Pause",
    "sync.started": "{n} Aktualisierung(en) gestartet", "sync.skipped": "{n} übersprungen: {why}",
    "sync.start": "Aktualisieren",
    "st.messagesTip": "Chats im Postfach (Kontakte, die uns geschrieben haben)",
    "st.visitsTip": "Profilbesuche", "st.notSynced": "Noch nicht synchronisiert",
    "st.actionsTip": "Likes + Dislikes + gesendete Nachrichten",
    "st.likesSub": "vergebene Likes", "st.dislikesSub": "vergebene Dislikes", "st.rate": "{r}% der Likes",
    "st.sent": "Gesendete Nachrichten", "st.sentSub": "{n} Kontakte angeschrieben", "st.pending": "Offene Matches", "st.pendingSub": "noch nicht angeschrieben",
    "state.active": "Aktiv", "state.working": "Arbeitet", "state.blocked": "Gesperrt", "state.error": "Fehler", "state.stopped": "Gestoppt",
    "acc.created": "erstellt {d}", "acc.lastLabel": "Letzte Aktivität", "acc.never": "noch keine",
    "acc.view": "Account ansehen", "acc.edit": "Bearbeiten", "acc.more": "Weitere Aktionen",
    "acc.menuMessage": "Matches anschreiben", "acc.menuLog": "Letztes Log öffnen", "acc.menuCopy": "Jaumo-ID kopieren",
    "acc.menuDelete": "Account löschen", "acc.copied": "Kopiert",
    "acc.empty": "Keine Accounts gefunden", "acc.emptySub": "Passe die Filter an oder erstelle neue Accounts.",
    "pager.showing": "Zeige {a}–{b} von {n} Accounts", "pager.per": "{n} pro Seite",
    "bulk.selected": "{n} ausgewählt", "bulk.message": "Matches anschreiben", "bulk.export": "Exportieren", "bulk.clear": "Auswahl aufheben",
    "filter.location": "Standort", "filter.all": "Alle", "filter.from": "Erstellt ab", "filter.to": "Erstellt bis",
    "filter.sort": "Sortierung", "filter.reset": "Zurücksetzen", "filter.apply": "Anwenden",
    "sort.newest": "Neueste zuerst", "sort.activity": "Letzte Aktivität", "sort.likes": "Meiste Likes",
    "sort.matches": "Meiste Matches", "sort.oldest": "Älteste zuerst",
    "new.title": "Neue Accounts erstellen", "new.config": "Konfiguration", "new.count": "Anzahl Accounts",
    "new.mode": "Ausführung", "new.sequential": "Nacheinander", "new.sequentialSub": "1 Worker — ein Account nach dem anderen",
    "new.parallel": "Parallel", "new.parallelSub": "Mehrere Worker gleichzeitig", "new.workers": "Worker",
    "new.names": "Eigene Namen (optional, einer pro Zeile)", "new.submit": "Accounts erstellen",
    "new.queued": "{n} Account(s) werden erstellt", "new.busy": "{w} Worker aktiv · {q} in Warteschlange",
    "new.idle": "Alle Worker frei",
    "new.blocked": "So kann noch nicht gestartet werden:", "new.fix": "Beheben",
    "new.p.apk": "Keine aktive APK-Konfiguration für diese Konfiguration.", "new.p.photos": "Nicht genug freie Fotos.",
    "new.p.names": "Nicht genug freie Namen.", "new.p.proxy": "Kein aktiver Proxy — die Konfiguration verlangt einen.",
    "setup.title": "Einrichtung", "setup.sub": "Das fehlt noch, bevor Accounts mit „{c}“ erstellt werden können:",
    "setup.apk": "APK-Profil", "setup.proxy": "Proxy", "setup.photos": "Fotos", "setup.names": "Namen",
    "setup.ok": "Bereit", "setup.proxyOff": "nicht verlangt",
    "edit.title": "Account bearbeiten", "edit.status": "Status", "edit.notes": "Notizen", "edit.save": "Speichern", "edit.saved": "Gespeichert",
    "msg.title": "Matches anschreiben", "msg.config": "Konfiguration für Nachrichten", "msg.start": "Starten",
    "common.cancel": "Abbrechen", "common.delete": "Löschen",
    "msg.noneEnabled": "In keiner Konfiguration ist das Anschreiben aktiviert. Aktiviere „Messaging enabled“ unter Konfigurationen → Messaging.",
    "outdated": "Der Server läuft noch mit altem Code. Bitte den Server neu starten, damit alle Funktionen korrekt arbeiten.",
    "del.confirm": "Account \"{name}\" (#{id}) wirklich löschen? Tokens und Verlauf gehen verloren.",
  },
  en: {
    "brand.sub": "Account management & automation",
    "sec.overview": "Overview", "sec.automation": "Automation", "sec.data": "Data", "sec.system": "System",
    "nav.dashboard": "Dashboard", "nav.accounts": "Jaumo Accounts", "nav.logs": "Runs & logs", "nav.configs": "Configurations",
    "nav.proxies": "Proxies", "nav.photos": "Photo library", "nav.settings": "Settings",
    "sys.online": "System online", "sys.offline": "Reconnecting…", "sys.version": "Version 1.0",
    "top.online": "Online", "top.offline": "Offline", "top.admin": "Administrator", "top.logout": "Sign out",
    "top.theme": "Light / dark", "top.lang": "Deutsch", "top.notifications": "Notifications", "top.noNotif": "No new notifications",
    "top.search": "Search accounts (ID, name, Jaumo ID, worker, …)",
    "acc.title": "Jaumo Accounts", "acc.sub": "Manage and monitor all Jaumo accounts",
    "acc.allStatus": "All statuses", "acc.allWorkers": "All workers", "acc.filter": "Filter", "acc.new": "New account",
    "kpi.total": "Total accounts", "kpi.likes": "Likes", "kpi.matches": "Matches", "kpi.messages": "Messages",
    "kpi.actions": "Actions", "kpi.today": "+{n} today", "kpi.notSynced": "Inbox not synced yet",
    "col.account": "Account", "col.stats": "Statistics", "col.status": "Status", "col.worker": "Worker",
    "col.last": "Last activity", "col.actions": "Actions",
    "st.likes": "Likes", "st.dislikes": "Dislikes", "st.matches": "Matches", "st.messages": "Messages",
    "st.visits": "Visits", "st.actions": "Actions",
    "st.likesIn": "Likes", "st.likesInTip": "Likes received — people who liked our profile",
    "st.visitsIn": "Visitors", "st.visitsInTip": "Visitors received — people who visited our profile",
    "st.messagesIn": "Messages", "st.messagesInTip": "Messages received — written to the profile",
    "st.matchesTip": "Mutual likes in the match game",
    "st.likesOut": "Likes sent", "st.likesOutTip": "Likes we sent",
    "st.dislikesTip": "Profiles we passed",
    "st.messagesOut": "Messages sent", "st.messagesOutLong": "Messages sent", "st.messagesOutTip": "Messages we sent to users with our profile",
    "sync.never": "Not synced yet", "sync.at": "Synced {t}", "sync.refresh": "Refresh stats",
    "sync.refreshOne": "Refresh", "sync.running": "Refreshing …", "sync.wait": "Wait {s}s",
    "sync.error": "Last refresh failed: {e}", "sync.title": "Refresh stats from Jaumo",
    "sync.text": "Reads likes, visitors, messages and matches directly from Jaumo (read-only — nothing is sent). Each account can be refreshed once at a time (15 s pause afterwards).",
    "sync.selected": "Selected accounts ({n})", "sync.all": "All accounts ({n})",
    "sync.cost": "{n} account(s) · about {r} requests through the proxy · one after another with a {d} s pause",
    "sync.started": "{n} refresh(es) started", "sync.skipped": "{n} skipped: {why}",
    "sync.start": "Refresh",
    "st.messagesTip": "Chats in the inbox (contacts who wrote to us)",
    "st.visitsTip": "Profile visits", "st.notSynced": "Not synced yet",
    "st.actionsTip": "Likes + dislikes + messages sent",
    "st.likesSub": "likes given", "st.dislikesSub": "dislikes given", "st.rate": "{r}% of likes",
    "st.sent": "Messages sent", "st.sentSub": "{n} people messaged", "st.pending": "Pending matches", "st.pendingSub": "not messaged yet",
    "state.active": "Active", "state.working": "Working", "state.blocked": "Blocked", "state.error": "Error", "state.stopped": "Stopped",
    "acc.created": "created {d}", "acc.lastLabel": "Last activity", "acc.never": "none yet",
    "acc.view": "View account", "acc.edit": "Edit", "acc.more": "More actions",
    "acc.menuMessage": "Message matches", "acc.menuLog": "Open latest log", "acc.menuCopy": "Copy Jaumo ID",
    "acc.menuDelete": "Delete account", "acc.copied": "Copied",
    "acc.empty": "No accounts found", "acc.emptySub": "Adjust the filters or create new accounts.",
    "pager.showing": "Showing {a}–{b} of {n} accounts", "pager.per": "{n} per page",
    "bulk.selected": "{n} selected", "bulk.message": "Message matches", "bulk.export": "Export", "bulk.clear": "Clear selection",
    "filter.location": "Location", "filter.all": "All", "filter.from": "Created from", "filter.to": "Created until",
    "filter.sort": "Sort by", "filter.reset": "Reset", "filter.apply": "Apply",
    "sort.newest": "Newest first", "sort.activity": "Last activity", "sort.likes": "Most likes",
    "sort.matches": "Most matches", "sort.oldest": "Oldest first",
    "new.title": "Create new accounts", "new.config": "Configuration", "new.count": "Number of accounts",
    "new.mode": "Run mode", "new.sequential": "One by one", "new.sequentialSub": "1 worker — one account after another",
    "new.parallel": "Parallel", "new.parallelSub": "Several workers at the same time", "new.workers": "Workers",
    "new.names": "Custom names (optional, one per line)", "new.submit": "Create accounts",
    "new.queued": "Creating {n} account(s)", "new.busy": "{w} worker(s) busy · {q} waiting",
    "new.idle": "All workers free",
    "new.blocked": "Cannot start yet:", "new.fix": "Fix",
    "new.p.apk": "No enabled APK profile for this configuration.", "new.p.photos": "Not enough free photos.",
    "new.p.names": "Not enough free names.", "new.p.proxy": "No enabled proxy — the configuration requires one.",
    "setup.title": "Setup", "setup.sub": "Still missing before accounts can be created with “{c}”:",
    "setup.apk": "APK profile", "setup.proxy": "Proxy", "setup.photos": "Photos", "setup.names": "Names",
    "setup.ok": "Ready", "setup.proxyOff": "not required",
    "edit.title": "Edit account", "edit.status": "Status", "edit.notes": "Notes", "edit.save": "Save", "edit.saved": "Saved",
    "msg.title": "Message matches", "msg.config": "Configuration for messages", "msg.start": "Start",
    "common.cancel": "Cancel", "common.delete": "Delete",
    "msg.noneEnabled": "No configuration has messaging turned on. Enable “Messaging enabled” under Configurations → Messaging.",
    "outdated": "The server is still running old code. Please restart the server so everything works correctly.",
    "del.confirm": "Delete account \"{name}\" (#{id})? Its tokens and history will be lost.",
  },
};

const prefs = {
  get(k, d) { try { return localStorage.getItem(k) || d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};
let LANG = prefs.get("lang", "de") === "en" ? "en" : "de";

function t(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) s = s.replace(/\{(\w+)\}/g, (_, v) => (vars[v] ?? ""));
  return s;
}

function applyI18n(root = document) {
  document.documentElement.lang = LANG;
  root.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  root.querySelectorAll("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
  root.querySelectorAll("[data-i18n-title]").forEach((el) => (el.title = t(el.dataset.i18nTitle)));
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  prefs.set("theme", theme);
}
setTheme(prefs.get("theme", "dark") === "light" ? "light" : "dark");

function relTime(iso) {
  if (!iso) return t("acc.never");
  const diff = (new Date(iso) - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LANG, { numeric: "auto", style: "short" });
  const abs = Math.abs(diff);
  if (abs < 45) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  return new Date(iso).toLocaleDateString(LANG);
}
const shortDate = (iso) => (iso ? new Date(iso).toLocaleDateString(LANG, { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—");

// Live refreshes: run at most once per `ms`, but never starve while events keep arriving
// (a plain debounce never fires while a worker sends updates faster than its delay).
function throttle(fn, ms) {
  let last = 0, timer = null;
  return (...a) => {
    if (document.hidden) { missedWhileHidden = true; return; }
    const wait = ms - (Date.now() - last);
    if (wait <= 0) { last = Date.now(); fn(...a); return; }
    if (!timer) timer = setTimeout(() => { timer = null; last = Date.now(); fn(...a); }, wait);
  };
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------------------------------------------------------------------------
// Icons (Lucide-style strokes) and number helpers
// ---------------------------------------------------------------------------

const ICONS = {
  dashboard: '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  sliders: '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  menu: '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
  userPlus: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
  userCheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>',
  heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  thumbsUp: '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>',
  thumbsDown: '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>',
  percent: '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
  message: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
  checkCircle: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  pause: '<circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/>',
  key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
  rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  stop: '<rect width="14" height="14" x="5" y="5" rx="2"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  smartphone: '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  arrowUp: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  arrowDown: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  imagePlus: '<path d="M16 5h6"/><path d="M19 2v6"/><path d="M21 11.5V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7.5"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/><circle cx="9" cy="9" r="2"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  archive: '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
  externalLink: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  play2: '<polygon points="6 3 20 12 6 21 6 3"/>',
  eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  languages: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
};

function icon(name) {
  return `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}
function iconBtn(name, attrs, title, cls = "") {
  return `<button type="button" class="icon-btn sm ${cls}" ${attrs} title="${esc(title)}" aria-label="${esc(title)}">${icon(name)}</button>`;
}
function hydrateIcons(root = document) {
  root.querySelectorAll("i[data-icon]:not([data-done])").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
    el.dataset.done = "1";
  });
}
const fmtNum = (n) => Number(n || 0).toLocaleString();
const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

let modalOnClose = null;
function openModal(title, html, onClose) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = html;
  $("#modal").classList.remove("hidden");
  modalOnClose = onClose || null;
}
function closeModal() {
  $("#modal").classList.add("hidden");
  $("#modal-body").innerHTML = "";
  if (modalOnClose) { const f = modalOnClose; modalOnClose = null; f(); }
}
$("#modal-close").onclick = closeModal;
$("#modal").addEventListener("click", (e) => { if (e.target.closest("[data-close-modal]")) closeModal(); });
$("#modal").addEventListener("mousedown", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#modal").classList.contains("hidden")) closeModal(); });

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  configs: [],
  apks: [],
  photos: [],
  runs: new Map(),       // dashboard cache: active + recent
  stats: null,
  tab: "dashboard",
  runsPage: 0,
  accPage: 0,
  accSort: "id",
  accOrder: "desc",
  accSelected: new Set(),
  proxySelected: new Set(),
  expandedAccount: null,
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function showLogin() {
  $("#app-view").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
  closeEvents();
}

async function showApp(user) {
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  if (user) {
    $("#sb-username").textContent = user;
    $("#sb-avatar").textContent = user.charAt(0).toUpperCase();
    $("#top-username").textContent = user;
    $("#top-avatar").textContent = user.charAt(0).toUpperCase();
  }
  await Promise.all([loadConfigs(), loadApks(), loadPhotos()]);
  guard(loadStats)();
  checkServerVersion();
  openEvents();
  switchTab(location.hash.slice(1) || "dashboard");
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  $("#login-error").textContent = "";
  try {
    await api("/api/login", { method: "POST", body: { username: f.get("username"), password: f.get("password") } });
    e.target.reset();
    showApp(f.get("username"));
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});

$("#logout-btn").onclick = guard(async () => {
  await api("/api/logout", { method: "POST" });
  showLogin();
});

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TAB_LOADERS = {
  dashboard: () => loadDashboard(),
  runs: () => loadRuns(),
  configs: () => Promise.all([loadConfigs(), loadApks(), loadPhotos()]),
  proxies: () => loadProxies(),
  photos: () => loadPhotos(),
  settings: () => loadSettings(),
  accounts: () => Promise.all([loadAccounts(), loadLocations()]),
};

function switchTab(route) {
  let tab = route, arg = null;
  const m = /^account\/(\d+)$/.exec(route || "");
  if (m) { tab = "account"; arg = +m[1]; }
  if (tab !== "account" && !TAB_LOADERS[tab]) tab = "dashboard";
  if (tab !== "account") closeAccountStreams();
  state.tab = tab;
  $("#app-view").dataset.tab = tab;
  const hash = "#" + (arg ? `account/${arg}` : tab);
  if (location.hash !== hash) history.replaceState(null, "", hash);
  const navTab = tab === "account" ? "accounts" : tab;
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === navTab));
  $$(".tab").forEach((s) => s.classList.toggle("hidden", s.id !== "tab-" + tab));
  $("#app-view").classList.remove("nav-open");
  window.scrollTo(0, 0);
  guard(tab === "account" ? () => openAccountPage(arg) : TAB_LOADERS[tab])();
}
window.addEventListener("hashchange", () => {
  if (!$("#app-view").classList.contains("hidden")) switchTab(location.hash.slice(1) || "dashboard");
});
$$("#tabs button").forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));
$("#sb-toggle").onclick = () => $("#app-view").classList.toggle("nav-open");

// --- Header: search, notifications, user menu ------------------------------
$("#top-search").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  state.acc.q = e.target.value.trim();
  state.acc.page = 0;
  $("#acc-search").value = state.acc.q;
  state.tab === "accounts" ? guard(loadAccounts)() : switchTab("accounts");
});
$("#top-bell").onclick = (e) => { e.stopPropagation(); $("#notif-panel").classList.toggle("hidden"); $("#user-menu").classList.add("hidden"); };
$("#top-user").onclick = (e) => { e.stopPropagation(); $("#user-menu").classList.toggle("hidden"); $("#notif-panel").classList.add("hidden"); };
document.addEventListener("click", (e) => {
  if (!e.target.closest("#notif-panel") && !e.target.closest("#top-bell")) $("#notif-panel").classList.add("hidden");
  if (!e.target.closest("#user-menu") && !e.target.closest("#top-user")) $("#user-menu").classList.add("hidden");
});
$("#user-menu").addEventListener("click", (e) => { if (e.target.closest("button")) $("#user-menu").classList.add("hidden"); });
$("#menu-theme").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
$("#menu-lang").onclick = () => {
  LANG = LANG === "de" ? "en" : "de";
  prefs.set("lang", LANG);
  applyI18n();
  switchTab(location.hash.slice(1) || "dashboard");
};
$("#menu-logout").onclick = () => $("#logout-btn").click();

async function checkServerVersion() {
  try {
    const r = await fetch("/api/version", { credentials: "same-origin" });
    const v = r.ok ? await r.json() : { outdated: true };   // no /api/version = server older than the page
    $("#outdated-banner").classList.toggle("hidden", !v.outdated);
  } catch {
    // older server without /api/version → it is outdated too
    $("#outdated-banner").classList.remove("hidden");
  }
}
setInterval(() => { if (!document.hidden && !$("#app-view").classList.contains("hidden")) checkServerVersion(); }, 60000);

function renderNotifications() {
  const s = state.stats;
  if (!s) return;
  const items = [];
  for (const w of s.apk_warnings || []) items.push({ icon: "alert", tone: "danger", text: `APK "${w.name}": ${w.problem}`, href: "#configs" });
  const blocked = (s.accounts_by_status || {}).blocked || 0;
  if (blocked) items.push({ icon: "ban", tone: "danger", text: `${blocked} × ${t("state.blocked")}`, href: "#accounts" });
  if (!s.proxies_enabled) items.push({ icon: "globe", tone: "warn", text: "No proxy enabled", href: "#proxies" });
  const freePhotos = (state.photos || []).filter((p) => p.status === "available").length;
  if (state.photos && freePhotos < 5) items.push({ icon: "image", tone: "warn", text: `${freePhotos} unused photos left`, href: "#photos" });
  $("#notif-count").textContent = items.length || "";
  $("#notif-list").innerHTML = items.length ? items.map((n) =>
    `<a class="notif" href="${n.href}"><span class="icon-bubble ${n.tone}">${icon(n.icon)}</span><span>${esc(n.text)}</span></a>`).join("")
    : `<div class="muted notif-empty">${esc(t("top.noNotif"))}</div>`;
}
$("#sb-backdrop").onclick = () => $("#app-view").classList.remove("nav-open");

function setLive(on) {
  $("#ws-status").classList.toggle("on", on);
  $("#ws-label").textContent = on ? t("sys.online") : t("sys.offline");
  $("#top-status").textContent = on ? t("top.online") : t("top.offline");
  $("#top-dot").classList.toggle("on", on);
  $("#live-chip").classList.toggle("on", on);
  $("#live-chip").lastChild.textContent = on ? "Live" : "Offline";
}

// ---------------------------------------------------------------------------
// Live events (WebSocket)
// ---------------------------------------------------------------------------

let eventsWs = null, eventsRetry = 0, eventsTimer = null;

function wsUrl(path) {
  return (location.protocol === "https:" ? "wss://" : "ws://") + location.host + path;
}

function openEvents() {
  closeEvents();
  const ws = new WebSocket(wsUrl("/ws/events"));
  eventsWs = ws;
  ws.onopen = () => {
    eventsRetry = 0;
    setLive(true);
    if (state.tab === "dashboard") guard(loadDashboardRuns)();
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "run") {
      const prev = state.runs.get(msg.run.id);
      state.runs.set(msg.run.id, msg.run);
      renderLiveCards();
      // Counter changes arrive as "counters" events; only status changes need fresh lists/stats.
      if (!prev || prev.status !== msg.run.status) {
        refreshStatsSoon();
        if (state.tab === "accounts") reloadAccountsSoon();
      }
      if (state.tab === "runs") reloadRunsSoon();
    } else if (msg.type === "counters") {
      applyCounters(msg);
    } else if (msg.type === "account") {
      refreshStatsSoon();
      refreshDailySoon();
      if (state.tab === "accounts") reloadAccountsSoon();
    } else if (msg.type === "settings") {
      refreshStatsSoon();
      if (state.tab === "dashboard") guard(renderSetupCheck)();
    } else if (msg.type === "apk") {
      refreshStatsSoon();
      if (state.tab === "configs") reloadApksSoon();
    }
  };
  ws.onclose = (e) => {
    setLive(false);
    if (eventsWs !== ws) return;
    eventsWs = null;
    if (e.code === 4401) return showLogin();
    eventsRetry = Math.min(eventsRetry + 1, 6);
    eventsTimer = setTimeout(openEvents, 1000 * eventsRetry);
  };
}

function closeEvents() {
  clearTimeout(eventsTimer);
  if (eventsWs) { const ws = eventsWs; eventsWs = null; ws.close(); }
}

const refreshStatsSoon = throttle(() => guard(loadStats)(), 5000);
const refreshDailySoon = throttle(() => { if (state.tab === "dashboard") guard(loadDaily)(); }, 5000);
const reloadRunsSoon = throttle(() => guard(loadRuns)(), 3000);

// Apply a "counters" push: patch the visible row / cards locally (no HTTP request).
function applyCounters(m) {
  const d = m.delta || {};
  const liked = d.liked || 0, disliked = d.disliked || 0, matches = d.matches || 0, msgs = d.messages || 0;
  const s = state.stats;
  if (s) {
    s.liked += liked; s.disliked += disliked; s.matches += matches; s.messages_sent += msgs;
    if (state.tab === "dashboard") { renderKpis(); renderEngagement(); }
  }
  const sum = state.acc && state.acc.summary;
  if (sum) {
    sum.likes += liked; sum.likes_sent = (sum.likes_sent || 0) + liked; sum.likes_today += liked;
    sum.dislikes += disliked; sum.dislikes_today = (sum.dislikes_today || 0) + disliked; sum.matches += matches; sum.matches_today += matches;
    sum.messages_sent += msgs; sum.messages_sent_today = (sum.messages_sent_today || 0) + msgs; sum.actions += liked + disliked + msgs; sum.actions_today += liked + disliked + msgs;
    if (d.synced) reloadAccountsSoon();   // received totals come from the server
  }
  if (state.tab !== "accounts") return;
  const item = state.acc.items.find((x) => x.id === m.account_id);
  const row = $(`#acc-tbody tr[data-acc="${m.account_id}"]`);
  if (item) Object.assign(item, m);
  if (row) {
    const setTile = (cls, v) => { const b = row.querySelector(`.stat-tile.${cls} b`); if (b) b.textContent = v === null || v === undefined ? "–" : fmtNum(v); };
    setTile("likes-out", m.liked_count); setTile("dislikes", m.disliked_count); setTile("matches", m.matches_count);
    setTile("messages-out", m.messages_sent); setTile("actions", m.actions);
    setTile("likes", m.likes_received); setTile("visits", m.profile_visits); setTile("messages", m.messages_received);
    const rel = row.querySelector("[data-rel]");
    if (rel && m.last_activity_at) { rel.dataset.rel = m.last_activity_at; rel.textContent = relTime(m.last_activity_at); }
  }
  if (sum) renderAccSummary();
}

// While the tab is hidden nothing is loaded; one catch-up when it becomes visible again.
let missedWhileHidden = false;
document.addEventListener("visibilitychange", () => {
  if (document.hidden || !missedWhileHidden || $("#app-view").classList.contains("hidden")) return;
  missedWhileHidden = false;
  guard(loadStats)();
  if (state.tab !== "account") guard(TAB_LOADERS[state.tab])();
});
const reloadApksSoon = throttle(() => guard(() => Promise.all([loadApks(), loadConfigs()]))(), 1500);

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

const STEP_FLOW = {
  signup: ["client_token", "signup", "location", "profile", "photo", "verify", "swiping"],
  message: ["login", "matches", "messaging"],
  sync: ["login", "links", "counters"],
};
const STEP_LABELS = {
  starting: "Starting", waiting_proxy: "Waiting for proxy", client_token: "Client token", signup: "Signing up",
  location: "Setting location", profile: "Loading profile", photo: "Uploading photo", verify: "Verifying photo",
  swiping: "Swiping", finished: "Finished", login: "Logging in", matches: "Loading matches", messaging: "Messaging",
  links: "Loading links", counters: "Reading counters",
};

state.days = 14;
state.daily = [];
state.liveFilter = "active";

async function loadDashboard() {
  await Promise.all([loadStats(), loadDaily(), loadDashboardRuns(), renderSetupCheck()]);
}

// First-run checklist: the same server check as "Neuer Account", shown only while something is missing.
async function renderSetupCheck() {
  const box = $("#setup-check");
  const c = state.configs.find((x) => String(x.id) === ($("#launch-config") || {}).value) || state.configs[0];
  if (!c) { box.classList.add("hidden"); return; }
  const res = await api("/api/runs/check", { method: "POST", body: { config_id: c.id, count: 1, names: [] } });
  if (state.tab !== "dashboard") return;
  box.classList.toggle("hidden", res.ok);
  if (res.ok) { box.innerHTML = ""; return; }
  const byCode = Object.fromEntries(res.problems.map((p) => [p.code, p]));
  const proxyRequired = (c.settings || {}).require_proxy !== false;
  const rows = [["apk", "configs"], ["proxy", "proxies"], ["photos", "photos"], ["names", "settings"]].map(([code, page]) => {
    const p = byCode[code];
    const note = p ? t("new.p." + code) : code === "proxy" && !proxyRequired ? t("setup.proxyOff") : t("setup.ok");
    return `<li class="${p ? "todo" : "done"}" data-setup="${code}" title="${esc(p ? p.message : "")}">
      <span class="icon-bubble ${p ? "warn" : "ok"}">${icon(p ? "alert" : "check")}</span>
      <span><b>${esc(t("setup." + code))}</b><small>${esc(note)}</small></span>
      ${p ? `<a class="btn ghost sm" href="#${page}">${esc(t("new.fix"))}</a>` : ""}</li>`;
  }).join("");
  box.innerHTML = `<div class="card-head"><div><h2>${icon("sliders")} ${esc(t("setup.title"))}</h2>
    <p class="card-sub">${esc(t("setup.sub", { c: c.name }))}</p></div></div><ul class="setup-list">${rows}</ul>`;
}

async function loadStats() {
  state.stats = await api("/api/stats");
  const s = state.stats;
  renderNotifications();
  $("#nav-running").textContent = s.running || "";
  $("#nav-apk").textContent = (s.apk_warnings || []).length || "";
  if (state.tab !== "dashboard") return;
  renderKpis();
  renderStatusBreakdown();
  renderEngagement();
  renderInfra();
  renderLaunchInfo();
  $("#apk-warnings").innerHTML = (s.apk_warnings || []).map((w) => `<div class="alert">
      <span class="alert-icon">${icon("alert")}</span>
      <div class="alert-body"><b>APK profile "${esc(w.name)}"</b> — ${esc(w.problem)}${w.configs.length ? ` · used by ${esc(w.configs.join(", "))}` : ""}
        ${w.last_error ? `<div class="muted mono">${esc(w.last_error)}</div>` : ""}</div>
      <button class="btn small" data-goto-apk>Manage APK profiles</button></div>`).join("");
}
$("#apk-warnings").addEventListener("click", (e) => {
  if (e.target.closest("[data-goto-apk]")) {
    switchTab("configs");
    setTimeout(() => $("#apk-table").scrollIntoView({ behavior: "smooth" }), 300);
  }
});

async function loadDaily() {
  state.daily = await api(`/api/stats/daily?days=${state.days}&tz_offset=${new Date().getTimezoneOffset()}`);
  if (state.tab !== "dashboard") return;
  renderChart();
  renderKpis();
}

// --- KPI tiles --------------------------------------------------------------

function kpiTile({ label, value, iconName, tone, foot }) {
  return `<div class="kpi">
    <div class="kpi-top">
      <div><div class="kpi-label">${esc(label)}</div><div class="kpi-value">${value}</div></div>
      <div class="icon-bubble ${tone}">${icon(iconName)}</div>
    </div>
    <div class="kpi-foot">${foot}</div>
  </div>`;
}

function renderKpis() {
  const s = state.stats;
  if (!s) return;
  const by = s.accounts_by_status || {};
  const today = state.daily.length ? state.daily[state.daily.length - 1].created : s.created_today;
  const yesterday = state.daily.length > 1 ? state.daily[state.daily.length - 2].created : null;
  let delta = "";
  if (yesterday !== null) {
    const d = today - yesterday;
    delta = `<span class="delta ${d > 0 ? "up" : d < 0 ? "down" : "flat"}">${d > 0 ? "+" : ""}${d}</span> vs yesterday`;
  }
  const active = (by.active || 0) + (by.legacy || 0);
  const blocked = by.blocked || 0;
  const matchRate = s.liked ? ((s.matches / s.liked) * 100).toFixed(1) : "0.0";
  $("#kpis").innerHTML = [
    kpiTile({ label: "Account creation", iconName: "cpu", tone: s.running || s.queued ? "ok" : "",
      value: s.running || s.queued ? `Running` : `Idle`,
      foot: s.running || s.queued
        ? `${s.running} worker${s.running === 1 ? "" : "s"} busy · ${s.queued} waiting`
        : s.parallel === 1 ? "one by one (1 worker)" : `parallel · ${s.parallel} workers` }),
    kpiTile({ label: "Created today", iconName: "userPlus", tone: "info",
      value: fmtNum(today), foot: delta || "accounts signed up today" }),
    kpiTile({ label: "Active accounts", iconName: "userCheck", tone: "ok",
      value: fmtNum(active), foot: `of ${fmtNum(s.accounts_total)} total · <span class="sr-danger">${fmtNum(blocked)} blocked</span>` }),
    kpiTile({ label: "Matches", iconName: "heart", tone: "danger",
      value: fmtNum(s.matches), foot: `${matchRate}% of ${fmtNum(s.liked)} likes` }),
  ].join("");
}

// --- Breakdown cards ----------------------------------------------------------

function statRow({ iconName, tone, label, value, sub, ratio }) {
  return `<div class="stat-row">
    <span class="sr-icon sr-${tone}">${icon(iconName)}</span>
    <span class="sr-label">${esc(label)}</span>
    <span class="sr-value">${value}${sub !== undefined ? `<small>${sub}</small>` : ""}</span>
    ${ratio !== undefined ? `<div class="meter ${tone === "accent" ? "" : tone === "info" ? "" : tone}"><span style="width:${Math.min(100, ratio * 100)}%"></span></div>` : ""}
  </div>`;
}

function renderStatusBreakdown() {
  const by = state.stats.accounts_by_status || {};
  const total = state.stats.accounts_total || 0;
  const groups = [
    { label: "Active", iconName: "checkCircle", tone: "ok", n: (by.active || 0) + (by.legacy || 0) },
    { label: "Blocked", iconName: "ban", tone: "danger", n: by.blocked || 0 },
    { label: "Failed setup", iconName: "alert", tone: "warn", n: (by.failed || 0) + (by.photo_failed || 0) },
    { label: "Stopped / in progress", iconName: "pause", tone: "neutral", n: (by.stopped || 0) + (by.signing_up || 0) },
  ];
  $("#status-sub").textContent = `${fmtNum(total)} accounts in total`;
  $("#status-breakdown").innerHTML = total
    ? `<div class="stat-rows">${groups.map((g) => statRow({ ...g, value: fmtNum(g.n), sub: `${pct(g.n, total)}%`, ratio: total ? g.n / total : 0 })).join("")}</div>`
    : emptyState("users", "No accounts yet", "Create new accounts to get started.");
}

function renderEngagement() {
  const s = state.stats;
  const rate = s.liked ? ((s.matches / s.liked) * 100).toFixed(1) : "0.0";
  const mini = (iconName, label, value, wide) =>
    `<div class="mini-stat${wide ? " wide" : ""}"><div class="ms-label">${icon(iconName)}${esc(label)}</div><div class="ms-value">${value}</div></div>`;
  $("#engagement").innerHTML = `<div class="mini-stats">
    ${mini("thumbsUp", "Likes", fmtNum(s.liked))}
    ${mini("thumbsDown", "Dislikes", fmtNum(s.disliked))}
    ${mini("heart", "Matches", fmtNum(s.matches))}
    ${mini("percent", "Match rate", `${rate}<small>%</small>`)}
    ${mini("message", "Messages sent", fmtNum(s.messages_sent), true)}
  </div>`;
}

function renderInfra() {
  const s = state.stats;
  const onProxy = Object.values(s.proxies_in_use || {}).reduce((a, b) => a + b, 0);
  const apks = state.apks || [];
  const healthy = apks.filter((a) => a.enabled && a.health !== "failing").length;
  const failing = apks.filter((a) => a.health === "failing").length;
  $("#infra").innerHTML = `<div class="stat-rows">
    ${statRow({ iconName: "bot", tone: "accent", label: "Workers (parallel accounts)", value: fmtNum(s.parallel), sub: s.parallel === 1 ? "one by one" : "parallel" })}
    ${statRow({ iconName: "image", tone: "info", label: "Unused photos", value: fmtNum((state.photos || []).filter((p) => p.status === "available").length) })}
    ${statRow({ iconName: "globe", tone: s.proxies_enabled ? "info" : "warn", label: "Proxies enabled", value: fmtNum(s.proxies_enabled), sub: `${onProxy} bots connected` })}
    ${statRow({ iconName: "key", tone: failing ? "danger" : "ok", label: "APK profiles healthy", value: `${healthy} / ${apks.length}`, sub: failing ? `${failing} failing` : "" , ratio: apks.length ? healthy / apks.length : 0 })}
    ${statRow({ iconName: "sliders", tone: "neutral", label: "Configurations", value: fmtNum(state.configs.length) })}
  </div>`;
}

function emptyState(iconName, title, text) {
  return `<div class="empty">${icon(iconName)}<b>${esc(title)}</b><span>${esc(text)}</span></div>`;
}

// --- Daily chart (single series, sequential blue) ----------------------------

function niceStep(max, ticks = 4) {
  if (max <= ticks) return 1;
  const raw = max / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
}

function renderChart() {
  const el = $("#daily-chart");
  const data = state.daily || [];
  const total = data.reduce((a, d) => a + d.created, 0);
  const blocked = data.reduce((a, d) => a + d.blocked, 0);
  const best = data.reduce((b, d) => (d.created > (b?.created ?? -1) ? d : b), null);
  const dayFmt = (iso, opts) => new Date(iso + "T00:00:00").toLocaleDateString(undefined, opts);
  $("#chart-summary").innerHTML = [
    ["Total created", fmtNum(total)],
    ["Avg per day", data.length ? (total / data.length).toFixed(1) : "0"],
    ["Best day", best && best.created ? `${best.created} <span class="muted" style="font-size:13px;font-weight:500">· ${dayFmt(best.date, { day: "numeric", month: "short" })}</span>` : "—"],
    ["Now blocked", `${fmtNum(blocked)} <span class="muted" style="font-size:13px;font-weight:500">· ${pct(blocked, total)}%</span>`],
  ].map(([l, v]) => `<div><div class="sum-label">${l}</div><div class="sum-value">${v}</div></div>`).join("");

  const W = el.clientWidth || 600, H = el.clientHeight || 240;
  const m = { t: 10, r: 4, b: 26, l: 36 };
  const iw = Math.max(10, W - m.l - m.r), ih = H - m.t - m.b;
  const maxV = Math.max(0, ...data.map((d) => d.created));
  const step = niceStep(maxV);
  const top = step * Math.max(1, Math.ceil(maxV / step));
  const y = (v) => m.t + ih - (v / top) * ih;
  const band = iw / Math.max(1, data.length);
  const bw = Math.max(4, Math.min(34, band * 0.62));
  const every = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(iw / 54))));

  let grid = "", axis = "", cols = "";
  for (let v = 0; v <= top; v += step) {
    grid += `<line x1="${m.l}" x2="${m.l + iw}" y1="${y(v)}" y2="${y(v)}"/>`;
    axis += `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  }
  data.forEach((d, i) => {
    const x0 = m.l + i * band;
    const x = x0 + (band - bw) / 2;
    const base = m.t + ih;
    let bar = "";
    if (d.created > 0) {
      const yt = y(d.created);
      const r = Math.min(4, (base - yt), bw / 2);
      bar = `<path class="bar" d="M${x},${base} V${yt + r} Q${x},${yt} ${x + r},${yt} H${x + bw - r} Q${x + bw},${yt} ${x + bw},${yt + r} V${base} Z"/>`;
    }
    if (i % every === 0 || i === data.length - 1) {
      axis += `<text x="${x0 + band / 2}" y="${H - 6}" text-anchor="middle">${dayFmt(d.date, { day: "numeric", month: "short" })}</text>`;
    }
    cols += `<g class="col" data-i="${i}"><rect class="band" x="${x0 + 1}" y="${m.t}" width="${Math.max(1, band - 2)}" height="${ih}" rx="6"/>${bar}</g>`;
  });

  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Accounts created per day, last ${data.length} days">
      <g class="grid">${grid}</g><g>${cols}</g><g class="axis">${axis}</g></svg>
    ${total ? "" : `<div class="chart-empty">No accounts created in this period</div>`}`;

  const tip = $("#chart-tip");
  el.querySelectorAll(".col").forEach((g) => {
    g.addEventListener("mousemove", (e) => {
      const d = data[+g.dataset.i];
      const row = (l, v) => `<div class="tip-row"><span>${l}</span><b>${fmtNum(v)}</b></div>`;
      tip.innerHTML = `<div class="tip-title">${esc(dayFmt(d.date, { weekday: "short", day: "numeric", month: "short" }))}</div>
        ${row("Accounts created", d.created)}<div class="tip-sep"></div>
        ${row("Active", d.active)}${row("Blocked", d.blocked)}${row("Failed setup", d.failed)}${d.other ? row("Stopped / other", d.other) : ""}
        <div class="tip-sep"></div>${row("Likes", d.likes)}${row("Matches", d.matches)}`;
      tip.classList.remove("hidden");
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let left = e.clientX + 14, topPx = e.clientY - th - 10;
      if (left + tw > window.innerWidth - 8) left = e.clientX - tw - 14;
      if (topPx < 8) topPx = e.clientY + 16;
      tip.style.left = left + "px";
      tip.style.top = topPx + "px";
    });
    g.addEventListener("mouseleave", () => tip.classList.add("hidden"));
  });
}

$("#chart-range").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("[data-days]");
  if (!b) return;
  state.days = +b.dataset.days;
  $$("#chart-range button").forEach((x) => x.classList.toggle("active", x === b));
  await loadDaily();
}));
window.addEventListener("resize", debounce(() => { if (state.tab === "dashboard") renderChart(); }, 150));

// --- Live bots ----------------------------------------------------------------

async function loadDashboardRuns() {
  const res = await api("/api/runs?limit=60");
  state.runs = new Map(res.items.map((r) => [r.id, r]));
  renderLiveCards();
}

function renderLiveCards() {
  if (state.tab !== "dashboard") return;
  const all = [...state.runs.values()].sort((a, b) => b.id - a.id);
  const active = all.filter((r) => ACTIVE.has(r.status))
    .sort((a, b) => (a.status === b.status ? b.id - a.id : a.status === "running" ? -1 : 1));
  const recent = all.filter((r) => !ACTIVE.has(r.status)).slice(0, 12);
  $("#cnt-active").textContent = active.length;
  $("#cnt-recent").textContent = recent.length;
  const list = state.liveFilter === "active" ? active : state.liveFilter === "recent" ? recent : [...active, ...recent];
  $("#live-cards").innerHTML = list.length ? list.map(botCard).join("")
    : state.liveFilter === "active"
      ? emptyState("cpu", "No accounts in progress", "Choose a configuration and how many accounts to create, then press Create accounts.")
      : emptyState("activity", "Nothing here yet", "Finished runs will show up here.");
}

function stepBar(r) {
  const flow = STEP_FLOW[r.kind] || STEP_FLOW.signup;
  let idx = flow.indexOf(r.step);
  const finished = r.step === "finished" || r.status === "done";
  if (finished) idx = flow.length;
  const running = ACTIVE.has(r.status);
  const segs = flow.map((_, i) => {
    if (i < idx) return `<span class="done"></span>`;
    if (i === idx && running) return `<span class="cur"></span>`;
    if (i === idx && !running) return `<span class="done"></span>`;
    return "<span></span>";
  }).join("");
  const ended = !running && r.status !== "done";
  let label = STEP_LABELS[r.step] || (r.step ? r.step : r.status === "queued" ? "Queued" : "—");
  if (ended && r.step === "finished") label = "Ended";
  const n = Math.min(flow.length, Math.max(0, idx + (running ? 1 : 0)));
  const right = r.status === "done" ? "complete" : ended ? r.status : `${n} / ${flow.length}`;
  return `<div class="steps s-${esc(r.status)}">${segs}</div>
    <div class="step-label"><b>${esc(label)}</b><span>${esc(right)}</span></div>`;
}

function botCard(r) {
  const name = r.requested_name || (r.kind === "message" ? `Account #${r.account_id}` : "New account");
  const initial = (r.requested_name || "?").trim().charAt(0).toUpperCase() || "?";
  const metrics = r.kind === "sync"
    ? `<div class="bot-metrics" style="grid-template-columns:1fr"><div><b>${icon("refresh")}</b><span>stats refresh</span></div></div>`
    : r.kind === "message"
    ? `<div class="bot-metrics" style="grid-template-columns:1fr"><div><b>${r.messages_sent}</b><span>messages sent</span></div></div>`
    : `<div class="bot-metrics">
        <div><b>${r.liked}</b><span>liked</span></div><div><b>${r.disliked}</b><span>disliked</span></div>
        <div><b>${r.matches}</b><span>matches</span></div><div><b>${r.swipes}</b><span>swipes</span></div></div>`;
  const stop = (r.account_id ? iconBtn("externalLink", `data-account="${r.account_id}"`, "Open account page") : "")
    + (ACTIVE.has(r.status) ? `<button class="btn small danger" data-stop="${r.id}">${icon("stop")}Stop</button>` : "");
  return `<div class="bot-card" data-run="${r.id}">
    <div class="bot-head">
      <div class="bot-avatar s-${esc(r.status)}">${esc(initial)}</div>
      <div class="bot-title">
        <div class="bot-name">${esc(name)}${r.kind === "message" ? icon("message") : ""}</div>
        <div class="bot-sub">${r.worker ? `${workerName(r.worker)} · ` : ""}#${r.id} · ${esc(r.config_name)}${r.account_id ? ` · account #${r.account_id}` : ""}</div>
      </div>
      ${badge(r.status)}
    </div>
    ${stepBar(r)}
    ${!ACTIVE.has(r.status) && r.reason ? `<div class="bot-reason" title="${esc(r.reason)}">${esc(r.reason)}</div>` : ""}
    ${metrics}
    <div class="bot-foot">
      <div class="meta">
        <span title="${esc(r.proxy_label || "no proxy")}">${icon("globe")}${esc(r.proxy_label ? r.proxy_label.split(" ")[0] : "direct")}</span>
        <span>${icon("clock")}${esc(duration(r) || "—")}</span>
      </div>
      ${stop}
    </div>
  </div>`;
}

$("#live-cards").addEventListener("click", guard(async (e) => {
  const stopBtn = e.target.closest("[data-stop]");
  if (stopBtn) {
    e.stopPropagation();
    await api(`/api/runs/${stopBtn.dataset.stop}/stop`, { method: "POST" });
    toast(`Stopping session #${stopBtn.dataset.stop}`);
    return;
  }
  const accBtn = e.target.closest("[data-account]");
  if (accBtn) { location.hash = `#account/${accBtn.dataset.account}`; return; }
  const card = e.target.closest("[data-run]");
  if (card) openRunModal(+card.dataset.run);
}));
$("#live-filter").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (!b) return;
  state.liveFilter = b.dataset.filter;
  $$("#live-filter button").forEach((x) => x.classList.toggle("active", x === b));
  renderLiveCards();
});
setInterval(() => { if (state.tab === "dashboard" && !document.hidden) renderLiveCards(); }, 5000);

// --- Launch -------------------------------------------------------------------

function fillConfigSelects() {
  const opts = (msg) => state.configs.map((c) =>
    `<option value="${c.id}">${esc(c.name)}${c.apk_profile_id ? "" : " (no APK profile!)"}${
      msg && !c.settings.messaging_enabled ? " — messaging off" : ""}</option>`).join("");
  for (const sel of [$("#launch-config"), $("#msg-config")].filter(Boolean)) {
    const prev = sel.value;
    sel.innerHTML = opts(sel.id === "msg-config") || `<option value="">— create a configuration first —</option>`;
    if (prev && state.configs.some((c) => String(c.id) === prev)) sel.value = prev;
  }
  renderLaunchInfo();
}

function renderLaunchInfo() {
  const c = state.configs.find((x) => String(x.id) === $("#launch-config").value);
  const s = state.stats;
  if (s) {
    const busy = s.running || s.queued;
    $("#launch-capacity").textContent = busy
      ? `${s.running} worker${s.running === 1 ? "" : "s"} busy — new accounts wait in the queue (${s.queued} waiting)`
      : `All workers free · ${s.parallel === 1 ? "one by one" : `${s.parallel} in parallel`}`;
    $("#launch-submit-label").textContent = busy ? "Add to queue" : "Create accounts";
  }
  if (!c) { $("#launch-config-info").innerHTML = ""; return; }
  const st = c.settings;
  const apkBad = !c.apk_profile_name || c.apk_profile_enabled === false;
  const chip = (t, bad) => `<span class="chip${bad ? " bad" : ""}">${esc(t)}</span>`;
  $("#launch-config-info").innerHTML = [
    chip(c.apk_profile_name ? `APK: ${c.apk_profile_name}${c.apk_profile_enabled === false ? " (disabled)" : ""}` : "No APK profile", apkBad),
    chip(`${Math.round(st.like_ratio * 100)}% likes`),
    chip(st.max_swipes ? `max ${st.max_swipes} swipes` : "swipe until blocked"),
    chip(st.require_proxy ? "proxy required" : "proxy optional", st.require_proxy && state.stats && !state.stats.proxies_enabled),
    chip(`${st.photo_pool.length || "all"} photos`),
    chip(`${st.name_source === "auto" ? "auto" : "custom"} names${c.names_unused !== undefined
      ? ` · ${fmtNum(c.names_unused)} unused` : ""}`, c.names_unused === 0),
    chip(`${fmtNum((state.photos || []).filter((p) => p.status === "available").length)} unused photos`,
      !(state.photos || []).some((p) => p.status === "available")),
  ].join("");
}
$("#launch-config").addEventListener("change", () => { renderLaunchInfo(); guard(renderSetupCheck)(); });

$("#launch-form").addEventListener("click", (e) => {
  const b = e.target.closest("[data-step]");
  if (!b) return;
  const input = $("#launch-form").elements.count;
  input.value = Math.min(500, Math.max(1, (+input.value || 1) + +b.dataset.step));
});

$("#launch-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { config_id: +f.get("config_id"), count: +f.get("count"), names: lines(f.get("names")) };
  const res = await api("/api/runs", { method: "POST", body });
  toast(`Creating ${res.run_ids.length} account(s)`);
  e.target.elements.names.value = "";
  guard(loadStats)();
  guard(loadPhotos)();
  state.liveFilter = "active";
  $$("#live-filter button").forEach((x) => x.classList.toggle("active", x.dataset.filter === "active"));
  await loadDashboardRuns();
}));

$("#stop-all-btn").onclick = guard(async () => {
  if (!confirm("Stop everything? Accounts in progress stop and the queue is cleared.")) return;
  const res = await api("/api/runs/stop-all", { method: "POST" });
  toast(`Stopping ${res.stopped} account session${res.stopped === 1 ? "" : "s"}`);
});

// ---------------------------------------------------------------------------
// Run detail + live log modal
// ---------------------------------------------------------------------------

async function openRunModal(id) {
  let lastId = 0, ws = null, closed = false, run = null;
  openModal(`Run #${id}`, `
    <div id="run-info"></div>
    <div class="log-toolbar">
      <label class="inline"><input type="checkbox" id="log-debug"> show debug (HTTP bodies)</label>
      <label class="inline"><input type="checkbox" id="log-follow" checked> auto-scroll</label>
      <span class="muted" id="log-count"></span>
      <div class="actions" style="margin-left:auto">
        <button class="btn small danger hidden" id="run-stop">Stop</button>
      </div>
    </div>
    <div class="log-view" id="log-view"></div>`, () => { closed = true; if (ws) ws.close(); });

  const view = $("#log-view");
  let count = 0;
  const applyDebug = () => {
    const show = $("#log-debug").checked;
    view.querySelectorAll(".l-debug").forEach((el) => (el.style.display = show ? "" : "none"));
  };
  $("#log-debug").onchange = applyDebug;

  const append = (entries) => {
    const showDebug = $("#log-debug")?.checked;
    const frag = document.createDocumentFragment();
    for (const l of entries) {
      if (l.id <= lastId) continue;
      lastId = l.id;
      count++;
      const div = document.createElement("div");
      div.className = "l-" + l.level;
      if (l.level === "debug" && !showDebug) div.style.display = "none";
      div.innerHTML = `<span class="ts">${esc(fmtTime(l.ts))}</span>${esc(l.msg)}`;
      frag.appendChild(div);
    }
    view.appendChild(frag);
    $("#log-count").textContent = `${count} lines`;
    if ($("#log-follow")?.checked) view.scrollTop = view.scrollHeight;
  };

  const renderInfo = (r) => {
    run = { ...run, ...r };
    const isActive = ACTIVE.has(run.status);
    $("#run-stop").classList.toggle("hidden", !isActive);
    $("#run-info").innerHTML = `<dl class="kv">
      <dt>Status</dt><dd>${badge(run.status)} ${esc(run.reason || "")}</dd>
      <dt>Type / step</dt><dd>${esc(run.kind)} · ${esc(run.step || "—")}</dd>
      <dt>Config</dt><dd>${esc(run.config_name)}${run.apk_profile_name ? " · APK: " + esc(run.apk_profile_name) : ""}</dd>
      <dt>Proxy</dt><dd>${esc(run.proxy_label || "—")}</dd>
      <dt>Account</dt><dd>${run.account_id ? `<a href="#account/${run.account_id}" data-close-modal>${esc(run.requested_name || "")} #${run.account_id}</a>` : esc(run.requested_name || "—")}</dd>
      <dt>Photo</dt><dd>${esc(run.photo || "—")}</dd>
      <dt>Counters</dt><dd>liked ${run.liked} · disliked ${run.disliked} · matches ${run.matches} · swipes ${run.swipes} · messages ${run.messages_sent}</dd>
      <dt>Time</dt><dd>created ${fmtDate(run.created_at)} · started ${fmtDate(run.started_at)} · finished ${fmtDate(run.finished_at)} ${run.started_at ? "· " + duration(run) : ""}</dd>
    </dl>`;
  };

  $("#run-stop").onclick = guard(async () => {
    await api(`/api/runs/${id}/stop`, { method: "POST" });
    toast(`Stopping run #${id}`);
  });

  // Open the socket first so nothing is missed, then backfill from REST.
  const buffer = [];
  let backfilled = false;
  ws = new WebSocket(wsUrl(`/ws/runs/${id}`));
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "log") backfilled ? append([msg]) : buffer.push(msg);
    else if (msg.type === "run" && !closed) renderInfo(msg.run);
  };

  try {
    renderInfo(await api(`/api/runs/${id}`));
    let batch;
    do {
      batch = await api(`/api/runs/${id}/logs?after_id=${lastId}&limit=5000`);
      if (closed) return;
      append(batch);
    } while (batch.length === 5000);
    backfilled = true;
    append(buffer);
    applyDebug();
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------------------------------------------------------------------
// Runs tab
// ---------------------------------------------------------------------------

const RUNS_LIMIT = 50;

async function loadRuns() {
  const status = $("#runs-status").value, kind = $("#runs-kind").value;
  const qs = new URLSearchParams({ limit: RUNS_LIMIT, offset: state.runsPage * RUNS_LIMIT });
  if (status) qs.set("status", status);
  if (kind) qs.set("kind", kind);
  const res = await api("/api/runs?" + qs);
  $("#runs-table").innerHTML = `<thead><tr>
      <th>#</th><th>Type</th><th>Status</th><th>Name / account</th><th>Config</th><th>Proxy</th><th>Step</th>
      <th class="num">Liked</th><th class="num">Disliked</th><th class="num">Matches</th><th class="num">Msgs</th>
      <th>Created</th><th>Duration</th><th>Reason</th><th></th></tr></thead>
    <tbody>${res.items.map((r) => `<tr class="clickable" data-run="${r.id}">
      <td>${r.id}</td><td>${esc(r.kind)}</td><td>${badge(r.status)}</td>
      <td>${esc(r.requested_name || "")}${r.account_id ? ` <span class="muted">#${r.account_id}</span>` : ""}</td>
      <td>${esc(r.config_name)}</td><td class="wrapcell">${esc(r.proxy_label)}</td><td>${esc(r.step)}</td>
      <td class="num">${r.liked}</td><td class="num">${r.disliked}</td><td class="num">${r.matches}</td><td class="num">${r.messages_sent}</td>
      <td>${fmtDate(r.created_at)}</td><td>${esc(duration(r))}</td><td class="wrapcell" title="${esc(r.reason)}">${esc(r.reason)}</td>
      <td class="actions">${ACTIVE.has(r.status)
        ? `<button class="btn small danger" data-stop="${r.id}">Stop</button>`
        : iconBtn("trash", `data-del="${r.id}"`, "Delete run and its logs", "danger")}</td>
    </tr>`).join("") || `<tr><td colspan="15" class="muted">No runs</td></tr>`}</tbody>`;
  renderPager("#runs-pager", res.total, RUNS_LIMIT, state.runsPage, (p) => { state.runsPage = p; guard(loadRuns)(); });
}

$("#runs-table").addEventListener("click", guard(async (e) => {
  const stop = e.target.closest("[data-stop]");
  const del = e.target.closest("[data-del]");
  if (stop) {
    await api(`/api/runs/${stop.dataset.stop}/stop`, { method: "POST" });
    return toast("Stopping…");
  }
  if (del) {
    if (!confirm(`Delete run #${del.dataset.del} and its logs?`)) return;
    await api(`/api/runs/${del.dataset.del}`, { method: "DELETE" });
    return loadRuns();
  }
  const row = e.target.closest("[data-run]");
  if (row) openRunModal(+row.dataset.run);
}));
$("#runs-status").onchange = $("#runs-kind").onchange = () => { state.runsPage = 0; guard(loadRuns)(); };
$("#runs-refresh").onclick = guard(loadRuns);
$("#runs-cleanup").onclick = guard(async () => {
  const days = prompt("Delete logs of finished runs older than how many days?", "7");
  if (days === null) return;
  const deleteRuns = confirm("Also delete the run rows themselves? (OK = yes, Cancel = keep runs, delete logs only)");
  const res = await api("/api/runs/cleanup", { method: "POST", body: { days: +days || 0, delete_runs: deleteRuns } });
  toast(`Cleaned ${res.runs_cleaned} run(s)`);
  loadRuns();
});

function renderPager(sel, total, limit, page, go) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const el = $(sel);
  el.innerHTML = `<span class="muted">${total} total · page ${page + 1} / ${pages}</span>
    <button class="btn small" data-p="${page - 1}" ${page <= 0 ? "disabled" : ""}>${icon("chevronLeft")}Prev</button>
    <button class="btn small" data-p="${page + 1}" ${page + 1 >= pages ? "disabled" : ""}>Next${icon("chevronRight")}</button>`;
  el.onclick = (e) => { const b = e.target.closest("[data-p]"); if (b && !b.disabled) go(+b.dataset.p); };
}

// ---------------------------------------------------------------------------
// Configurations
// ---------------------------------------------------------------------------

async function loadConfigs() {
  state.configs = await api("/api/configs");
  fillConfigSelects();
  $("#configs-table").innerHTML = `<thead><tr>
      <th>Name</th><th>APK profile</th><th class="num">Like ratio</th><th class="num">Max swipes</th>
      <th class="num">Block after</th><th>Proxy</th><th class="num">Photos</th><th class="num">Locations</th><th>Names</th><th>Messaging</th>
      <th>Updated</th><th></th></tr></thead>
    <tbody>${state.configs.map((c) => {
      const s = c.settings;
      return `<tr>
        <td><b>${esc(c.name)}</b></td>
        <td>${!c.apk_profile_name ? `<span class="badge bad">missing</span>`
          : esc(c.apk_profile_name) + (c.apk_profile_enabled === false ? ` <span class="badge bad">disabled</span>`
          : c.apk_profile_fail_streak >= 3 ? ` <span class="badge warn">failing</span>` : "")}</td>
        <td class="num">${Math.round(s.like_ratio * 100)}%</td>
        <td class="num">${s.max_swipes || "∞"}</td>
        <td class="num">${s.block_threshold} fails</td>
        <td>${s.require_proxy ? "required" : "optional"}</td>
        <td class="num">${s.photo_pool.length || "all"}</td>
        <td class="num">${s.locations.length}</td>
        <td>${esc(s.name_source === "auto" ? "Auto" : "Custom")} · <span class="${c.names_unused ? "" : "sr-danger"}">${fmtNum(c.names_unused)} unused</span></td>
        <td>${s.messaging_enabled ? `<span class="badge ok">on</span>` : `<span class="badge">off</span>`}</td>
        <td>${fmtDate(c.updated_at)}</td>
        <td class="actions">
          <button class="btn small primary" data-launch="${c.id}">${icon("play")}Start</button>
          ${iconBtn("pencil", `data-edit="${c.id}"`, "Edit configuration")}
          ${iconBtn("copy", `data-dup="${c.id}"`, "Duplicate configuration")}
          ${iconBtn("trash", `data-del="${c.id}"`, "Delete configuration", "danger")}
        </td></tr>`;
    }).join("") || `<tr><td colspan="12" class="muted">No configurations</td></tr>`}</tbody>`;
}

$("#configs-table").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.launch) {
    switchTab("dashboard");
    $("#launch-config").value = b.dataset.launch;
    $("#launch-form").elements.count.focus();
  } else if (b.dataset.edit) {
    openConfigEditor(state.configs.find((c) => c.id === +b.dataset.edit));
  } else if (b.dataset.dup) {
    await api(`/api/configs/${b.dataset.dup}/duplicate`, { method: "POST" });
    await loadConfigs();
  } else if (b.dataset.del) {
    const c = state.configs.find((x) => x.id === +b.dataset.del);
    if (!confirm(`Delete configuration "${c.name}"?`)) return;
    await api(`/api/configs/${c.id}`, { method: "DELETE" });
    await loadConfigs();
  }
}));

$("#new-config-btn").onclick = guard(async () => {
  const meta = await api("/api/meta");
  openConfigEditor({ id: null, name: "", apk_profile_id: state.apks[0]?.id ?? null, settings: meta.default_settings });
});

// Values the decoded APK knows for both relationship fields (RelationshipItem.isFlirt / isFriendship).
const RELATIONSHIP_LABELS = { FLIRT: "Flirt / Dating (FLIRT)", FRIENDSHIP: "Freundschaft / Friendship (FRIENDSHIP)" };
function relationshipOptions(current) {
  const values = (state.meta && state.meta.relationship_values) || Object.keys(RELATIONSHIP_LABELS);
  return values.map((v) => `<option value="${v}" ${v === current ? "selected" : ""}>${esc(RELATIONSHIP_LABELS[v] || v)}</option>`).join("");
}

// What Jaumo's own signup/defaults response offered at the last registration.
function offeredByJaumo() {
  const sd = state.meta && state.meta.signup_defaults;
  if (!sd) {
    return `<p class="field-hint">Jaumo's own list of options is saved automatically at the next account creation
      (from <code>signup/defaults</code>) and will be shown here.</p>`;
  }
  const found = [];
  (function walk(v, path) {
    if (Array.isArray(v)) v.forEach((x, i) => walk(x, path));
    else if (v && typeof v === "object") Object.entries(v).forEach(([k, x]) => walk(x, path.concat(k)));
    else if (path.some((k) => /relationship/i.test(k)) && typeof v === "string" && /^[A-Z_]{3,}$/.test(v)) found.push(v);
  })(sd.data, []);
  const uniq = [...new Set(found)];
  const unknown = uniq.filter((v) => !(state.meta.relationship_values || []).includes(v));
  return `<div class="sent-list"><span>Jaumo offers (signup/defaults, ${esc(fmtDate(sd.received_at))}):</span>
      ${uniq.length ? uniq.map((v) => `<code>${esc(v)}</code>`).join(" ") : "no relationship values found in the response"}
      ${unknown.length ? `<div class="sr-warn">Not in the dropdown yet: ${unknown.map(esc).join(", ")} — tell the developer to add them.</div>` : ""}
      <details><summary>Show full response</summary><pre class="mono pre-json">${esc(JSON.stringify(sd.data, null, 2))}</pre></details></div>`;
}

const DELAY_LABELS = {
  after_signup: "After signup", after_location: "After location", after_refresh: "After token refresh",
  after_profile: "After profile fetch", before_photo: "Before photo upload", after_photo: "After photo upload",
  between_swipes: "Between swipes", between_batches: "Between card batches", before_message: "Before each message",
};

async function openConfigEditor(c) {
  const s = c.settings;
  state.meta = await api("/api/meta");
  if (!state.settings) state.settings = await api("/api/settings");
  await loadPhotos();
  const apkOpts = `<option value="">— none —</option>` + state.apks.map((a) =>
    `<option value="${a.id}" ${a.id === c.apk_profile_id ? "selected" : ""}>${esc(a.name)}</option>`).join("");
  const photoSet = new Set(s.photo_pool);
  const photos = state.photos.map((p) => `<label class="pp-${p.status}" title="${esc(p.name)} — ${p.status}">
      <input type="checkbox" name="photo_pool" value="${esc(p.name)}" ${photoSet.has(p.name) ? "checked" : ""}
        ${p.status !== "available" && !photoSet.has(p.name) ? "disabled" : ""}>
      <img src="/api/photos/${encodeURIComponent(p.name)}/thumb" loading="lazy" alt="">
      <span>${p.status === "available" ? esc(p.name) : esc(p.status)}</span></label>`).join("");
  const availablePhotos = state.photos.filter((p) => p.status === "available").length;
  const delays = Object.entries(DELAY_LABELS).map(([k, label]) => `<label>${esc(label)}
      <span class="pair"><input type="number" step="any" min="0" name="d_${k}_0" value="${s.delays[k][0]}"> –
      <input type="number" step="any" min="0" name="d_${k}_1" value="${s.delays[k][1]}"> s</span></label>`).join("");

  openModal(c.id ? `Edit configuration — ${c.name}` : "New configuration", `
  <form id="config-form">
    <div class="form-grid">
      <label class="span-2">Name<input name="name" value="${esc(c.name)}" required></label>
      <label>APK profile<select name="apk_profile_id">${apkOpts}</select></label>
      <label class="inline" style="align-self:end"><input type="checkbox" name="require_proxy" ${s.require_proxy ? "checked" : ""}> Require proxy</label>
    </div>

    <div class="form-section"><h3>Swiping</h3>
      <div class="form-grid">
        <label>Like ratio (0–1)<input type="number" name="like_ratio" step="any" min="0" max="1" value="${s.like_ratio}"></label>
        <label>Max swipes (0 = until blocked/stopped)<input type="number" name="max_swipes" min="0" value="${s.max_swipes}"></label>
        <label>Blocked after N consecutive failures<input type="number" name="block_threshold" min="1" value="${s.block_threshold}"></label>
        <label>Finish after N empty card batches<input type="number" name="max_empty_batches" min="1" value="${s.max_empty_batches}"></label>
        <label>Request timeout (s)<input type="number" name="request_timeout" min="5" value="${s.request_timeout}"></label>
      </div>
    </div>

    <div class="form-section"><h3>Profile (always female)</h3>
      <div class="form-grid">
        <label>Age min<input type="number" name="age_min" min="18" max="99" value="${s.age_min}"></label>
        <label>Age max<input type="number" name="age_max" min="18" max="99" value="${s.age_max}"></label>
      </div>
      <h3>Names</h3>
      <div class="choice-cards">
        <label class="choice"><input type="radio" name="name_source" value="auto" ${s.name_source === "auto" ? "checked" : ""}>
          <div><b>Auto names</b><span>Built-in list of ${state.meta.auto_names.length} common female first names</span></div></label>
        <label class="choice"><input type="radio" name="name_source" value="custom" ${s.name_source === "custom" ? "checked" : ""}>
          <div><b>Custom list</b><span>Only the names you paste below</span></div></label>
      </div>
      <p class="field-hint rule-hint">${icon("shieldCheck")}Whether names and photos may be reused is one global rule for all configurations —
        see <a href="#settings" data-close-modal>Settings</a>.</p>
      <label id="custom-names-box" class="${s.name_source === "custom" ? "" : "hidden"}">Custom names (one per line)
        <textarea name="name_pool" rows="6">${esc(s.name_pool.join("\n"))}</textarea></label>
      <div class="name-usage" id="name-usage"><span class="muted">Checking which names are used…</span></div>
      <h3 style="margin-top:14px">Profile photo</h3>
      <p class="field-hint">None checked = any unused photo from the whole library (${fmtNum(availablePhotos)} available).
        Check photos to limit this configuration to them. Used photos are greyed out. <a href="#photos" data-close-modal>Manage photo library</a></p>
      <div class="photo-pick">${photos || `<span class="muted">No photos uploaded yet</span>`}</div>
    </div>

    <div class="form-section"><h3>Locations</h3>
      <div class="form-grid one-col">
        <label class="span-2"><span>Locations — <code>label,lat,lon</code> or <code>label,lat,lon,radius_km</code> per line</span>
          <span class="field-hint">One city is picked at random for each account. With a radius, each account gets its own random
            point inside that circle around the city centre (like real users spread over a city). Jaumo turns the point into the
            real city at run time.</span>
          <span class="radius-row">Default radius around each city
            <input type="number" name="location_radius_km" min="0" max="100" step="any" value="${s.location_radius_km ?? 0}"> km
            <span class="field-hint">0 = exact city centre · e.g. 15 = anywhere within 15 km · a 4th value on a line overrides it for that city</span></span>
          <textarea name="locations" rows="8">${esc(s.locations.map((l) => `${l.label},${l.lat},${l.lon}${l.radius_km != null ? `,${l.radius_km}` : ""}`).join("\n"))}</textarea></label>
      </div>
    </div>

    <div class="form-section"><h3>Messaging</h3>
      <label class="toggle-row"><input type="checkbox" class="switch" name="messaging_enabled" ${s.messaging_enabled ? "checked" : ""}>
        <div><b>Messaging enabled</b><span>Allow the messaging job (Accounts page) to message matches with this configuration. Signup bots never send messages.</span></div></label>
      <label>Message templates (one per line, random pick)
        <textarea name="message_templates" rows="5">${esc(s.message_templates.join("\n"))}</textarea></label>
    </div>

    <div class="adv-head">Advanced — the defaults work; change only if needed</div>
    <details class="form-section adv" data-adv="signup"><summary><span><b>Signup details</b><small>Values sent to Jaumo at registration (relationship, looking for, brands)</small></span></summary>
      <p class="field-hint">Exactly the fields sent to Jaumo when an account is registered. The defaults are the values used
        so far — change them only if the APK expects other values.</p>
      <div class="form-grid" style="margin-top:10px">
        <label>Gender<input value="Female (2)" disabled></label>
        <label>Looking for<select name="looking_for_gender">
          <option value="1" ${s.looking_for_gender === 1 ? "selected" : ""}>Men (1)</option>
          <option value="2" ${s.looking_for_gender === 2 ? "selected" : ""}>Women (2)</option></select></label>
        <label>Relationship search<select name="relationship_search">${relationshipOptions(s.relationship_search)}</select></label>
        <label>Dating relationship search<select name="dating_relationship_search">${relationshipOptions(s.dating_relationship_search)}</select></label>
      </div>
      ${offeredByJaumo()}
      <label class="toggle-row"><input type="checkbox" class="switch" name="allow_in_all_brands" ${s.allow_in_all_brands ? "checked" : ""}>
        <div><b>Allow in all brands</b><span>Sent as allow_in_all_brands=1 (profile visible across Jaumo's partner apps).</span></div></label>
      <div class="sent-list">
        <span>Also sent:</span><code>name</code> from Names · <code>birthday</code> from the age range · <code>photo_url</code> (fixed value from the original script) ·
        <code>location_permission</code> and <code>notifications_services</code> empty (as the app does).
        After signup the location is set and the profile photo uploaded. Nothing else (bio, height, …) is set.
      </div>
    </details>
    <details class="form-section adv" data-adv="devices"><summary><span><b>Devices</b><small>${s.devices.length} phone models — one is picked per account</small></span></summary>
      <label><span>Devices — <code>manufacturer;model;brand</code> per line</span>
        <textarea name="devices" rows="8">${esc(s.devices.map((d) => `${d.manufacturer};${d.model};${d.brand}`).join("\n"))}</textarea></label>
    </details>
    <details class="form-section adv" data-adv="delays"><summary><span><b>Delays</b><small>Random pauses between steps, in seconds (min – max)</small></span></summary>
      <div class="delay-grid">${delays}</div>
    </details>

    <p class="error" id="config-error"></p>
    <div class="modal-foot">
      <button type="button" class="btn ghost" id="config-cancel">Cancel</button>
      <button type="submit" class="btn primary">Save</button>
    </div>
  </form>`);

  $("#config-cancel").onclick = closeModal;
  const form = $("#config-form");
  form.addEventListener("invalid", (e) => { const d = e.target.closest("details"); if (d) d.open = true; }, true);
  let usage = {};
  const renderNameUsage = () => {
    const custom = form.elements.name_source.value === "custom";
    $("#custom-names-box").classList.toggle("hidden", !custom);
    const seen = new Set();
    const pool = (custom ? lines(form.elements.name_pool.value) : state.meta.auto_names)
      .filter((n) => !seen.has(n.toLowerCase()) && seen.add(n.toLowerCase()));
    const isUsed = (n) => (usage[n.trim().toLocaleLowerCase()] || 0) > 0;
    const used = pool.filter(isUsed);
    const unique = state.settings ? state.settings.identity.unique_names : true;
    const shown = custom ? pool : used;
    $("#name-usage").innerHTML = `<div class="name-usage-head">
        <span><b>${fmtNum(pool.length - used.length)}</b> unused · <b>${fmtNum(used.length)}</b> already used of ${fmtNum(pool.length)}
          ${unique ? "" : `<span class="muted">· unique off, names may repeat</span>`}</span>
        ${custom && used.length ? `<button type="button" class="btn small" id="drop-used">Remove used names</button>` : ""}
      </div>
      ${shown.length ? `<div class="name-chips">${shown.map((n) =>
        `<span class="name-chip${isUsed(n) ? " used" : ""}" title="${isUsed(n) ? "already used by an account" : "available"}">${esc(n)}</span>`).join("")}</div>`
        : `<span class="muted">${custom ? "No names yet — paste one per line above." : "None of the auto names have been used yet."}</span>`}`;
    const drop = $("#drop-used");
    if (drop) drop.onclick = () => {
      form.elements.name_pool.value = lines(form.elements.name_pool.value).filter((n) => !isUsed(n)).join("\n");
      renderNameUsage();
    };
  };
  form.addEventListener("change", (e) => { if (["name_source", "unique_names"].includes(e.target.name)) renderNameUsage(); });
  form.elements.name_pool.addEventListener("input", debounce(renderNameUsage, 250));
  api("/api/names/usage").then((u) => { usage = u; if (document.body.contains(form)) renderNameUsage(); })
    .catch(() => { $("#name-usage").textContent = "Could not load name usage"; });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    const fd = new FormData(e.target);
    $("#config-error").textContent = "";
    try {
      const locations = lines(f.locations.value).map((l, i) => {
        const [label, lat, lon, radius] = l.split(",").map((x) => x.trim());
        if (!label || !lat || !lon || isNaN(+lat) || isNaN(+lon) || Math.abs(+lat) > 90 || Math.abs(+lon) > 180
            || (radius !== undefined && radius !== "" && (isNaN(+radius) || +radius < 0 || +radius > 100))) {
          throw new Error(`Location line ${i + 1} is invalid: "${l}" (label,lat,lon[,radius_km 0–100])`);
        }
        return { label, lat, lon, radius_km: radius === undefined || radius === "" ? null : +radius };
      });
      const devices = lines(f.devices.value).map((l, i) => {
        const [manufacturer, model, brand] = l.split(";").map((x) => x.trim());
        if (!manufacturer || !model || !brand) throw new Error(`Device line ${i + 1} is invalid: "${l}"`);
        return { manufacturer, model, brand };
      });
      const delaysOut = {};
      for (const k of Object.keys(DELAY_LABELS)) delaysOut[k] = [+f[`d_${k}_0`].value, +f[`d_${k}_1`].value];
      const body = {
        name: f.name.value.trim(),
        apk_profile_id: f.apk_profile_id.value ? +f.apk_profile_id.value : null,
        settings: {
          require_proxy: f.require_proxy.checked,
          like_ratio: +f.like_ratio.value,
          location_radius_km: +f.location_radius_km.value || 0,
          max_swipes: +f.max_swipes.value,
          block_threshold: +f.block_threshold.value,
          max_empty_batches: +f.max_empty_batches.value,
          request_timeout: +f.request_timeout.value,
          age_min: +f.age_min.value,
          age_max: +f.age_max.value,
          name_source: f.name_source.value,
          looking_for_gender: +f.looking_for_gender.value,
          relationship_search: f.relationship_search.value.trim(),
          dating_relationship_search: f.dating_relationship_search.value.trim(),
          allow_in_all_brands: f.allow_in_all_brands.checked,
          messaging_enabled: f.messaging_enabled.checked,
          name_pool: lines(f.name_pool.value),
          photo_pool: fd.getAll("photo_pool"),
          locations, devices,
          message_templates: lines(f.message_templates.value),
          delays: delaysOut,
        },
      };
      await api(c.id ? `/api/configs/${c.id}` : "/api/configs", { method: c.id ? "PUT" : "POST", body });
      closeModal();
      toast("Configuration saved");
      await loadConfigs();
    } catch (err) {
      $("#config-error").textContent = err.message;
    }
  });
}

// --- APK profiles ----------------------------------------------------------

const HEALTH_BADGE = { ok: "ok", warning: "warn", failing: "bad", disabled: "bad", untested: "" };

async function loadApks() {
  state.apks = await api("/api/apk-profiles");
  $("#apk-table").innerHTML = `<thead><tr><th>Name</th><th>Health</th><th>Enabled</th><th>Used by</th>
      <th>Last OK</th><th>Last failure</th><th class="num">OK / fail</th><th>Client ID</th><th>User-Agent</th><th></th></tr></thead>
    <tbody>${state.apks.map((a) => `<tr>
      <td><b>${esc(a.name)}</b>${a.notes ? `<div class="muted wrapcell" title="${esc(a.notes)}">${esc(a.notes)}</div>` : ""}</td>
      <td><span class="badge ${HEALTH_BADGE[a.health]}">${esc(a.health)}</span>${a.fail_streak ? ` <span class="muted">streak ${a.fail_streak}</span>` : ""}</td>
      <td><input type="checkbox" data-toggle="${a.id}" ${a.enabled ? "checked" : ""}></td>
      <td>${a.used_by.length ? esc(a.used_by.join(", ")) : `<span class="muted">—</span>`}</td>
      <td>${fmtDate(a.last_ok_at)}</td>
      <td title="${esc(a.last_error)}">${fmtDate(a.last_fail_at)}${a.last_error ? `<div class="muted mono wrapcell">${esc(a.last_error)}</div>` : ""}</td>
      <td class="num">${a.ok_count} / ${a.fail_count}</td>
      <td class="mono wrapcell" title="${esc(a.client_id)}">${esc(a.client_id)}</td>
      <td class="mono wrapcell" title="${esc(a.user_agent)}">${esc(a.user_agent)}</td>
      <td class="actions">${iconBtn("pencil", `data-edit="${a.id}"`, "Edit APK profile")}
        ${a.used_by.length ? `<button class="btn small" data-move="${a.id}">Switch configs…</button>` : ""}
        ${a.fail_streak ? iconBtn("refresh", `data-reset="${a.id}"`, "Clear failure streak") : ""}
        ${iconBtn("trash", `data-del="${a.id}"`, "Delete APK profile", "danger")}</td></tr>`).join("")
      || `<tr><td colspan="10" class="muted">No APK profiles — add one, bots cannot run without it</td></tr>`}</tbody>`;
}

$("#apk-table").addEventListener("change", guard(async (e) => {
  const t = e.target;
  if (!t.dataset.toggle) return;
  const a = state.apks.find((x) => x.id === +t.dataset.toggle);
  await api(`/api/apk-profiles/${a.id}`, { method: "PATCH", body: { enabled: t.checked } });
  toast(`APK profile "${a.name}" ${t.checked ? "enabled" : "disabled"}`);
  await Promise.all([loadApks(), loadConfigs()]);
  if (!t.checked && a.used_by.length) openMoveConfigs(state.apks.find((x) => x.id === a.id));
}));

$("#apk-table").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  const id = +(b.dataset.edit || b.dataset.del || b.dataset.move || b.dataset.reset);
  const a = state.apks.find((x) => x.id === id);
  if (b.dataset.edit) return openApkEditor(a);
  if (b.dataset.move) return openMoveConfigs(a);
  if (b.dataset.reset) {
    await api(`/api/apk-profiles/${id}/reset-health`, { method: "POST" });
    return Promise.all([loadApks(), loadConfigs()]);
  }
  if (!confirm(`Delete APK profile "${a.name}"?`)) return;
  await api(`/api/apk-profiles/${a.id}`, { method: "DELETE" });
  await Promise.all([loadApks(), loadConfigs()]);
}));

function openMoveConfigs(a) {
  const targets = state.apks.filter((x) => x.id !== a.id);
  if (!targets.length) return toast("Add another APK profile first, then switch the configs to it", true);
  const rank = { ok: 0, untested: 1, warning: 2, failing: 3, disabled: 4 };
  const best = [...targets].sort((x, y) => rank[x.health] - rank[y.health])[0];
  openModal(`Switch configs away from "${a.name}"`, `
    <p>These configurations use <b>${esc(a.name)}</b>: ${esc(a.used_by.join(", "))}</p>
    <p class="hint">Accounts already in progress keep their current APK profile; new ones use the new profile.</p>
    <label>Switch to<select id="move-target">${targets.map((x) =>
      `<option value="${x.id}" ${x.id === best.id ? "selected" : ""}>${esc(x.name)} — ${esc(x.health)}${x.enabled ? "" : " (disabled)"}</option>`).join("")}</select></label>
    <div class="modal-foot"><button class="btn ghost" id="move-cancel">Cancel</button>
      <button class="btn primary" id="move-ok">Switch ${a.used_by.length} config(s)</button></div>`);
  $("#move-cancel").onclick = closeModal;
  $("#move-ok").onclick = guard(async () => {
    const res = await api(`/api/apk-profiles/${a.id}/move-configs`, { method: "POST",
      body: { to_apk_profile_id: +$("#move-target").value } });
    closeModal();
    toast(`Switched ${res.moved} config(s) to "${res.to}"`);
    await Promise.all([loadApks(), loadConfigs()]);
    guard(loadStats)();
  });
}
$("#new-apk-btn").onclick = () => openApkEditor(null);

function openApkEditor(a) {
  const v = a || { name: "", client_id: "", user_agent: "Android 202609.1.4 (1001864) (GooglePlay;Free)",
    package_id: "com.jaumo", os_version: "14", accept_language: "en_US" };
  openModal(a ? `Edit APK profile — ${a.name}` : "New APK profile", `
    <form id="apk-form">
      <div class="form-grid">
        <label class="span-2">Name<input name="name" value="${esc(v.name)}" required></label>
        <label class="span-2">Client ID<input name="client_id" value="${esc(v.client_id)}" required class="mono"></label>
        <label class="span-2">Sign secret ${a ? `(leave empty to keep ${esc(a.sign_secret_hint)})` : ""}
          <input name="sign_secret" type="password" autocomplete="off" ${a ? "" : "required"} class="mono"></label>
        <label class="span-2">User-Agent<input name="user_agent" value="${esc(v.user_agent)}" required class="mono"></label>
        <label>Package ID<input name="package_id" value="${esc(v.package_id)}"></label>
        <label>Android OS version<input name="os_version" value="${esc(v.os_version)}"></label>
        <label>Accept-Language<input name="accept_language" value="${esc(v.accept_language)}"></label>
        <label class="inline" style="align-self:end"><input type="checkbox" name="enabled" ${v.enabled === false ? "" : "checked"}> Enabled</label>
        <label class="span-2">Notes (e.g. APK version, where it came from, why it was disabled)
          <textarea name="notes" rows="2">${esc(v.notes || "")}</textarea></label>
      </div>
      <p class="error" id="apk-error"></p>
      <div class="modal-foot"><button type="button" class="btn ghost" id="apk-cancel">Cancel</button>
        <button class="btn primary" type="submit">Save</button></div>
    </form>`);
  $("#apk-cancel").onclick = closeModal;
  $("#apk-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target));
    body.enabled = e.target.elements.enabled.checked;
    try {
      await api(a ? `/api/apk-profiles/${a.id}` : "/api/apk-profiles", { method: a ? "PUT" : "POST", body });
      closeModal();
      toast("APK profile saved");
      await Promise.all([loadApks(), loadConfigs()]);
    } catch (err) {
      $("#apk-error").textContent = err.message;
    }
  });
}

// ---------------------------------------------------------------------------
// Proxies
// ---------------------------------------------------------------------------

let proxies = [];

async function loadProxies() {
  proxies = await api("/api/proxies");
  const ids = new Set(proxies.map((p) => p.id));
  state.proxySelected = new Set([...state.proxySelected].filter((id) => ids.has(id)));
  $("#proxies-table").innerHTML = `<thead><tr>
      <th><input type="checkbox" id="proxy-all"></th><th>#</th><th>Label</th><th>Host:port</th><th>User</th>
      <th>Mode</th><th>Enabled</th><th class="num">In use</th><th class="num">Used</th><th>Last test</th><th></th></tr></thead>
    <tbody>${proxies.map((p) => {
      const test = p.last_test_at == null ? `<span class="muted">never</span>`
        : p.last_test_ok ? `<span class="badge ok">ok</span> ${esc(p.last_test_ip)} · ${esc(p.last_test_country)}`
        : `<span class="badge bad" title="${esc(p.last_test_error)}">fail</span> <span class="muted wrapcell">${esc((p.last_test_error || "").slice(0, 60))}</span>`;
      return `<tr>
        <td><input type="checkbox" data-sel="${p.id}" ${state.proxySelected.has(p.id) ? "checked" : ""}></td>
        <td>${p.id}</td><td>${esc(p.label)}</td>
        <td class="mono">${esc(p.scheme)}://${esc(p.host)}:${p.port}</td>
        <td class="mono wrapcell" title="${esc(p.username)}">${esc(p.username)}</td>
        <td>${p.shared ? `<span class="badge info">shared</span>` : `<span class="badge">dedicated</span>`}</td>
        <td><input type="checkbox" data-toggle="${p.id}" ${p.enabled ? "checked" : ""}></td>
        <td class="num">${p.in_use}</td><td class="num">${p.use_count}</td>
        <td title="${esc(fmtDate(p.last_test_at))}">${test}</td>
        <td class="actions">${iconBtn("zap", `data-test="${p.id}"`, "Test proxy")}
          ${iconBtn("pencil", `data-edit="${p.id}"`, "Edit proxy")}
          ${iconBtn("trash", `data-del="${p.id}"`, "Delete proxy", "danger")}</td></tr>`;
    }).join("") || `<tr><td colspan="11" class="muted">No proxies yet</td></tr>`}</tbody>`;
  updateProxySelected();
}

function updateProxySelected() {
  $("#proxy-selected").textContent = `${state.proxySelected.size} selected`;
  $$("#proxy-bulk-actions [data-action]").forEach((b) => (b.disabled = !state.proxySelected.size));
  const all = $("#proxy-all");
  if (all) all.checked = proxies.length > 0 && state.proxySelected.size === proxies.length;
}

$("#proxies-table").addEventListener("change", guard(async (e) => {
  const t = e.target;
  if (t.id === "proxy-all") {
    state.proxySelected = t.checked ? new Set(proxies.map((p) => p.id)) : new Set();
    $$("[data-sel]").forEach((c) => (c.checked = t.checked));
    return updateProxySelected();
  }
  if (t.dataset.sel) {
    t.checked ? state.proxySelected.add(+t.dataset.sel) : state.proxySelected.delete(+t.dataset.sel);
    return updateProxySelected();
  }
  if (t.dataset.toggle) {
    await api(`/api/proxies/${t.dataset.toggle}`, { method: "PUT", body: { enabled: t.checked } });
  }
}));

$("#proxies-table").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.test) {
    b.disabled = true; b.classList.add("spin");
    const r = await api(`/api/proxies/${b.dataset.test}/test`, { method: "POST" });
    toast(r.ok ? `OK — ${r.ip} (${r.country})` : `Failed: ${r.error}`, !r.ok);
    return loadProxies();
  }
  if (b.dataset.edit) return openProxyEditor(proxies.find((p) => p.id === +b.dataset.edit));
  if (b.dataset.del) {
    if (!confirm("Delete this proxy?")) return;
    await api(`/api/proxies/${b.dataset.del}`, { method: "DELETE" });
    return loadProxies();
  }
}));

$("#proxy-bulk-actions").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("[data-action]");
  if (!b || !state.proxySelected.size) return;
  const action = b.dataset.action;
  if (action === "delete" && !confirm(`Delete ${state.proxySelected.size} proxies?`)) return;
  b.disabled = true;
  const res = await api("/api/proxies/bulk-action", { method: "POST", body: { ids: [...state.proxySelected], action } });
  if (action === "test") toast(`Tested ${res.tested}: ${res.ok} ok`);
  if (action === "delete") state.proxySelected.clear();
  await loadProxies();
}));

$("#proxy-test-all").onclick = guard(async () => {
  const btn = $("#proxy-test-all");
  btn.disabled = true;
  try {
    const res = await api("/api/proxies/test-all", { method: "POST" });
    toast(`Tested ${res.tested}: ${res.ok} ok`);
  } finally { btn.disabled = false; }
  await loadProxies();
});

$("#proxy-bulk-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = e.target.elements;
  if (f.replace.checked && !confirm("Replace ALL existing proxies with these lines?")) return;
  const res = await api("/api/proxies/bulk", { method: "POST", body: {
    text: f.text.value, shared: f.shared.value === "1", label: f.label.value.trim(), replace: f.replace.checked,
  } });
  toast(`Added ${res.added} proxy line(s)`);
  e.target.reset();
  await loadProxies();
}));

function openProxyEditor(p) {
  openModal(`Edit proxy #${p.id}`, `
    <form id="proxy-form">
      <div class="form-grid">
        <label>Label<input name="label" value="${esc(p.label)}"></label>
        <label>Scheme<select name="scheme">${["http", "https", "socks5", "socks5h", "socks4"].map((s) =>
          `<option ${s === p.scheme ? "selected" : ""}>${s}</option>`).join("")}</select></label>
        <label>Host<input name="host" value="${esc(p.host)}" required></label>
        <label>Port<input name="port" type="number" value="${p.port}" required></label>
        <label class="span-2">Username<input name="username" value="${esc(p.username)}" class="mono"></label>
        <label class="span-2">Password<input name="password" value="${esc(p.password)}" class="mono"></label>
        <label class="inline"><input type="checkbox" name="shared" ${p.shared ? "checked" : ""}> Shared (rotating gateway)</label>
        <label class="inline"><input type="checkbox" name="enabled" ${p.enabled ? "checked" : ""}> Enabled</label>
      </div>
      <p class="error" id="proxy-error"></p>
      <div class="modal-foot"><button type="button" class="btn ghost" id="proxy-cancel">Cancel</button>
        <button class="btn primary" type="submit">Save</button></div>
    </form>`);
  $("#proxy-cancel").onclick = closeModal;
  $("#proxy-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    try {
      await api(`/api/proxies/${p.id}`, { method: "PUT", body: {
        label: f.label.value, scheme: f.scheme.value, host: f.host.value.trim(), port: +f.port.value,
        username: f.username.value, password: f.password.value, shared: f.shared.checked, enabled: f.enabled.checked,
      } });
      closeModal();
      await loadProxies();
    } catch (err) {
      $("#proxy-error").textContent = err.message;
    }
  });
}

// ---------------------------------------------------------------------------
// Photo library (bulk upload: files, folders, ZIP)
// ---------------------------------------------------------------------------

const PHOTO_EXTS = /\.(jpe?g|png|webp|bmp|gif|tiff?|zip)$/i;
state.photoFilter = "all";
state.photoSelected = new Set();
const thumbUrl = (name) => `/api/photos/${encodeURIComponent(name)}/thumb`;

async function loadPhotos() {
  state.photos = await api("/api/photos");
  const names = new Set(state.photos.map((p) => p.name));
  state.photoSelected = new Set([...state.photoSelected].filter((n) => names.has(n)));
  if (state.tab === "photos") renderPhotos();
}

function renderPhotos() {
  const all = state.photos;
  const count = (st) => all.filter((p) => p.status === st).length;
  const avail = count("available"), used = count("used"), reserved = count("reserved");
  $("#photo-stats").innerHTML = [
    kpiTile({ label: "Photos in library", iconName: "image", tone: "accent", value: fmtNum(all.length), foot: "each one goes to a single account" }),
    kpiTile({ label: "Available", iconName: "checkCircle", tone: "ok", value: fmtNum(avail),
      foot: avail ? `enough for ${fmtNum(avail)} more account${avail === 1 ? "" : "s"}` : `<span class="sr-danger">upload more to keep creating accounts</span>` }),
    kpiTile({ label: "Reserved", iconName: "clock", tone: "info", value: fmtNum(reserved), foot: "held by accounts waiting in the queue" }),
    kpiTile({ label: "Used", iconName: "userCheck", tone: "warn", value: fmtNum(used), foot: "kept for the account's history" }),
  ].join("");
  $$("#photo-filter button").forEach((b) => {
    const f = b.dataset.filter;
    b.classList.toggle("active", f === state.photoFilter);
    const n = f === "all" ? all.length : count(f);
    b.querySelector(".seg-count").textContent = n;
  });
  const list = state.photoFilter === "all" ? all : all.filter((p) => p.status === state.photoFilter);
  $("#photo-grid").innerHTML = list.length ? list.map(photoCard).join("")
    : emptyState("image", all.length ? "No photos in this filter" : "Your photo library is empty",
      all.length ? "Choose another filter above." : "Drop photos, a folder or a ZIP file above to get started.");
  updatePhotoSelection();
}

function photoCard(p) {
  const selectable = p.status === "available";
  const owner = p.account
    ? `<a href="#account/${p.account.id}" class="pc-owner">${icon("user")}${esc(p.account.name)} <span class="muted">#${p.account.id}</span></a>`
    : p.status === "reserved" ? `<span class="pc-owner muted">${icon("clock")}waiting in queue</span>` : "";
  return `<div class="photo-card s-${p.status}${state.photoSelected.has(p.name) ? " selected" : ""}" data-name="${esc(p.name)}">
    <div class="pc-img" data-view="${esc(p.name)}">
      <img src="${thumbUrl(p.name)}" loading="lazy" alt="">
      ${selectable ? `<label class="pc-check" title="Select"><input type="checkbox" data-sel="${esc(p.name)}" ${state.photoSelected.has(p.name) ? "checked" : ""}></label>` : ""}
      <span class="pc-status ${p.status}">${p.status}</span>
    </div>
    <div class="pc-body">
      <div class="pc-name" title="${esc(p.original_name || p.name)}">${esc(p.name)}</div>
      <div class="pc-meta">${p.width}×${p.height} · ${fmtNum(Math.round(p.size / 1024))} KB</div>
      <div class="pc-foot">${owner || `<span class="pc-owner muted">${icon("checkCircle")}not used yet</span>`}
        ${selectable ? iconBtn("trash", `data-del="${esc(p.name)}"`, "Delete photo", "danger") : ""}</div>
    </div>
  </div>`;
}

function updatePhotoSelection() {
  const n = state.photoSelected.size;
  $("#photo-selected").textContent = n ? `${n} selected` : "";
  $("#photo-bulk-delete").disabled = !n;
  const availableShown = $$("#photo-grid [data-sel]").length;
  $("#photo-select-all").disabled = !availableShown;
}

$("#photo-filter").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (!b) return;
  state.photoFilter = b.dataset.filter;
  renderPhotos();
});

$("#photo-grid").addEventListener("change", (e) => {
  const t = e.target.closest("[data-sel]");
  if (!t) return;
  t.checked ? state.photoSelected.add(t.dataset.sel) : state.photoSelected.delete(t.dataset.sel);
  t.closest(".photo-card").classList.toggle("selected", t.checked);
  updatePhotoSelection();
});

$("#photo-grid").addEventListener("click", guard(async (e) => {
  if (e.target.closest(".pc-check") || e.target.closest("a")) return;
  const del = e.target.closest("[data-del]");
  if (del) {
    if (!confirm(`Delete ${del.dataset.del}?`)) return;
    await api(`/api/photos/${encodeURIComponent(del.dataset.del)}`, { method: "DELETE" });
    state.photoSelected.delete(del.dataset.del);
    toast("Photo deleted");
    return loadPhotos();
  }
  const view = e.target.closest("[data-view]");
  if (view) openPhotoViewer(view.dataset.view);
}));

$("#photo-select-all").onclick = () => {
  const boxes = $$("#photo-grid [data-sel]");
  const allOn = boxes.every((b) => b.checked);
  boxes.forEach((b) => {
    b.checked = !allOn;
    allOn ? state.photoSelected.delete(b.dataset.sel) : state.photoSelected.add(b.dataset.sel);
    b.closest(".photo-card").classList.toggle("selected", !allOn);
  });
  updatePhotoSelection();
};

$("#photo-bulk-delete").onclick = guard(async () => {
  const names = [...state.photoSelected];
  if (!names.length || !confirm(`Delete ${names.length} photo(s)? This cannot be undone.`)) return;
  const res = await api("/api/photos/bulk-delete", { method: "POST", body: { names } });
  state.photoSelected.clear();
  toast(`Deleted ${res.deleted.length} photo(s)${res.blocked.length ? ` · ${res.blocked.length} kept (in use)` : ""}`);
  await loadPhotos();
});

function openPhotoViewer(name) {
  const p = state.photos.find((x) => x.name === name);
  if (!p) return;
  openModal(p.name, `<div class="viewer">
      <img src="/api/photos/${encodeURIComponent(p.name)}/file" alt="">
      <dl class="kv">
        <dt>Status</dt><dd>${badge(p.status)}</dd>
        <dt>Size</dt><dd>${p.width}×${p.height} · ${fmtNum(Math.round(p.size / 1024))} KB</dd>
        <dt>Uploaded</dt><dd>${fmtDate(p.created_at)}</dd>
        <dt>Original</dt><dd>${esc(p.original_name)}</dd>
        <dt>Account</dt><dd>${p.account ? `<a href="#account/${p.account.id}" data-close>${esc(p.account.name)} #${p.account.id}</a> ${badge(p.account.status)}` : "—"}</dd>
      </dl></div>`);
  $("#modal-body [data-close]")?.addEventListener("click", closeModal);
}

// --- Upload ------------------------------------------------------------------

function readEntry(entry) {
  return new Promise((resolve) => {
    if (entry.isFile) return entry.file((f) => resolve([f]), () => resolve([]));
    if (!entry.isDirectory) return resolve([]);
    const reader = entry.createReader(), out = [];
    const next = () => reader.readEntries(async (batch) => {
      if (!batch.length) return resolve(out);
      for (const e of batch) out.push(...await readEntry(e));
      next();
    }, () => resolve(out));
    next();
  });
}

async function filesFromDrop(dt) {
  const entries = [...(dt.items || [])].map((i) => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
  if (!entries.length) return [...dt.files];
  const nested = await Promise.all(entries.map(readEntry));
  return nested.flat();
}

function batchFiles(files) {
  // ZIPs go alone; images are grouped (≤ 12 files / ≤ 25 MB per request).
  const batches = [];
  let cur = [], size = 0;
  for (const f of files) {
    if (/\.zip$/i.test(f.name)) { batches.push([f]); continue; }
    if (cur.length && (cur.length >= 12 || size + f.size > 25 * 1024 * 1024)) { batches.push(cur); cur = []; size = 0; }
    cur.push(f); size += f.size;
  }
  if (cur.length) batches.push(cur);
  return batches;
}

function postWithProgress(files, onProgress) {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.webkitRelativePath || f.name));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/photos");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded);
    xhr.onload = () => {
      if (xhr.status === 401) { showLogin(); return reject(new Error("Not authenticated")); }
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      xhr.status < 400 ? resolve(data) : reject(new Error(data.detail || `Upload failed (HTTP ${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(fd);
  });
}

let uploading = false;
async function uploadPhotos(fileList) {
  const files = [...fileList].filter((f) => PHOTO_EXTS.test(f.name));
  const skipped = fileList.length - files.length;
  if (!files.length) return toast("No images or ZIP files found in that selection", true);
  if (uploading) return toast("An upload is already running — wait for it to finish", true);
  uploading = true;
  const panel = $("#upload-panel");
  panel.classList.remove("hidden");
  const totalBytes = files.reduce((a, f) => a + f.size, 0) || 1;
  const totals = { saved: 0, duplicate: 0, error: 0 };
  const problems = [];
  let doneBytes = 0;
  const render = (phase, pctDone) => {
    panel.innerHTML = `<div class="up-head">
        <div class="icon-bubble accent">${icon("upload")}</div>
        <div class="up-text"><b>${esc(phase)}</b>
          <span>${fmtNum(files.length)} file${files.length === 1 ? "" : "s"} · ${(totalBytes / 1048576).toFixed(1)} MB${skipped ? ` · ${skipped} non-image file(s) ignored` : ""}</span></div>
        <div class="up-counts"><span class="sr-ok">${icon("checkCircle")}${totals.saved} added</span>
          <span class="muted">${icon("copy")}${totals.duplicate} duplicates</span>
          <span class="sr-danger">${icon("alert")}${totals.error} failed</span></div>
      </div>
      <div class="meter up-bar"><span style="width:${pctDone}%"></span></div>
      ${problems.length ? `<details class="up-problems"${totals.error ? " open" : ""}><summary>${problems.length} file(s) not added</summary>
        <ul>${problems.map((r) => `<li><span class="badge ${r.status === "duplicate" ? "" : "bad"}">${r.status}</span>
          <span class="mono">${esc(r.name)}</span> <span class="muted">— ${esc(r.detail)}</span></li>`).join("")}</ul></details>` : ""}`;
  };
  try {
    const batches = batchFiles(files);
    for (let i = 0; i < batches.length; i++) {
      const b = batches[i];
      const bBytes = b.reduce((a, f) => a + f.size, 0);
      const label = b.length === 1 && /\.zip$/i.test(b[0].name) ? `Unpacking ${b[0].name}…` : `Uploading batch ${i + 1} of ${batches.length}…`;
      render(label, Math.round((doneBytes / totalBytes) * 100));
      const res = await postWithProgress(b, (loaded) => render(label, Math.min(99, Math.round(((doneBytes + loaded) / totalBytes) * 100))));
      doneBytes += bBytes;
      for (const k of Object.keys(totals)) totals[k] += res[k] || 0;
      problems.push(...(res.results || []).filter((r) => r.status !== "saved"));
      render(label, Math.round((doneBytes / totalBytes) * 100));
    }
    render(`Done — ${totals.saved} photo${totals.saved === 1 ? "" : "s"} added`, 100);
    toast(`${totals.saved} added · ${totals.duplicate} duplicates skipped · ${totals.error} failed`, totals.saved === 0 && totals.error > 0);
  } catch (e) {
    render(`Upload stopped: ${e.message}`, Math.round((doneBytes / totalBytes) * 100));
    toast(e.message, true);
  } finally {
    uploading = false;
    await guard(loadPhotos)();
  }
}

const dz = $("#dropzone");
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); if (ev === "dragleave" && dz.contains(e.relatedTarget)) return; dz.classList.remove("over"); }));
dz.addEventListener("drop", async (e) => uploadPhotos(await filesFromDrop(e.dataTransfer)));
// Stop the browser from opening files dropped outside the zone.
["dragover", "drop"].forEach((ev) => window.addEventListener(ev, (e) => { if (!dz.contains(e.target)) e.preventDefault(); }));

for (const [btn, input] of [["#dz-files", "#photo-files"], ["#dz-folder", "#photo-folder"], ["#dz-zip", "#photo-zip"], ["#photo-pick-files", "#photo-files"]]) {
  $(btn).onclick = () => $(input).click();
}
for (const id of ["#photo-files", "#photo-folder", "#photo-zip"]) {
  $(id).addEventListener("change", (e) => { const fl = [...e.target.files]; e.target.value = ""; uploadPhotos(fl); });
}

// ---------------------------------------------------------------------------
// Jaumo Accounts (main overview — live)
// ---------------------------------------------------------------------------

const ACC_STATUSES = ["active", "blocked", "photo_failed", "failed", "stopped", "signing_up", "legacy"];
const SORTS = {
  newest: ["id", "desc"], activity: ["last_activity_at", "desc"], likes: ["liked_count", "desc"],
  matches: ["matches_count", "desc"], oldest: ["id", "asc"],
};
const STATE_STYLE = {
  active: { cls: "ok", icon: "checkCircle" }, working: { cls: "working", icon: "refresh" },
  blocked: { cls: "bad", icon: "ban" }, error: { cls: "warn", icon: "alert" }, stopped: { cls: "", icon: "pause" },
};
state.acc = { page: 0, per: +prefs.get("accPer", "12") || 12, q: "", state: "", worker: "", location: "",
  from: "", to: "", sort: "newest", total: 0, items: [], summary: null };
const workerName = (n) => (n ? `Worker-${String(n).padStart(2, "0")}` : "—");

function accQuery() {
  const a = state.acc;
  const qs = new URLSearchParams({ limit: a.per, offset: a.page * a.per, sort: SORTS[a.sort][0], order: SORTS[a.sort][1] });
  if (a.q) qs.set("q", a.q);
  if (a.state) qs.set("state", a.state);
  if (a.worker) qs.set("worker", a.worker);
  if (a.location) qs.set("location", a.location);
  if (a.from) qs.set("date_from", a.from);
  if (a.to) qs.set("date_to", a.to);
  return qs;
}

async function loadAccounts() {
  const [res, sum] = await Promise.all([
    api("/api/accounts?" + accQuery()),
    api(`/api/accounts/summary?tz_offset=${new Date().getTimezoneOffset()}`),
  ]);
  state.acc.total = res.total;
  state.acc.items = res.items;
  state.acc.summary = sum;
  $("#nav-accounts").textContent = sum.accounts || "";
  if (state.tab !== "accounts") return;
  renderAccSummary();
  renderAccWorkers();
  renderAccTable();
}

async function loadLocations() {
  const locs = await api("/api/accounts/locations");
  $("#flt-location").innerHTML = `<option value="">${esc(t("filter.all"))}</option>` +
    locs.map((l) => `<option ${l === state.acc.location ? "selected" : ""}>${esc(l)}</option>`).join("");
}

function renderAccSummary() {
  const s = state.acc.summary;
  const card = (tone, iconName, label, value, today, tip) => `<div class="acc-kpi ${tone}" ${tip ? `title="${esc(tip)}"` : ""}>
      <div class="acc-kpi-ic">${icon(iconName)}</div>
      <div><div class="acc-kpi-label">${esc(label)}</div><div class="acc-kpi-value">${value}</div>
        <div class="acc-kpi-delta">${today}</div></div></div>`;
  const plus = (n) => (n ? `<span class="up">${esc(t("kpi.today", { n: fmtNum(n) }))}</span>` : `<span>${esc(t("kpi.today", { n: 0 }))}</span>`);
  const synced = s.stats_synced_accounts;
  const syncedFoot = synced ? `<span>${esc(t("sync.at", { t: relTime(s.stats_last_synced_at) }))}</span>` : `<span>${esc(t("sync.never"))}</span>`;
  $("#acc-summary").innerHTML = [
    card("teal", "users", t("kpi.total"), fmtNum(s.accounts), plus(s.accounts_today)),
    card("green", "heart", t("st.likesIn"), synced ? fmtNum(s.likes_received) : "–", syncedFoot, t("st.likesInTip")),
    card("violet", "thumbsUp", t("kpi.matches"), fmtNum(s.matches), plus(s.matches_today), t("st.matchesTip")),
    card("blue", "message", t("st.messagesIn"), synced ? fmtNum(s.messages_received) : "–", syncedFoot, t("st.messagesInTip")),
    card("indigo", "zap", t("kpi.actions"), fmtNum(s.actions), plus(s.actions_today), t("st.actionsTip")),
  ].join("");
}

function renderAccWorkers() {
  const sel = $("#flt-worker");
  const workers = state.acc.summary.workers || [];
  sel.innerHTML = `<option value="">${esc(t("acc.allWorkers"))}</option>` +
    workers.map((w) => `<option value="${w}" ${String(w) === String(state.acc.worker) ? "selected" : ""}>${workerName(w)}</option>`).join("");
}

function statTile(kind, iconName, value, label, tip, muted) {
  return `<div class="stat-tile ${kind}${muted ? " muted" : ""}" title="${esc(tip || label)}">
    <span class="stat-ic">${icon(iconName)}</span><span class="stat-txt"><b>${value}</b><small>${esc(label)}</small></span></div>`;
}

function receivedTile(kind, iconName, value, labelKey, tipKey) {
  const none = value === null || value === undefined;
  return statTile(kind, iconName, none ? "–" : fmtNum(value), t(labelKey),
    none ? `${t(tipKey)} — ${t("sync.never")}` : t(tipKey), none);
}

function stateBadge(st) {
  const s = STATE_STYLE[st] || STATE_STYLE.stopped;
  return `<span class="state-badge ${s.cls}">${icon(s.icon)}${esc(t("state." + st)).toUpperCase()}</span>`;
}

function accRow(a) {
  const nd = (v) => (v === null || v === undefined ? "–" : fmtNum(v));
  return `<tr data-acc="${a.id}" class="${a.working ? "is-working" : ""}">
    <td class="cb"><input type="checkbox" data-sel="${a.id}" ${state.accSelected.has(a.id) ? "checked" : ""}></td>
    <td><div class="acc-id">
      ${a.photo ? `<img src="${thumbUrl(a.photo)}" alt="" loading="lazy">` : `<span class="acc-avatar">${esc((a.name || "?").charAt(0))}</span>`}
      <div><div class="acc-name">${esc(a.name)}</div>
        <div class="acc-meta">ID: ${a.id}${a.jaumo_id ? ` · Jaumo ${esc(a.jaumo_id)}` : ""}</div>
        <div class="acc-meta">${esc(t("acc.created", { d: shortDate(a.created_at) }))}${a.location ? ` · ${esc(a.location)}` : ""}</div></div>
    </div></td>
    <td><div class="stat-tiles">
      ${receivedTile("likes", "heart", a.likes_received, "st.likesIn", "st.likesInTip")}
      ${receivedTile("visits", "eye", a.profile_visits, "st.visitsIn", "st.visitsInTip")}
      ${receivedTile("messages", "users", a.messages_received, "st.messagesIn", "st.messagesInTip")}
      ${statTile("matches", "thumbsUp", fmtNum(a.matches_count), t("st.matches"), t("st.matchesTip"))}
      ${statTile("likes-out", "thumbsUp", fmtNum(a.liked_count), t("st.likesOut"), t("st.likesOutTip"))}
      ${statTile("dislikes", "thumbsDown", fmtNum(a.disliked_count), t("st.dislikes"), t("st.dislikesTip"))}
      ${statTile("messages-out", "send", fmtNum(a.messages_sent), t("st.messagesOut"), t("st.messagesOutTip"))}
      ${statTile("actions", "zap", fmtNum(a.actions), t("st.actions"), t("st.actionsTip"))}
    </div></td>
    <td>${stateBadge(a.state)}</td>
    <td><div class="worker-cell"><span class="worker-ic">${icon("cpu")}</span>
      <div><div class="w-name">${workerName(a.worker)}</div><div class="acc-meta">Jaumo</div></div></div></td>
    <td><div class="last-cell" title="${esc(fmtDate(a.last_activity_at))}">${icon("clock")}
      <div><div class="w-name" data-rel="${esc(a.last_activity_at || "")}">${esc(relTime(a.last_activity_at))}</div>
        <div class="acc-meta">${esc(t("acc.lastLabel"))}</div></div></div></td>
    <td class="row-actions">
      ${iconBtn("eye", `data-view="${a.id}"`, t("acc.view"))}
      ${iconBtn("pencil", `data-edit="${a.id}"`, t("acc.edit"))}
      ${iconBtn("more", `data-more="${a.id}"`, t("acc.more"))}
    </td>
  </tr>`;
}

function renderAccTable() {
  const a = state.acc;
  $("#acc-tbody").innerHTML = a.items.length ? a.items.map(accRow).join("")
    : `<tr><td colspan="7">${emptyState("users", t("acc.empty"), t("acc.emptySub"))}</td></tr>`;
  const from = a.total ? a.page * a.per + 1 : 0, to = Math.min(a.total, (a.page + 1) * a.per);
  $("#acc-showing").textContent = t("pager.showing", { a: from, b: to, n: fmtNum(a.total) });
  const pages = Math.max(1, Math.ceil(a.total / a.per));
  const nums = [];
  for (let i = 0; i < pages; i++) {
    if (i === 0 || i === pages - 1 || Math.abs(i - a.page) <= 2) nums.push(i);
    else if (nums[nums.length - 1] !== "…") nums.push("…");
  }
  $("#acc-pages").innerHTML = `<button class="pg" data-pg="${a.page - 1}" ${a.page <= 0 ? "disabled" : ""} aria-label="Previous">${icon("chevronLeft")}</button>
    ${nums.map((n) => n === "…" ? `<span class="pg-gap">…</span>`
      : `<button class="pg${n === a.page ? " active" : ""}" data-pg="${n}">${n + 1}</button>`).join("")}
    <button class="pg" data-pg="${a.page + 1}" ${a.page + 1 >= pages ? "disabled" : ""} aria-label="Next">${icon("chevronRight")}</button>`;
  $("#acc-per").innerHTML = [12, 25, 50, 100].map((n) =>
    `<option value="${n}" ${n === a.per ? "selected" : ""}>${esc(t("pager.per", { n }))}</option>`).join("");
  const all = $("#acc-all");
  all.checked = a.items.length > 0 && a.items.every((x) => state.accSelected.has(x.id));
  updateAccSelected();
}

function updateAccSelected() {
  const n = state.accSelected.size;
  $("#acc-bulk").classList.toggle("hidden", !n);
  $("#acc-bulk-count").textContent = t("bulk.selected", { n });
}

const reloadAccountsSoon = throttle(() => { if (state.tab === "accounts") guard(loadAccounts)(); }, 3000);
setInterval(() => {
  if (state.tab !== "accounts" || document.hidden) return;
  $$("#acc-tbody [data-rel]").forEach((el) => { if (el.dataset.rel) el.textContent = relTime(el.dataset.rel); });
}, 30000);

// --- toolbar ------------------------------------------------------------------

$("#acc-search").addEventListener("input", debounce((e) => {
  state.acc.q = e.target.value.trim(); state.acc.page = 0; guard(loadAccounts)();
}, 300));
$("#flt-state").addEventListener("change", (e) => { state.acc.state = e.target.value; state.acc.page = 0; guard(loadAccounts)(); });
$("#flt-worker").addEventListener("change", (e) => { state.acc.worker = e.target.value; state.acc.page = 0; guard(loadAccounts)(); });
$("#acc-per").addEventListener("change", (e) => {
  state.acc.per = +e.target.value; state.acc.page = 0; prefs.set("accPer", String(state.acc.per)); guard(loadAccounts)();
});
$("#acc-pages").addEventListener("click", (e) => {
  const b = e.target.closest("[data-pg]");
  if (!b || b.disabled) return;
  state.acc.page = +b.dataset.pg; guard(loadAccounts)();
  $("#tab-accounts").scrollIntoView({ behavior: "smooth" });
});

$("#flt-toggle").onclick = (e) => { e.stopPropagation(); $("#flt-panel").classList.toggle("hidden"); };
document.addEventListener("click", (e) => {
  if (!e.target.closest("#flt-panel") && !e.target.closest("#flt-toggle")) $("#flt-panel").classList.add("hidden");
  if (!e.target.closest(".menu") && !e.target.closest("[data-more]")) $$(".menu").forEach((m) => m.remove());
});
$("#flt-apply").onclick = () => {
  Object.assign(state.acc, {
    location: $("#flt-location").value, from: $("#flt-from").value, to: $("#flt-to").value,
    sort: $("#flt-sort").value, page: 0,
  });
  const active = [state.acc.location, state.acc.from, state.acc.to].filter(Boolean).length + (state.acc.sort !== "newest");
  $("#flt-count").textContent = active || "";
  $("#flt-panel").classList.add("hidden");
  guard(loadAccounts)();
};
$("#flt-reset").onclick = () => {
  $("#flt-location").value = ""; $("#flt-from").value = ""; $("#flt-to").value = ""; $("#flt-sort").value = "newest";
  $("#flt-apply").click();
};

// --- table interactions -------------------------------------------------------

$("#acc-table").addEventListener("change", (e) => {
  const tgt = e.target;
  if (tgt.id === "acc-all") {
    state.acc.items.forEach((x) => (tgt.checked ? state.accSelected.add(x.id) : state.accSelected.delete(x.id)));
    $$("#acc-tbody [data-sel]").forEach((c) => (c.checked = tgt.checked));
  } else if (tgt.dataset.sel) {
    tgt.checked ? state.accSelected.add(+tgt.dataset.sel) : state.accSelected.delete(+tgt.dataset.sel);
  }
  updateAccSelected();
});

$("#acc-table").addEventListener("click", guard(async (e) => {
  if (e.target.closest("input")) return;
  const view = e.target.closest("[data-view]"), edit = e.target.closest("[data-edit]"), more = e.target.closest("[data-more]");
  if (edit) return openAccountEdit(+edit.dataset.edit);
  if (more) return openAccountMenu(more, +more.dataset.more);
  const row = e.target.closest("[data-acc]");
  if (view || (row && !e.target.closest(".row-actions"))) location.hash = `#account/${(view || row).dataset.view || row.dataset.acc}`;
}));

function openAccountMenu(btn, id) {
  $$(".menu").forEach((m) => m.remove());
  const a = state.acc.items.find((x) => x.id === id);
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.innerHTML = `
    <button data-act="message" ${a.pending_messages ? "" : "disabled"}>${icon("send")}${esc(t("acc.menuMessage"))}${a.pending_messages ? ` <span class="seg-count">${a.pending_messages}</span>` : ""}</button>
    <button data-act="log" ${a.run_id ? "" : "disabled"}>${icon("terminal")}${esc(t("acc.menuLog"))}</button>
    <button data-act="copy" ${a.jaumo_id ? "" : "disabled"}>${icon("copy")}${esc(t("acc.menuCopy"))}</button>
    <hr><button data-act="delete" class="danger" ${a.working ? "disabled" : ""}>${icon("trash")}${esc(t("acc.menuDelete"))}</button>`;
  document.body.appendChild(menu);
  const r = btn.getBoundingClientRect();
  menu.style.top = `${Math.min(window.innerHeight - menu.offsetHeight - 8, r.bottom + 6)}px`;
  menu.style.left = `${Math.max(8, r.right - menu.offsetWidth)}px`;
  menu.onclick = guard(async (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (!act) return;
    menu.remove();
    if (act === "message") return openMessageDialog([id]);
    if (act === "log") return openRunModal(a.run_id);
    if (act === "copy") { await navigator.clipboard.writeText(a.jaumo_id); return toast(t("acc.copied")); }
    if (act === "delete") {
      if (!confirm(t("del.confirm", { name: a.name, id }))) return;
      await api(`/api/accounts/${id}`, { method: "DELETE" });
      state.accSelected.delete(id);
      await loadAccounts();
    }
  });
}

function openAccountEdit(id) {
  const a = state.acc.items.find((x) => x.id === id);
  openModal(`${t("edit.title")} — ${a.name}`, `<form id="acc-edit-form" class="narrow-form">
      <label>${esc(t("edit.status"))}<select name="status">${ACC_STATUSES.map((s) =>
        `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></label>
      <label>${esc(t("edit.notes"))}<textarea name="notes" rows="4">${esc(a.notes || "")}</textarea></label>
      <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
        <button class="btn primary">${icon("check")}${esc(t("edit.save"))}</button></div></form>`);
  $("#acc-edit-form").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    await api(`/api/accounts/${id}`, { method: "PATCH", body: { status: f.status.value, notes: f.notes.value } });
    closeModal();
    toast(t("edit.saved"));
    await loadAccounts();
  }));
}

function openMessageDialog(ids) {
  const usable = state.configs.filter((c) => c.settings.messaging_enabled);
  if (!usable.length) {
    openModal(t("msg.title"), `<div class="narrow-form">
        <p>${esc(t("msg.noneEnabled"))}</p>
        <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
          <a class="btn primary" href="#configs" data-close-modal>${icon("sliders")}${esc(t("nav.configs"))}</a></div></div>`);
    return;
  }
  const opts = usable.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  openModal(t("msg.title"), `<form id="msg-form" class="narrow-form">
      <p class="muted">${ids.length ? esc(t("bulk.selected", { n: ids.length })) : ""}</p>
      <label>${esc(t("msg.config"))}<select name="config">${opts}</select></label>
      <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
        <button class="btn primary">${icon("send")}${esc(t("msg.start"))}</button></div></form>`);
  $("#msg-form").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const res = await api("/api/messages", { method: "POST", body: { config_id: +e.target.elements.config.value, account_ids: ids } });
    closeModal();
    toast(res.run_ids.length ? `${res.run_ids.length} ✓` : "No eligible accounts (need pending matches and a login token)", !res.run_ids.length);
  }));
}

$("#bulk-message").onclick = () => openMessageDialog([...state.accSelected]);
$("#bulk-export").onclick = () => { window.location = "/api/accounts/export?" + accQuery(); };
$("#bulk-clear").onclick = () => { state.accSelected.clear(); renderAccTable(); };

async function openSyncDialog() {
  const settings = await api("/api/settings");
  const delay = settings.bot.sync_delay_seconds;
  const total = (state.acc.summary && state.acc.summary.accounts) || 0;
  const sel = state.accSelected.size;
  openModal(t("sync.title"), `<form id="sync-form" class="narrow-form">
      <p class="muted">${esc(t("sync.text"))}</p>
      <div class="choice-cards">
        <label class="choice"><input type="radio" name="scope" value="selected" ${sel ? "checked" : "disabled"}>
          <div><b>${esc(t("sync.selected", { n: sel }))}</b></div></label>
        <label class="choice"><input type="radio" name="scope" value="all" ${sel ? "" : "checked"}>
          <div><b>${esc(t("sync.all", { n: total }))}</b></div></label>
      </div>
      <p class="field-hint" id="sync-cost"></p>
      <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
        <button class="btn primary">${icon("refresh")}${esc(t("sync.start"))}</button></div></form>`);
  const form = $("#sync-form");
  const cost = () => {
    const n = form.elements.scope.value === "all" ? total : sel;
    $("#sync-cost").textContent = t("sync.cost", { n, r: n * 3, d: delay });
  };
  cost();
  form.addEventListener("change", cost);
  form.addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const all = form.elements.scope.value === "all";
    const res = await api("/api/accounts/sync", { method: "POST", body: all ? { all: true } : { account_ids: [...state.accSelected] } });
    closeModal();
    toast(t("sync.started", { n: res.run_ids.length }));
    if (res.skipped.length) {
      const why = [...new Set(res.skipped.map((x) => x.reason))].join("; ");
      toast(t("sync.skipped", { n: res.skipped.length, why }), true);
    }
  }));
}
$("#acc-sync").onclick = guard(openSyncDialog);
$("#bulk-sync").onclick = guard(openSyncDialog);

// --- New accounts (one by one or parallel workers) -----------------------------

async function openNewAccounts() {
  const [settings, stats] = await Promise.all([api("/api/settings"), api("/api/stats")]);
  const par = settings.bot.parallel_accounts;
  const opts = state.configs.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  openModal(t("new.title"), `<form id="new-acc-form" class="narrow-form">
      <p class="muted">${esc(stats.running || stats.queued ? t("new.busy", { w: stats.running, q: stats.queued }) : t("new.idle"))}</p>
      <label>${esc(t("new.config"))}<select name="config_id" required>${opts}</select></label>
      <div id="new-config-info" class="config-info"></div>
      <label>${esc(t("new.count"))}
        <div class="stepper"><button type="button" data-step="-1">−</button>
          <input name="count" type="number" min="1" max="500" value="1" required>
          <button type="button" data-step="1">+</button></div></label>
      <div><div class="lbl">${esc(t("new.mode"))}</div>
        <div class="choice-cards">
          <label class="choice"><input type="radio" name="mode" value="seq" ${par === 1 ? "checked" : ""}>
            <div><b>${esc(t("new.sequential"))}</b><span>${esc(t("new.sequentialSub"))}</span></div></label>
          <label class="choice"><input type="radio" name="mode" value="par" ${par > 1 ? "checked" : ""}>
            <div><b>${esc(t("new.parallel"))}</b><span>${esc(t("new.parallelSub"))}</span></div></label>
        </div>
        <label id="par-box" class="${par > 1 ? "" : "hidden"}">${esc(t("new.workers"))}
          <div class="stepper sm"><button type="button" data-wstep="-1">−</button>
            <input name="workers" type="number" min="2" max="20" value="${Math.max(2, par)}">
            <button type="button" data-wstep="1">+</button></div></label>
      </div>
      <details class="names-details"><summary>${esc(t("new.names"))}</summary><textarea name="names" rows="3"></textarea></details>
      <div id="new-problems" class="new-problems hidden" role="alert"></div>
      <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
        <button id="new-submit" class="btn primary">${icon("plus")}${esc(t("new.submit"))}</button></div></form>`);
  const form = $("#new-acc-form");
  const showInfo = () => {
    const prev = $("#launch-config").value;
    $("#launch-config").value = form.elements.config_id.value;
    renderLaunchInfo();
    $("#new-config-info").innerHTML = $("#launch-config-info").innerHTML;
    $("#launch-config").value = prev;
  };
  // Ask the server whether this start would be refused, so the reason is shown here instead of a toast.
  let checkSeq = 0;
  const check = async () => {
    const seq = ++checkSeq, f = form.elements;
    if (!f.config_id.value) return;
    let res;
    try {
      res = await api("/api/runs/check", { method: "POST",
        body: { config_id: +f.config_id.value, count: Math.min(500, Math.max(1, +f.count.value || 1)), names: lines(f.names.value) } });
    } catch { return; }
    if (seq !== checkSeq || !$("#new-problems")) return;
    const box = $("#new-problems");
    box.classList.toggle("hidden", res.ok);
    $("#new-submit").disabled = !res.ok;
    box.innerHTML = res.ok ? "" : `<b>${icon("alert")}${esc(t("new.blocked"))}</b><ul>${res.problems.map((p) =>
      `<li><span>${esc(t("new.p." + p.code))} <small>${esc(p.message)}</small></span>
        <a href="#${p.page}" data-close-modal class="btn ghost sm">${esc(t("new.fix"))}</a></li>`).join("")}</ul>`;
  };
  const checkSoon = throttle(check, 400);
  showInfo();
  check();
  form.elements.config_id.onchange = () => { showInfo(); check(); };
  form.addEventListener("input", (e) => { if (e.target.name === "count" || e.target.name === "names") checkSoon(); });
  form.addEventListener("change", (e) => { if (e.target.name === "mode") $("#par-box").classList.toggle("hidden", e.target.value !== "par"); });
  form.addEventListener("click", (e) => {
    const s = e.target.closest("[data-step]"), w = e.target.closest("[data-wstep]");
    if (s) { form.elements.count.value = Math.min(500, Math.max(1, (+form.elements.count.value || 1) + +s.dataset.step)); checkSoon(); }
    if (w) form.elements.workers.value = Math.min(20, Math.max(2, (+form.elements.workers.value || 2) + +w.dataset.wstep));
  });
  form.addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const f = form.elements;
    const workers = f.mode.value === "par" ? Math.min(20, Math.max(2, +f.workers.value || 2)) : 1;
    if (workers !== par) await api("/api/settings", { method: "PUT", body: { bot: { parallel_accounts: workers } } });
    const res = await api("/api/runs", { method: "POST", body: { config_id: +f.config_id.value, count: +f.count.value, names: lines(f.names.value) } });
    closeModal();
    toast(t("new.queued", { n: res.run_ids.length }));
    guard(loadStats)();
    guard(loadPhotos)();
    reloadAccountsSoon();
  }));
}
$("#acc-new").onclick = guard(openNewAccounts);

// ---------------------------------------------------------------------------
// Account detail page (live)
// ---------------------------------------------------------------------------

const EVENT_STYLE = {
  created: { icon: "userPlus", tone: "accent", text: () => "Account created" },
  status: { icon: "activity", tone: "info", text: () => "Status changed" },
  like: { icon: "thumbsUp", tone: "info", text: (e) => `Liked user ${e.user_id}` },
  match: { icon: "heart", tone: "danger", text: (e) => `Liked user ${e.user_id} — it's a match!` },
  dislike: { icon: "thumbsDown", tone: "neutral", text: (e) => `Disliked user ${e.user_id}` },
  message: { icon: "message", tone: "ok", text: (e) => `Messaged user ${e.user_id}` },
  message_failed: { icon: "alert", tone: "danger", text: (e) => `Message to ${e.user_id} failed` },
};

const acct = { id: null, data: null, runs: [], events: [], ws: null, logWs: null, logRunId: null, listTab: "matches" };

function ageFrom(birthday) {
  if (!birthday) return null;
  const b = new Date(birthday + "T00:00:00"), n = new Date();
  let age = n.getFullYear() - b.getFullYear();
  if (n < new Date(n.getFullYear(), b.getMonth(), b.getDate())) age--;
  return age;
}

function closeAccountStreams() {
  if (acct.ws) { const w = acct.ws; acct.ws = null; w.close(); }
  if (acct.logWs) { const w = acct.logWs; acct.logWs = null; w.close(); }
  acct.logRunId = null;
}

async function openAccountPage(id) {
  closeAccountStreams();
  acct.id = id;
  acct.events = [];
  $("#account-page").innerHTML = `<div class="empty">${icon("clock")}<b>Loading account…</b></div>`;
  // Subscribe first, then load: events that happen while the page loads are buffered, not lost.
  const early = [];
  let loaded = false;
  const ws = new WebSocket(wsUrl(`/ws/accounts/${id}`));
  acct.ws = ws;
  const addEvent = (ev) => {
    if (acct.events.some((x) => x.id === ev.id)) return;
    acct.events.unshift(ev);
    prependTimeline(ev);
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (acct.id !== id) return;
    if (msg.type === "activity") {
      if (!loaded) { early.push(msg.event); return; }
      addEvent(msg.event);
      refreshAccountSoon();
    } else if (msg.type === "changed" && loaded) {
      refreshAccountSoon();
    }
  };
  await new Promise((res) => { ws.addEventListener("open", res, { once: true }); ws.addEventListener("error", res, { once: true }); setTimeout(res, 3000); });
  if (acct.id !== id) return;
  const [data, runs, events] = await Promise.all([
    api(`/api/accounts/${id}`), api(`/api/accounts/${id}/runs`), api(`/api/accounts/${id}/events?limit=200`),
  ]);
  if (acct.id !== id) return;
  acct.data = data; acct.runs = runs; acct.events = events;
  renderAccountPage();
  loaded = true;
  early.sort((a, b) => a.id - b.id).forEach(addEvent);
  if (early.length) refreshAccountSoon();
}

const refreshAccountSoon = throttle(guard(async () => {
  if (!acct.id || state.tab !== "account") return;
  const id = acct.id;
  const [data, runs] = await Promise.all([api(`/api/accounts/${id}`), api(`/api/accounts/${id}/runs`)]);
  if (acct.id !== id) return;
  acct.data = data; acct.runs = runs;
  renderAccountSections();
}), 500);

function activeRun() {
  return acct.runs.find((r) => ACTIVE.has(r.status));
}

function renderAccountPage() {
  const a = acct.data;
  $("#account-page").innerHTML = `
    <a href="#accounts" class="back-link">${icon("chevronLeft")}All accounts</a>
    <div id="acc-hero"></div>
    <div id="acc-sync-bar" class="sync-bar"></div>
    <div id="acc-kpis" class="kpi-grid eight"></div>
    <div id="acc-live"></div>
    <div class="grid-12">
      <div class="card span-7">
        <div class="card-head"><div><h2>Activity</h2><p class="card-sub">Every like, match, message and status change — updates live</p></div></div>
        <div id="acc-timeline" class="timeline"></div>
        <div class="timeline-more"><button class="btn small" id="acc-more">Load older activity</button></div>
      </div>
      <div class="span-5 stack">
        <div class="card">
          <div class="card-head"><div><h2>People</h2></div>
            <div class="seg" id="acc-list-tabs">
              <button data-list="matches">Matches <span class="seg-count" id="cnt-matches"></span></button>
              <button data-list="liked">Liked <span class="seg-count" id="cnt-liked"></span></button>
              <button data-list="disliked">Disliked <span class="seg-count" id="cnt-disliked"></span></button>
            </div></div>
          <div id="acc-people"></div>
        </div>
        <div class="card">
          <div class="card-head"><div><h2>Profile &amp; device</h2></div></div>
          <div id="acc-details"></div>
        </div>
      </div>
    </div>
    <div class="card table-card">
      <div class="card-head padded"><div><h2>Sessions</h2><p class="card-sub">Signup and messaging runs for this account</p></div></div>
      <table class="table" id="acc-runs"></table>
    </div>`;
  renderTimeline();
  renderAccountSections();
  $("#acc-more").onclick = guard(async () => {
    const last = acct.events[acct.events.length - 1];
    if (!last) return;
    const older = await api(`/api/accounts/${a.id}/events?before_id=${last.id}&limit=200`);
    acct.events.push(...older);
    $("#acc-timeline").insertAdjacentHTML("beforeend", older.map(timelineItem).join(""));
    if (older.length < 200) $("#acc-more").disabled = true;
  });
  if (acct.events.length < 200) $("#acc-more").disabled = true;
  $("#acc-list-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-list]");
    if (!b) return;
    acct.listTab = b.dataset.list;
    renderPeople();
  });
}

function renderAccountSections() {
  const a = acct.data;
  const run = activeRun();
  const age = ageFrom(a.birthday);
  const dev = a.device_info ? `${a.device_info.manufacturer} ${a.device_info.model}` : "Unknown device";
  const config = state.configs.find((c) => c.id === a.config_id);
  const msgOpts = state.configs.map((c) =>
    `<option value="${c.id}" ${c.id === a.config_id ? "selected" : ""}>${esc(c.name)}${c.settings.messaging_enabled ? "" : " — messaging off"}</option>`).join("");
  $("#acc-hero").innerHTML = `<div class="card acc-hero">
    <div class="acc-photo">${a.photo ? `<img src="${thumbUrl(a.photo)}" alt="" data-full="${esc(a.photo)}">` : icon("user")}</div>
    <div class="acc-main">
      <div class="acc-title"><h1>${esc(a.name)}</h1>${badge(a.status)}
        ${run ? `<span class="live-chip on"><span class="pulse"></span>${esc(workerName(run.worker))} ${esc(t("state.working").toLowerCase())}</span>` : ""}</div>
      <div class="acc-sub">Account #${a.id}${a.jaumo_id ? ` · Jaumo ${esc(a.jaumo_id)}` : ""} · ${esc(workerName(a.worker))}${age !== null ? ` · ${age} years` : ""} · ${esc(a.location || "—")} · joined ${fmtDate(a.created_at)}</div>
      <div class="acc-chips">
        <span class="chip">${icon("smartphone")}${esc(dev)}</span>
        <span class="chip">${icon("sliders")}${esc(config ? config.name : a.config_id ? `config #${a.config_id}` : "legacy import")}</span>
        <span class="chip">${icon("globe")}${a.proxy_id ? `proxy #${a.proxy_id}` : "no proxy"}</span>
        <span class="chip ${a.has_token ? "" : "bad"}">${icon("key")}${a.has_token ? "login token stored" : "no login token"}</span>
      </div>
    </div>
    <div class="acc-actions">
      <label>Message matches with<select id="acc-msg-config">${msgOpts}</select></label>
      <button class="btn primary" id="acc-msg" ${a.pending_messages ? "" : "disabled"}>${icon("send")}Message ${a.pending_messages || ""} pending</button>
    </div>
  </div>`;
  $("#acc-hero [data-full]")?.addEventListener("click", () => openPhotoViewer(a.photo));
  $("#acc-msg").onclick = guard(async () => {
    const res = await api("/api/messages", { method: "POST", body: { config_id: +$("#acc-msg-config").value, account_ids: [a.id] } });
    toast(res.run_ids.length ? "Messaging session queued" : "Nothing to send (no pending matches or a session is already running)", !res.run_ids.length);
    refreshAccountSoon();
  });

  const rate = a.liked_count ? ((a.matches_count / a.liked_count) * 100).toFixed(1) : "0.0";
  const nd = (v) => (v === null || v === undefined ? "–" : fmtNum(v));
  $("#acc-kpis").innerHTML = [
    kpiTile({ label: t("st.likesIn"), iconName: "heart", tone: "danger", value: nd(a.likes_received), foot: t("st.likesInTip") }),
    kpiTile({ label: t("st.visitsIn"), iconName: "eye", tone: "info", value: nd(a.profile_visits), foot: t("st.visitsInTip") }),
    kpiTile({ label: t("st.messagesIn"), iconName: "users", tone: "accent", value: nd(a.messages_received), foot: t("st.messagesInTip") }),
    kpiTile({ label: t("st.matches"), iconName: "thumbsUp", tone: "ok", value: fmtNum(a.matches_count),
      foot: `${t("st.rate", { r: rate })} · ${t("st.pending")}: ${fmtNum(a.pending_messages)}` }),
    kpiTile({ label: t("st.likesOut"), iconName: "thumbsUp", tone: "info", value: fmtNum(a.liked_count), foot: t("st.likesOutTip") }),
    kpiTile({ label: t("st.dislikes"), iconName: "thumbsDown", tone: "", value: fmtNum(a.disliked_count), foot: t("st.dislikesTip") }),
    kpiTile({ label: t("st.messagesOutLong"), iconName: "send", tone: "ok", value: fmtNum(a.messages_sent), foot: t("st.messagesOutTip") }),
    kpiTile({ label: t("st.actions"), iconName: "zap", tone: "accent", value: fmtNum(a.actions), foot: t("st.actionsTip") }),
  ].join("");
  renderSyncBar(a);

  renderLiveSession(run);
  renderPeople();

  const lf = { 1: "Men", 2: "Women" }[a.looking_for_gender] || a.looking_for_gender;
  $("#acc-details").innerHTML = `<dl class="kv">
      <dt>Name</dt><dd>${esc(a.name)}</dd>
      <dt>Birthday</dt><dd>${esc(a.birthday || "—")}${age !== null ? ` (${age})` : ""}</dd>
      <dt>Gender / looking for</dt><dd>Female · ${esc(lf)}</dd>
      <dt>Relationship (signup)</dt><dd>${a.relationship_search ? `${esc(a.relationship_search)} · dating ${esc(a.dating_relationship_search || "—")}` : "—"}</dd>
      <dt>Location</dt><dd>${esc(a.location || "—")}${a.latitude ? ` <span class="muted">(${esc(a.latitude)}, ${esc(a.longitude)})</span>` : ""}</dd>
      <dt>Profile photo</dt><dd>${esc(a.photo || "—")} · ${a.photo_uploaded ? "uploaded" : "not uploaded"} · gallery ${a.gallery_count}</dd>
      <dt>Signup photo_url</dt><dd class="mono">${esc(a.photo_url || "—")}</dd>
      <dt>Device</dt><dd>${esc(dev)}</dd>
      <dt>Android ID</dt><dd class="mono">${esc(a.android_id || "—")}</dd>
      <dt>Last update</dt><dd>${fmtDate(a.updated_at)}</dd>
    </dl>
    <div class="form-grid" style="margin:0">
      <label>Status<select id="acc-status">${ACC_STATUSES.map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></label>
      <label class="span-2">Notes<textarea id="acc-notes" rows="2" placeholder="Anything worth remembering about this account">${esc(a.notes)}</textarea></label>
    </div>
    <div class="actions">
      <button class="btn small primary" id="acc-save">${icon("check")}Save</button>
      <button class="btn small danger" id="acc-delete" ${run ? "disabled title='Stop the running session first'" : ""}>${icon("trash")}Delete account</button>
    </div>`;
  $("#acc-save").onclick = guard(async () => {
    await api(`/api/accounts/${a.id}`, { method: "PATCH", body: { status: $("#acc-status").value, notes: $("#acc-notes").value } });
    toast("Account saved");
    refreshAccountSoon();
  });
  $("#acc-delete").onclick = guard(async () => {
    if (!confirm(`Delete account "${a.name}" (#${a.id}) from the database? Its tokens and history will be lost.`)) return;
    await api(`/api/accounts/${a.id}`, { method: "DELETE" });
    toast("Account deleted");
    location.hash = "#accounts";
  });

  $("#acc-runs").innerHTML = `<thead><tr><th>#</th><th>Type</th><th>Status</th><th>Step</th>
      <th class="num">Liked</th><th class="num">Disliked</th><th class="num">Matches</th><th class="num">Msgs</th>
      <th>Started</th><th>Duration</th><th>Result</th><th></th></tr></thead>
    <tbody>${acct.runs.map((r) => `<tr>
      <td>${r.id}</td><td>${r.kind === "message" ? "Messaging" : r.kind === "sync" ? "Stats refresh" : "Signup + swiping"}</td><td>${badge(r.status)}</td>
      <td>${esc(STEP_LABELS[r.step] || r.step || "—")}</td>
      <td class="num">${r.liked}</td><td class="num">${r.disliked}</td><td class="num">${r.matches}</td><td class="num">${r.messages_sent}</td>
      <td>${fmtDate(r.started_at)}</td><td>${esc(duration(r))}</td><td class="wrapcell" title="${esc(r.reason)}">${esc(r.reason || "—")}</td>
      <td class="actions">${iconBtn("terminal", `data-log="${r.id}"`, "Open log")}</td></tr>`).join("")
      || `<tr><td colspan="12" class="muted">No sessions recorded (legacy account)</td></tr>`}</tbody>`;
  $("#acc-runs").onclick = (e) => { const b = e.target.closest("[data-log]"); if (b) openRunModal(+b.dataset.log); };
}

const SYNC_COOLDOWN_MS = 15000;
let syncTimer = null;
function renderSyncBar(a) {
  clearInterval(syncTimer);
  const bar = $("#acc-sync-bar");
  if (!bar) return;
  const running = acct.runs.some((r) => r.kind === "sync" && ACTIVE.has(r.status));
  const draw = () => {
    const left = a.stats_synced_at ? Math.ceil((new Date(a.stats_synced_at).getTime() + SYNC_COOLDOWN_MS - Date.now()) / 1000) : 0;
    const label = running ? t("sync.running") : left > 0 ? t("sync.wait", { s: left }) : t("sync.refreshOne");
    bar.innerHTML = `<div class="sync-info">${icon("refresh")}
        <span>${esc(a.stats_synced_at ? t("sync.at", { t: relTime(a.stats_synced_at) }) : t("sync.never"))}</span>
        ${a.stats_sync_error ? `<span class="sr-danger">${esc(t("sync.error", { e: a.stats_sync_error }))}</span>` : ""}</div>
      <button class="btn small" id="acc-sync-btn" ${running || left > 0 ? "disabled" : ""}>${icon("refresh")}${esc(label)}</button>`;
    $("#acc-sync-btn").onclick = guard(async () => {
      await api(`/api/accounts/${a.id}/sync`, { method: "POST" });
      toast(t("sync.started", { n: 1 }));
      refreshAccountSoon();
    });
    if (!running && left <= 0) clearInterval(syncTimer);
  };
  draw();
  syncTimer = setInterval(draw, 1000);
}

function renderLiveSession(run) {
  const box = $("#acc-live");
  if (!run) {
    box.innerHTML = "";
    if (acct.logWs) { acct.logWs.close(); acct.logWs = null; acct.logRunId = null; }
    return;
  }
  if (acct.logRunId !== run.id) {
    box.innerHTML = `<div class="card live-card">
      <div class="card-head"><div><h2>${icon("cpu")} ${esc(workerName(run.worker))} is working on this account</h2>
        <p class="card-sub" id="acc-live-sub"></p></div>
        <div class="actions">${iconBtn("terminal", `data-log="${run.id}"`, "Open full log")}
          <button class="btn small danger" id="acc-stop">${icon("stop")}Stop</button></div></div>
      <div id="acc-live-steps"></div>
      <div class="log-view compact" id="acc-live-log"></div>
    </div>`;
    $("#acc-stop").onclick = guard(async () => { await api(`/api/runs/${run.id}/stop`, { method: "POST" }); toast("Stopping…"); });
    box.querySelector("[data-log]").onclick = () => openRunModal(run.id);
    streamRunLog(run.id);
  }
  $("#acc-live-sub").textContent = `Session #${run.id} · ${run.kind === "message" ? "messaging" : "signup + swiping"} · ${duration(run) || "starting"} · proxy ${run.proxy_label || "—"}`;
  $("#acc-live-steps").innerHTML = stepBar(run);
}

async function streamRunLog(runId) {
  if (acct.logWs) acct.logWs.close();
  acct.logRunId = runId;
  let lastId = 0;
  const view = $("#acc-live-log");
  const append = (entries) => {
    const frag = document.createDocumentFragment();
    for (const l of entries) {
      if (l.id <= lastId || l.level === "debug") { lastId = Math.max(lastId, l.id); continue; }
      lastId = l.id;
      const div = document.createElement("div");
      div.className = "l-" + l.level;
      div.innerHTML = `<span class="ts">${esc(fmtTime(l.ts))}</span>${esc(l.msg)}`;
      frag.appendChild(div);
    }
    view.appendChild(frag);
    while (view.childElementCount > 300) view.firstElementChild.remove();
    view.scrollTop = view.scrollHeight;
  };
  const buffer = [];
  let ready = false;
  const ws = new WebSocket(wsUrl(`/ws/runs/${runId}`));
  acct.logWs = ws;
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "log") ready ? append([msg]) : buffer.push(msg);
    else if (msg.type === "run" && acct.logRunId === runId) {
      const i = acct.runs.findIndex((r) => r.id === runId);
      if (i >= 0) acct.runs[i] = msg.run;
      if (!ACTIVE.has(msg.run.status)) refreshAccountSoon();
      else renderLiveSession(msg.run);
    }
  };
  append(await api(`/api/runs/${runId}/logs?levels=info,warning,error&limit=300`));
  ready = true;
  append(buffer);
}

function renderPeople() {
  const a = acct.data;
  const messaged = new Set((a.messaged || []).map(String));
  const lists = { matches: a.matches || [], liked: a.liked || [], disliked: a.disliked || [] };
  for (const k of Object.keys(lists)) $(`#cnt-${k}`).textContent = lists[k].length;
  $$("#acc-list-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.list === acct.listTab));
  const items = [...lists[acct.listTab]].reverse();
  $("#acc-people").innerHTML = items.length ? `<div class="people">${items.map((uid) => {
      const tag = acct.listTab === "matches"
        ? (messaged.has(String(uid)) ? `<span class="badge ok">messaged</span>` : `<span class="badge warn">pending</span>`) : "";
      return `<div class="person">${icon(acct.listTab === "matches" ? "heart" : acct.listTab === "liked" ? "thumbsUp" : "thumbsDown")}
        <span class="mono">${esc(uid)}</span>${tag}</div>`;
    }).join("")}</div>`
    : emptyState(acct.listTab === "matches" ? "heart" : "users", "Nothing here yet",
      acct.listTab === "matches" ? "Matches appear when a liked user likes back." : "No swipes with this account yet.");
}

function timelineItem(e) {
  const st = EVENT_STYLE[e.kind] || { icon: "activity", tone: "neutral", text: () => e.kind };
  return `<div class="tl-item" data-ev="${e.id}">
    <span class="tl-icon icon-bubble ${st.tone}">${icon(st.icon)}</span>
    <div class="tl-body"><div class="tl-text">${esc(st.text(e))}</div>
      ${e.detail ? `<div class="tl-detail">${esc(e.detail)}</div>` : ""}</div>
    <time title="${esc(fmtDate(e.ts))}">${esc(fmtTime(e.ts))}<span>${esc(new Date(e.ts).toLocaleDateString(undefined, { day: "numeric", month: "short" }))}</span></time>
  </div>`;
}

function renderTimeline() {
  $("#acc-timeline").innerHTML = acct.events.length ? acct.events.map(timelineItem).join("")
    : emptyState("activity", "No activity yet", "Likes, matches and messages will show up here as they happen.");
}

function prependTimeline(e) {
  const tl = $("#acc-timeline");
  if (!tl) return;
  if (tl.querySelector(".empty")) tl.innerHTML = "";
  tl.insertAdjacentHTML("afterbegin", timelineItem(e));
  tl.firstElementChild.classList.add("fresh");
}

// ---------------------------------------------------------------------------
// Settings (global rules)
// ---------------------------------------------------------------------------

async function loadSettings() {
  const s = await api("/api/settings");
  state.settings = s;
  const c = s.counts;
  $("#settings-body").innerHTML = `
    <div class="card">
      <div class="card-head"><div><h2>${icon("cpu")} Account creation</h2>
        <p class="card-sub">New accounts are created by workers. They take accounts from the queue in the order they were requested.</p></div></div>
      <div class="setting-row">
        <div><b>Workers (accounts at the same time)</b>
          <span>1 = one by one: a single worker finishes an account before the next starts. Higher values run several workers in
            parallel (each with its own proxy and device). Changes apply immediately, even while accounts are being created.</span></div>
        <div class="stepper sm" id="parallel-stepper">
          <button type="button" data-step="-1" aria-label="Less">−</button>
          <input type="number" id="parallel-input" min="1" max="20" value="${s.bot.parallel_accounts}">
          <button type="button" data-step="1" aria-label="More">+</button>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-head"><div><h2>${icon("refresh")} Stats refresh</h2>
        <p class="card-sub">Reading likes, visitors, messages and matches from Jaumo only happens when you click Refresh
          (never in the background). Each account can be refreshed once at a time, then 15 s cooldown.</p></div></div>
      <div class="setting-row">
        <div><b>Pause between accounts for "refresh all" (seconds)</b>
          <span>"Refresh all" works through the accounts one after another with this pause, so Jaumo sees no burst of requests.</span></div>
        <input type="number" id="sync-delay-input" min="2" max="600" step="1" value="${s.bot.sync_delay_seconds}" style="width:110px">
      </div>
    </div>
    <div class="card">
      <div class="card-head"><div><h2>${icon("shieldCheck")} Identity rules</h2>
        <p class="card-sub">Apply to every configuration and every launch. Names and photos are reserved the moment an account is queued.</p></div></div>
      <label class="setting-row">
        <div><b>Never reuse a name</b><span>A name that any account already has is never given out again. ${fmtNum(c.names_used)} names are taken so far.</span></div>
        <input type="checkbox" class="switch" id="rule-names" ${s.identity.unique_names ? "checked" : ""}>
      </label>
      <label class="setting-row">
        <div><b>Never reuse a photo</b><span>Each photo in the library is used by one account only.
          ${fmtNum(c.photos_available)} of ${fmtNum(c.photos_total)} photos are still available — <a href="#photos">open photo library</a>.</span></div>
        <input type="checkbox" class="switch" id="rule-photos" ${s.identity.unique_photos ? "checked" : ""}>
      </label>
    </div>`;
  const save = guard(async (body, msg) => { await api("/api/settings", { method: "PUT", body }); toast(msg); await loadSettings(); });
  $("#rule-names").onchange = (e) => save({ identity: { unique_names: e.target.checked, unique_photos: $("#rule-photos").checked } },
    e.target.checked ? "Names will never be reused" : "Names may now be reused");
  $("#rule-photos").onchange = (e) => save({ identity: { unique_names: $("#rule-names").checked, unique_photos: e.target.checked } },
    e.target.checked ? "Photos will never be reused" : "Photos may now be reused");
  const commit = debounce(() => {
    const v = Math.min(20, Math.max(1, +$("#parallel-input").value || 1));
    save({ bot: { parallel_accounts: v } }, v === 1 ? "Accounts are now created one by one" : `Accounts are now created by ${v} workers in parallel`);
  }, 600);
  $("#parallel-stepper").onclick = (e) => {
    const b = e.target.closest("[data-step]");
    if (!b) return;
    const inp = $("#parallel-input");
    inp.value = Math.min(20, Math.max(1, (+inp.value || 1) + +b.dataset.step));
    commit();
  };
  $("#parallel-input").onchange = commit;
  $("#sync-delay-input").onchange = (e) => {
    const v = Math.min(600, Math.max(2, +e.target.value || 10));
    save({ bot: { parallel_accounts: +$("#parallel-input").value || 1, sync_delay_seconds: v } }, `Pause between refreshes: ${v} s`);
  };
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

hydrateIcons();
applyI18n();
(async () => {
  try {
    const me = await api("/api/me");
    me.authenticated ? showApp(me.user) : showLogin();
  } catch {
    showLogin();
  }
})();
