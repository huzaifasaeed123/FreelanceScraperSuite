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
  try { await fn(...args); } catch (e) { if (e.message !== "Not authenticated") toast(serverText(e.message), true); }
};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(LANG === "de" ? "de-DE" : "en-GB", { year: "2-digit", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function fmtTime(iso) {
  return iso ? new Date(iso).toLocaleTimeString(LANG === "de" ? "de-DE" : "en-GB", { hour12: false }) : "";
}
function duration(run) {
  if (!run.started_at) return "";
  const end = run.finished_at ? new Date(run.finished_at) : new Date();
  const s = Math.max(0, Math.round((end - new Date(run.started_at)) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`;
}
const badge = (status) => `<span class="badge ${esc(status)}">${esc(statusText(status))}</span>`;

// ---------------------------------------------------------------------------
// Language (DE default) and theme (dark default)
// ---------------------------------------------------------------------------

const I18N = {
  de: {
    "brand.sub": "Accountverwaltung & Automatisierung",
    "sec.overview": "Übersicht", "sec.automation": "Automatisierung", "sec.data": "Daten", "sec.system": "System",
    "nav.dashboard": "Armaturenbrett", "nav.accounts": "Jaumo Accounts", "nav.logs": "Logs / Protokolle", "nav.configs": "Konfigurationen",
    "nav.proxies": "Proxies", "nav.photos": "Fotos", "nav.settings": "Einstellungen",
    "nav.jaumo": "Jaumo", "nav.config": "Konfiguration", "nav.names": "Nicknamen", "nav.cities": "Städte",
    "nav.rename": "Nicknamen ändern", "rename.pageSub": "Neue Nicknamen für bestehende und neue Accounts",
    "rename.title": "Neue Nicknamen", "rename.sub": "Aus dieser Liste bekommt ein Account seinen neuen Nicknamen — direkt nach der Registrierung oder später.",
    "rename.after": "Direkt nach der Registrierung ändern", "rename.afterSub": "Neue Accounts registrieren sich mit einem Namen aus „Nicknamen“ und bekommen nach Foto und Profiltext sofort einen Namen aus dieser Liste.",
    "rename.list": "Neue Nicknamen (einer pro Zeile)", "rename.rules": "Regel", "rename.unique": "Nickname nie wiederverwenden",
    "rename.uniqueSub": "Ein Name, den ein Account hat oder früher hatte, wird nie wieder vergeben.",
    "rename.later": "Später ändern", "rename.laterSub": "In der Accountliste Accounts auswählen → „Nickname ändern“ (oder ⋯-Menü bzw. Accountseite). Jeder Account bekommt den nächsten freien Namen aus der Liste.",
    "rename.stats": "{u} frei · {d} bereits vergeben von {n}", "rename.dropUsed": "Vergebene Namen entfernen",
    "rename.empty": "Noch keine Namen — einen pro Zeile oben einfügen.", "rename.loadFail": "Namensnutzung konnte nicht geladen werden",
    "rename.btn": "Nickname ändern", "rename.started": "{n} Nickname-Änderung(en) gestartet", "rename.skipped": "{n} übersprungen — {r}",
    "rename.kind": "Nickname ändern", "rename.formerly": "früher: {n}", "rename.notSet": "Nickname nicht geändert",
    "rename.chip": "Neue Nicknamen · {n} frei", "setup.rename": "Neue Nicknamen", "new.p.rename": "Nicht genug freie neue Nicknamen.",
    "rename.confirm": "{n} Account(s) bekommen einen neuen Nicknamen aus der Liste. Fortfahren?",
    "nav.about": "Profiltexte / Über mich", "about.pageSub": "Texte für das Profil neuer Accounts",
    "about.title": "Profiltexte", "about.sub": "Nach dem Profilfoto bekommt jeder neue Account einen dieser Texte als „Über mich“.",
    "about.on": "Profiltext bei neuen Accounts setzen", "about.onSub": "Aus = Accounts bleiben ohne Text (wie bisher).",
    "about.list": "Texte (einer pro Zeile)", "about.rules": "Regel", "about.unique": "Text nie wiederverwenden",
    "about.uniqueSub": "Ein Text, den schon ein Account hat, wird nie wieder vergeben.",
    "about.stats": "{u} frei · {d} bereits vergeben von {n}", "about.dropUsed": "Vergebene Texte entfernen",
    "about.empty": "Noch keine Texte — einen pro Zeile oben einfügen.", "about.loadFail": "Textnutzung konnte nicht geladen werden",
    "about.chip": "Profiltexte · {n} frei", "about.label": "Über mich", "about.notSet": "Profiltext nicht gesetzt",
    "setup.about": "Profiltexte", "new.p.about": "Nicht genug freie Profiltexte.",
    "swipe.btn": "Weiter swipen", "swipe.started": "{n} Account(s) swipen weiter",
    "swipe.skipped": "{n} übersprungen — {r}", "swipe.kind": "Weiter swipen",
    "swipe.tip": "Mit dem gespeicherten Login und Gerät weiter swipen (keine neue Registrierung)",
    "nav.toggle": "Menü auf-/zuklappen",
    "cfg.pageSub": "Einstellungen für neue Jaumo Accounts", "cfg.save": "Speichern", "cfg.saved": "Gespeichert",
    "cfg.apkTitle": "Jaumo-Zugang (APK)", "cfg.apkSub": "Schlüssel der Jaumo-App, mit denen jede Anfrage signiert wird.",
    "cfg.source": "Quelle", "cfg.srcEnv": "Umgebungsvariablen (Coolify)",
    "cfg.srcStored": "Gespeichertes Profil — Umgebungsvariablen sind nicht gesetzt", "cfg.srcNone": "Keine Schlüssel vorhanden",
    "cfg.apkNone": "Keine APK-Schlüssel — JAUMO_CLIENT_ID und JAUMO_SIGN_SECRET setzen.",
    "cfg.apkDisabled": "Die APK-Schlüssel sind deaktiviert.", "cfg.apkFailing": "{n} Fehlschläge in Folge beim Jaumo-Login.",
    "cfg.apkOk": "APK bereit", "cfg.apkReset": "Fehlerzähler zurücksetzen", "cfg.lastOk": "Letzter Erfolg", "cfg.failed": "fehlgeschlagen",
    "cfg.apkHow": "Ändern: in Coolify die Umgebungsvariablen setzen und neu deployen —",
    "health.ok": "OK", "health.warning": "Warnung", "health.failing": "Fehlerhaft", "health.disabled": "Deaktiviert", "health.untested": "Noch nicht getestet",
    "cfg.creation": "Account-Erstellung", "cfg.creationSub": "Worker nehmen die Accounts in der angeforderten Reihenfolge aus der Warteschlange.",
    "cfg.workers": "Worker (Accounts gleichzeitig)",
    "cfg.workersSub": "1 = nacheinander. Mehr Worker arbeiten parallel, jeder mit eigenem Proxy und Gerät. Gilt sofort, auch während Accounts erstellt werden.",
    "cfg.requireProxy": "Proxy erforderlich", "cfg.requireProxySub": "Ohne aktiven Proxy wird kein Account erstellt (nie direkt mit der Server-IP).",
    "cfg.swiping": "Swipen", "cfg.likeRatio": "Like-Anteil (0–1)", "cfg.maxSwipes": "Max. Swipes (0 = bis gesperrt)",
    "cfg.blockAfter": "Gesperrt nach N Fehlern in Folge", "cfg.emptyBatches": "Fertig nach N leeren Kartenstapeln", "cfg.timeout": "Anfrage-Timeout (s)",
    "cfg.profile": "Profil", "cfg.profileSub": "Immer weiblich. Alter wird zufällig im Bereich gewählt.",
    "cfg.ageMin": "Alter von", "cfg.ageMax": "Alter bis",
    "cfg.uniquePhotos": "Foto nie wiederverwenden", "cfg.uniquePhotosSub": "Jedes Foto wird nur von einem Account benutzt. {a} von {n} Fotos sind noch frei.",
    "cfg.photoPool": "Profilfotos", "cfg.photoPoolSub": "Keins ausgewählt = jedes freie Foto der Bibliothek ({n} frei). Auswählen, um nur diese Fotos zu nutzen.",
    "cfg.noPhotos": "Noch keine Fotos hochgeladen", "cfg.messaging": "Nachrichten",
    "cfg.msgOn": "Matches anschreiben erlaubt", "cfg.msgOnSub": "Erlaubt den Job „Matches anschreiben“ auf der Accounts-Seite. Beim Erstellen werden nie Nachrichten gesendet.",
    "cfg.templates": "Nachrichtenvorlagen (eine pro Zeile, zufällige Auswahl)",
    "cfg.sync": "Stats aktualisieren", "cfg.syncSub": "Erhaltene Likes, Besucher, Nachrichten und Matches werden von Jaumo gelesen (nur lesen). Arbeitende Accounts werden nie gleichzeitig gelesen.",
    "cfg.syncAfter": "Am Ende jeder Sitzung", "cfg.syncAfterSub": "Die Sitzung liest die Stats zum Schluss selbst (auch beim Stoppen) — mit ihrem eigenen Login, ohne neue Anmeldung.",
    "cfg.syncDuring": "Während der Sitzung alle N Swipes (0 = aus)", "cfg.syncDuringSub": "Die laufende Sitzung liest die Stats selbst mit ihrem Login. Beispiel 200: bei 2.000 Aktionen 10× gelesen (je 2 Anfragen).",
    "cfg.syncEvery": "Ruhende Accounts alle X Minuten (0 = aus)", "cfg.syncEverySub": "Liest alle Accounts, die gerade nicht arbeiten, nacheinander (mit der Pause unten). Kurz vorher gelesene werden übersprungen.",
    "cfg.syncDelay": "Pause zwischen Accounts bei „alle aktualisieren“ (Sekunden)",
    "cfg.syncDelaySub": "Die Accounts werden nacheinander mit dieser Pause gelesen, damit Jaumo keine Anfragespitze sieht.",
    "cfg.advanced": "Erweitert — die Standardwerte funktionieren; nur bei Bedarf ändern",
    "cfg.signup": "Registrierungsdaten", "cfg.signupSub": "Werte, die bei der Registrierung an Jaumo gesendet werden",
    "cfg.devices": "Geräte", "cfg.devicesSub": "{n} Handymodelle — eins wird pro Account gewählt",
    "cfg.delays": "Pausen", "cfg.delaysSub": "Zufällige Pausen zwischen den Schritten in Sekunden (min – max)",
    "names.pageSub": "Namen für neue Accounts", "names.source": "Namensquelle", "names.sourceSub": "Woher die Namen neuer Accounts kommen.",
    "names.auto": "Automatische Namen", "names.autoSub": "Eingebaute Liste mit {n} gängigen weiblichen Vornamen",
    "names.custom": "Eigene Liste", "names.customSub": "Nur die Namen, die du unten einfügst",
    "names.list": "Eigene Namen (einer pro Zeile)", "names.rules": "Regel", "names.unique": "Namen nie wiederverwenden",
    "names.uniqueSub": "Ein Name, den schon ein Account hat, wird nie wieder vergeben. {n} Namen sind bereits vergeben.",
    "names.stats": "{u} frei · {d} bereits vergeben von {n}", "names.repeat": "· Wiederverwendung erlaubt",
    "names.dropUsed": "Vergebene Namen entfernen", "names.emptyCustom": "Noch keine Namen — einen pro Zeile oben einfügen.",
    "names.noneUsed": "Noch keiner der automatischen Namen wurde vergeben.", "names.usedTip": "schon von einem Account benutzt", "names.freeTip": "frei",
    "names.loadFail": "Namensnutzung konnte nicht geladen werden",
    "cities.pageSub": "Standorte für neue Accounts", "cities.title": "Städte",
    "cities.sub": "Für jeden Account wird zufällig eine Stadt gewählt. Mit Radius bekommt jeder Account einen eigenen Punkt im Umkreis.",
    "cities.radius": "Standard-Radius um jede Stadt (km)", "cities.radiusSub": "0 = genau das Stadtzentrum · z. B. 15 = irgendwo im Umkreis von 15 km",
    "cities.list": "Städte — eine pro Zeile:", "cities.or": "oder", "cities.count": "{n} Städte",
    "cities.none": "Mindestens eine Stadt eintragen.", "cities.bad": "Zeile {i} ist ungültig: „{l}“ (Name,Breitengrad,Längengrad[,Radius_km 0–100])",
    "devices.bad": "Gerät in Zeile {i} ist ungültig: „{l}“ (Hersteller;Modell;Marke)",
    "msg.confirm": "Alle ausstehenden Matches dieser Accounts mit den Nachrichtenvorlagen anschreiben.",
    "msg.off": "Das Anschreiben ist ausgeschaltet. Aktiviere „Matches anschreiben erlaubt“ unter Konfiguration → Nachrichten.",
    "infra.apk": "Jaumo-Zugang (APK)", "infra.cities": "Städte",
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
    "res.done": "Fertig", "res.blocked": "Gesperrt", "res.failed": "Fehler", "res.stopped": "Gestoppt", "res.verification_required": "Verifizierung nötig", "res.limit_reached": "Limit erreicht",
    "res.interrupted": "Unterbrochen", "res.last": "Letzte Sitzung", "about.textLabel": "Über mich Text:",
    "state.queued": "In Warteschlange", "acc.stop": "Stoppen", "acc.dequeue": "Aus Warteschlange entfernen",
    "acc.stopped": "{n} Sitzung(en) gestoppt", "acc.stopConfirm": "{n} Account(s) stoppen? Laufende Sitzungen enden, wartende werden entfernt.",
    "state.active": "Aktiv", "state.working": "Arbeitet", "state.blocked": "Gesperrt", "state.error": "Fehler", "state.stopped": "Gestoppt",
    "state.verification": "Verifizierung nötig", "state.limit": "Limit erreicht", "verify.title": "Jaumo verlangt eine Verifizierung",
    "verify.sub": "Jaumo hat beim Liken eine Profil-Verifizierung verlangt. Das muss ein Mensch in der Jaumo-App machen (Selfie) — der Bot kann es nicht.",
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
    "setup.title": "Einrichtung", "setup.sub": "Das fehlt noch, bevor Accounts erstellt werden können:",
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
    "nav.dashboard": "Dashboard", "nav.accounts": "Jaumo Accounts", "nav.logs": "Logs", "nav.configs": "Configurations",
    "nav.proxies": "Proxies", "nav.photos": "Photos", "nav.settings": "Settings",
    "nav.jaumo": "Jaumo", "nav.config": "Configuration", "nav.names": "Nicknames", "nav.cities": "Cities",
    "nav.rename": "Change nicknames", "rename.pageSub": "New nicknames for existing and new accounts",
    "rename.title": "New nicknames", "rename.sub": "An account gets its new nickname from this list — right after registration or later.",
    "rename.after": "Change right after registration", "rename.afterSub": "New accounts register with a name from “Nicknames” and get a name from this list right after photo and profile text.",
    "rename.list": "New nicknames (one per line)", "rename.rules": "Rule", "rename.unique": "Never reuse a nickname",
    "rename.uniqueSub": "A name that an account has or had before is never given out again.",
    "rename.later": "Change later", "rename.laterSub": "In the accounts list select accounts → “Change nickname” (or the ⋯ menu / account page). Each account gets the next free name from the list.",
    "rename.stats": "{u} free · {d} already used of {n}", "rename.dropUsed": "Remove used names",
    "rename.empty": "No names yet — paste one per line above.", "rename.loadFail": "Could not load name usage",
    "rename.btn": "Change nickname", "rename.started": "{n} nickname change(s) started", "rename.skipped": "{n} skipped — {r}",
    "rename.kind": "Nickname change", "rename.formerly": "formerly: {n}", "rename.notSet": "Nickname not changed",
    "rename.chip": "New nicknames · {n} free", "setup.rename": "New nicknames", "new.p.rename": "Not enough free new nicknames.",
    "rename.confirm": "{n} account(s) get a new nickname from the list. Continue?",
    "nav.about": "Profile texts / About me", "about.pageSub": "Texts for the profile of new accounts",
    "about.title": "Profile texts", "about.sub": "After the profile photo every new account gets one of these texts as “About me”.",
    "about.on": "Set a profile text on new accounts", "about.onSub": "Off = accounts stay without text (as before).",
    "about.list": "Texts (one per line)", "about.rules": "Rule", "about.unique": "Never reuse a text",
    "about.uniqueSub": "A text that an account already has is never given out again.",
    "about.stats": "{u} free · {d} already used of {n}", "about.dropUsed": "Remove used texts",
    "about.empty": "No texts yet — paste one per line above.", "about.loadFail": "Could not load text usage",
    "about.chip": "Profile texts · {n} free", "about.label": "About me", "about.notSet": "Profile text not set",
    "setup.about": "Profile texts", "new.p.about": "Not enough free profile texts.",
    "swipe.btn": "Continue swiping", "swipe.started": "{n} account(s) continue swiping",
    "swipe.skipped": "{n} skipped — {r}", "swipe.kind": "Continue swiping",
    "swipe.tip": "Continue swiping with the stored login and device (no new signup)",
    "nav.toggle": "Expand / collapse menu",
    "cfg.pageSub": "Settings for new Jaumo accounts", "cfg.save": "Save", "cfg.saved": "Saved",
    "cfg.apkTitle": "Jaumo access (APK)", "cfg.apkSub": "Keys of the Jaumo app used to sign every request.",
    "cfg.source": "Source", "cfg.srcEnv": "Environment variables (Coolify)",
    "cfg.srcStored": "Stored profile — environment variables are not set", "cfg.srcNone": "No keys available",
    "cfg.apkNone": "No APK keys — set JAUMO_CLIENT_ID and JAUMO_SIGN_SECRET.",
    "cfg.apkDisabled": "The APK keys are disabled.", "cfg.apkFailing": "{n} failed Jaumo logins in a row.",
    "cfg.apkOk": "APK ready", "cfg.apkReset": "Reset failure count", "cfg.lastOk": "Last success", "cfg.failed": "failed",
    "cfg.apkHow": "To change: set the environment variables in Coolify and redeploy —",
    "health.ok": "OK", "health.warning": "Warning", "health.failing": "Failing", "health.disabled": "Disabled", "health.untested": "Not tested yet",
    "cfg.creation": "Account creation", "cfg.creationSub": "Workers take accounts from the queue in the order they were requested.",
    "cfg.workers": "Workers (accounts at the same time)",
    "cfg.workersSub": "1 = one by one. More workers run in parallel, each with its own proxy and device. Applies immediately, even while accounts are being created.",
    "cfg.requireProxy": "Proxy required", "cfg.requireProxySub": "No account is created without an enabled proxy (never directly from the server IP).",
    "cfg.swiping": "Swiping", "cfg.likeRatio": "Like ratio (0–1)", "cfg.maxSwipes": "Max swipes (0 = until blocked)",
    "cfg.blockAfter": "Blocked after N failures in a row", "cfg.emptyBatches": "Finish after N empty card batches", "cfg.timeout": "Request timeout (s)",
    "cfg.profile": "Profile", "cfg.profileSub": "Always female. The age is picked at random within the range.",
    "cfg.ageMin": "Age from", "cfg.ageMax": "Age to",
    "cfg.uniquePhotos": "Never reuse a photo", "cfg.uniquePhotosSub": "Each photo is used by one account only. {a} of {n} photos are still free.",
    "cfg.photoPool": "Profile photos", "cfg.photoPoolSub": "None selected = any free photo in the library ({n} free). Select photos to use only those.",
    "cfg.noPhotos": "No photos uploaded yet", "cfg.messaging": "Messages",
    "cfg.msgOn": "Messaging matches allowed", "cfg.msgOnSub": "Allows the “Message matches” job on the Accounts page. Creating accounts never sends messages.",
    "cfg.templates": "Message templates (one per line, random pick)",
    "cfg.sync": "Stats refresh", "cfg.syncSub": "Received likes, visitors, messages and matches are read from Jaumo (read-only). Working accounts are never read at the same time.",
    "cfg.syncAfter": "At the end of every session", "cfg.syncAfterSub": "The session reads its stats itself at the end (also when stopped) — with its own login, no new login.",
    "cfg.syncDuring": "During the session every N swipes (0 = off)", "cfg.syncDuringSub": "The running session reads its stats itself with its login. Example 200: 10 reads for 2,000 actions (2 requests each).",
    "cfg.syncEvery": "Idle accounts every X minutes (0 = off)", "cfg.syncEverySub": "Reads all accounts that are not working, one after another (with the pause below). Accounts read shortly before are skipped.",
    "cfg.syncDelay": "Pause between accounts for “refresh all” (seconds)",
    "cfg.syncDelaySub": "Accounts are read one after another with this pause, so Jaumo sees no burst of requests.",
    "cfg.advanced": "Advanced — the defaults work; change only if needed",
    "cfg.signup": "Signup details", "cfg.signupSub": "Values sent to Jaumo at registration",
    "cfg.devices": "Devices", "cfg.devicesSub": "{n} phone models — one is picked per account",
    "cfg.delays": "Delays", "cfg.delaysSub": "Random pauses between steps in seconds (min – max)",
    "names.pageSub": "Names for new accounts", "names.source": "Name source", "names.sourceSub": "Where the names of new accounts come from.",
    "names.auto": "Auto names", "names.autoSub": "Built-in list of {n} common female first names",
    "names.custom": "Custom list", "names.customSub": "Only the names you paste below",
    "names.list": "Custom names (one per line)", "names.rules": "Rule", "names.unique": "Never reuse a name",
    "names.uniqueSub": "A name that an account already has is never given out again. {n} names are taken so far.",
    "names.stats": "{u} free · {d} already used of {n}", "names.repeat": "· reuse allowed",
    "names.dropUsed": "Remove used names", "names.emptyCustom": "No names yet — paste one per line above.",
    "names.noneUsed": "None of the auto names have been used yet.", "names.usedTip": "already used by an account", "names.freeTip": "free",
    "names.loadFail": "Could not load name usage",
    "cities.pageSub": "Locations for new accounts", "cities.title": "Cities",
    "cities.sub": "A city is picked at random for each account. With a radius each account gets its own point around the city.",
    "cities.radius": "Default radius around each city (km)", "cities.radiusSub": "0 = exact city centre · e.g. 15 = anywhere within 15 km",
    "cities.list": "Cities — one per line:", "cities.or": "or", "cities.count": "{n} cities",
    "cities.none": "Add at least one city.", "cities.bad": "Line {i} is invalid: “{l}” (name,latitude,longitude[,radius_km 0–100])",
    "devices.bad": "Device line {i} is invalid: “{l}” (manufacturer;model;brand)",
    "msg.confirm": "Message all pending matches of these accounts with the message templates.",
    "msg.off": "Messaging is turned off. Enable “Messaging matches allowed” under Configuration → Messages.",
    "infra.apk": "Jaumo access (APK)", "infra.cities": "Cities",
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
    "res.done": "Finished", "res.blocked": "Blocked", "res.failed": "Error", "res.stopped": "Stopped", "res.verification_required": "Verification required", "res.limit_reached": "Limit reached",
    "res.interrupted": "Interrupted", "res.last": "Last session", "about.textLabel": "About me text:",
    "state.queued": "Queued", "acc.stop": "Stop", "acc.dequeue": "Remove from queue",
    "acc.stopped": "{n} session(s) stopped", "acc.stopConfirm": "Stop {n} account(s)? Running sessions end, queued ones are removed.",
    "state.active": "Active", "state.working": "Working", "state.blocked": "Blocked", "state.error": "Error", "state.stopped": "Stopped",
    "state.verification": "Verification required", "state.limit": "Limit reached", "verify.title": "Jaumo requires verification",
    "verify.sub": "Jaumo asked for a profile verification when liking. A person must do it in the Jaumo app (a selfie) — the bot cannot.",
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
    "setup.title": "Setup", "setup.sub": "Still missing before accounts can be created:",
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

// Inline translation for page texts: L("Deutsch", "English") — switches with the language menu.
function L(de, en) {
  return LANG === "de" ? de : en;
}

const STATUS_TEXT = {
  queued: ["Wartet", "Queued"], running: ["Läuft", "Running"], done: ["Fertig", "Done"],
  blocked: ["Gesperrt", "Blocked"], failed: ["Fehler", "Failed"], stopped: ["Gestoppt", "Stopped"],
  interrupted: ["Unterbrochen", "Interrupted"], active: ["Aktiv", "Active"], legacy: ["Importiert", "Imported"],
  photo_failed: ["Foto-Fehler", "Photo failed"], signing_up: ["Registrierung", "Signing up"],
  verification_required: ["Verifizierung nötig", "Verification required"],
  limit_reached: ["Limit erreicht", "Limit reached"],
};
function statusText(status) {
  const p = STATUS_TEXT[status];
  return p ? L(p[0], p[1]) : status;
}

function t(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) s = s.replace(/\{(\w+)\}/g, (_, v) => (vars[v] ?? ""));
  return s;
}

function applyI18n(root = document) {
  document.documentElement.lang = LANG;
  // Static HTML: English is the default text, data-de holds the German one (data-de-ph / data-de-title alike).
  root.querySelectorAll("[data-de]").forEach((el) => {
    if (el.dataset.en === undefined) el.dataset.en = el.textContent;
    el.textContent = LANG === "de" ? el.dataset.de : el.dataset.en;
  });
  root.querySelectorAll("[data-de-ph]").forEach((el) => {
    if (el.dataset.enPh === undefined) el.dataset.enPh = el.placeholder;
    el.placeholder = LANG === "de" ? el.dataset.dePh : el.dataset.enPh;
  });
  root.querySelectorAll("[data-de-title]").forEach((el) => {
    if (el.dataset.enTitle === undefined) el.dataset.enTitle = el.title;
    el.title = LANG === "de" ? el.dataset.deTitle : el.dataset.enTitle;
  });
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
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
  mapPin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
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
  await Promise.all([loadConfig(), loadPhotos()]);
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
  configs: () => loadConfigPage(),
  names: () => loadNamesPage(),
  about: () => loadAboutPage(),
  rename: () => loadRenamePage(),
  cities: () => loadCitiesPage(),
  proxies: () => loadProxies(),
  photos: () => loadPhotos(),
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
  if (navTab !== "dashboard") $("#nav-jaumo").classList.remove("collapsed");   // the Jaumo group holds every other page
  $$(".tab").forEach((s) => s.classList.toggle("hidden", s.id !== "tab-" + tab));
  $("#app-view").classList.remove("nav-open");
  window.scrollTo(0, 0);
  guard(tab === "account" ? () => openAccountPage(arg) : TAB_LOADERS[tab])();
}
window.addEventListener("hashchange", () => {
  if (!$("#app-view").classList.contains("hidden")) switchTab(location.hash.slice(1) || "dashboard");
});
$$("#tabs button").forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));

// Jaumo menu group: the header opens the accounts; the arrow folds the sub-menu (remembered per browser).
try { if (localStorage.getItem("navJaumo") === "0") $("#nav-jaumo").classList.add("collapsed"); } catch { /* storage blocked */ }
const toggleJaumoNav = (e) => {
  e.stopPropagation();
  e.preventDefault();
  const g = $("#nav-jaumo");
  g.classList.toggle("collapsed");
  try { localStorage.setItem("navJaumo", g.classList.contains("collapsed") ? "0" : "1"); } catch { /* storage blocked */ }
};
$("#nav-jaumo-toggle").addEventListener("click", toggleJaumoNav);
$("#nav-jaumo-toggle").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") toggleJaumoNav(e); });
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
  const apkBad = apkProblem(state.config);
  if (state.config && apkBad) items.push({ icon: "alert", tone: "danger", text: `APK: ${apkBad}`, href: "#configs" });
  const blocked = (s.accounts_by_status || {}).blocked || 0;
  if (blocked) items.push({ icon: "ban", tone: "danger", text: `${blocked} × ${t("state.blocked")}`, href: "#accounts" });
  if (!s.proxies_enabled) items.push({ icon: "globe", tone: "warn", text: L("Kein Proxy aktiv", "No proxy enabled"), href: "#proxies" });
  const freePhotos = (state.photos || []).filter((p) => p.status === "available").length;
  if (state.photos && freePhotos < 5) items.push({ icon: "image", tone: "warn", text: L(`Nur noch ${freePhotos} freie Fotos`, `${freePhotos} unused photos left`), href: "#photos" });
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
  $("#live-chip").lastChild.textContent = on ? "Live" : L("Getrennt", "Offline");
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
      reloadApksSoon();
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
const reloadApksSoon = throttle(() => guard(loadConfig)(), 1500);

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

const STEP_FLOW = {
  signup: ["client_token", "signup", "location", "profile", "photo", "verify", "about", "rename", "swiping"],
  message: ["login", "matches", "messaging"],
  sync: ["login", "links", "counters"],
  swipe: ["login", "profile", "swiping"],
  rename: ["login", "rename"],
};
const STEP_LABELS = {
  starting: ["Startet", "Starting"], waiting_proxy: ["Wartet auf Proxy", "Waiting for proxy"],
  client_token: ["App-Anmeldung", "Client token"], signup: ["Registrierung", "Signing up"],
  location: ["Standort setzen", "Setting location"], profile: ["Profil laden", "Loading profile"],
  photo: ["Foto hochladen", "Uploading photo"], verify: ["Foto prüfen", "Verifying photo"],
  about: ["Profiltext", "Profile text"], rename: ["Nickname ändern", "Changing nickname"],
  swiping: ["Swipen", "Swiping"], finished: ["Beendet", "Finished"], login: ["Anmelden", "Logging in"],
  matches: ["Matches laden", "Loading matches"], messaging: ["Nachrichten senden", "Messaging"],
  links: ["Links laden", "Loading links"], counters: ["Zähler lesen", "Reading counters"],
};
const stepLabel = (step) => (STEP_LABELS[step] ? L(...STEP_LABELS[step]) : step);
const KIND_TEXT = {
  signup: ["Erstellung + Swipen", "Signup + swiping"], swipe: ["Weiter swipen", "Continue swiping"],
  message: ["Matches anschreiben", "Messaging"], sync: ["Stats aktualisieren", "Stats refresh"],
  rename: ["Nickname ändern", "Nickname change"],
};
const kindText = (kind) => (KIND_TEXT[kind] ? L(...KIND_TEXT[kind]) : kind);

state.days = 14;
state.daily = [];
state.liveFilter = "active";

async function loadDashboard() {
  await Promise.all([loadStats(), loadDaily(), loadDashboardRuns(), renderSetupCheck()]);
}

// First-run checklist: the same server check as "Neuer Account", shown only while something is missing.
async function renderSetupCheck() {
  const box = $("#setup-check");
  const c = state.config;
  if (!c) { box.classList.add("hidden"); return; }
  const res = await api("/api/runs/check", { method: "POST", body: { count: 1, names: [] } });
  if (state.tab !== "dashboard") return;
  box.classList.toggle("hidden", res.ok);
  if (res.ok) { box.innerHTML = ""; return; }
  const byCode = Object.fromEntries(res.problems.map((p) => [p.code, p]));
  const proxyRequired = (c.settings || {}).require_proxy !== false;
  const rows = [["apk", "configs"], ["proxy", "proxies"], ["photos", "photos"], ["names", "names"],
    ...(c.settings.about_enabled ? [["about", "about"]] : []),
    ...(c.settings.rename_after_signup ? [["rename", "rename"]] : [])].map(([code, page]) => {
    const p = byCode[code];
    const note = p ? t("new.p." + code) : code === "proxy" && !proxyRequired ? t("setup.proxyOff") : t("setup.ok");
    return `<li class="${p ? "todo" : "done"}" data-setup="${code}" title="${esc(p ? serverText(p.message) : "")}">
      <span class="icon-bubble ${p ? "warn" : "ok"}">${icon(p ? "alert" : "check")}</span>
      <span><b>${esc(t("setup." + code))}</b><small>${esc(note)}</small></span>
      ${p ? `<a class="btn ghost sm" href="#${page}">${esc(t("new.fix"))}</a>` : ""}</li>`;
  }).join("");
  box.innerHTML = `<div class="card-head"><div><h2>${icon("sliders")} ${esc(t("setup.title"))}</h2>
    <p class="card-sub">${esc(t("setup.sub"))}</p></div></div><ul class="setup-list">${rows}</ul>`;
}

async function loadStats() {
  state.stats = await api("/api/stats");
  const s = state.stats;
  renderNotifications();
  $("#nav-running").textContent = s.running || "";
  $("#nav-apk").textContent = state.config && apkProblem(state.config) ? "!" : "";
  if (state.tab !== "dashboard") return;
  renderKpis();
  renderStatusBreakdown();
  renderEngagement();
  renderInfra();
  renderLaunchInfo();
  // Only the APK keys of the one configuration matter (old stored profiles are ignored).
  const apkBad = apkProblem(state.config);
  const lastErr = state.config && state.config.apk && state.config.apk.last_error;
  $("#apk-warnings").innerHTML = apkBad ? `<div class="alert">
      <span class="alert-icon">${icon("alert")}</span>
      <div class="alert-body"><b>${esc(t("cfg.apkTitle"))}</b> — ${esc(apkBad)}
        ${lastErr ? `<div class="muted mono">${esc(lastErr)}</div>` : ""}</div>
      <a class="btn small" href="#configs">${esc(t("nav.config"))}</a></div>` : "";
}

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
    delta = `<span class="delta ${d > 0 ? "up" : d < 0 ? "down" : "flat"}">${d > 0 ? "+" : ""}${d}</span> ${L("ggü. gestern", "vs yesterday")}`;
  }
  const active = (by.active || 0) + (by.legacy || 0);
  const blocked = by.blocked || 0;
  const matchRate = s.liked ? ((s.matches / s.liked) * 100).toFixed(1) : "0.0";
  $("#kpis").innerHTML = [
    kpiTile({ label: L("Account-Erstellung", "Account creation"), iconName: "cpu", tone: s.running || s.queued ? "ok" : "",
      value: s.running || s.queued ? L("Läuft", "Running") : L("Bereit", "Idle"),
      foot: s.running || s.queued
        ? `${s.running} worker${s.running === 1 ? "" : "s"} busy · ${s.queued} waiting`
        : s.parallel === 1 ? L("nacheinander (1 Worker)", "one by one (1 worker)") : L(`parallel · ${s.parallel} Worker`, `parallel · ${s.parallel} workers`) }),
    kpiTile({ label: L("Heute erstellt", "Created today"), iconName: "userPlus", tone: "info",
      value: fmtNum(today), foot: delta || L("heute registrierte Accounts", "accounts signed up today") }),
    kpiTile({ label: L("Aktive Accounts", "Active accounts"), iconName: "userCheck", tone: "ok",
      value: fmtNum(active), foot: L(`von ${fmtNum(s.accounts_total)} gesamt · <span class="sr-danger">${fmtNum(blocked)} gesperrt</span>`,
                                     `of ${fmtNum(s.accounts_total)} total · <span class="sr-danger">${fmtNum(blocked)} blocked</span>`) }),
    kpiTile({ label: "Matches", iconName: "heart", tone: "danger",
      value: fmtNum(s.matches), foot: L(`${matchRate}% von ${fmtNum(s.liked)} Likes`, `${matchRate}% of ${fmtNum(s.liked)} likes`) }),
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
    { label: L("Aktiv", "Active"), iconName: "checkCircle", tone: "ok", n: (by.active || 0) + (by.legacy || 0) },
    { label: L("Gesperrt", "Blocked"), iconName: "ban", tone: "danger", n: by.blocked || 0 },
    { label: L("Einrichtung fehlgeschlagen", "Failed setup"), iconName: "alert", tone: "warn", n: (by.failed || 0) + (by.photo_failed || 0) },
    { label: L("Gestoppt / in Arbeit", "Stopped / in progress"), iconName: "pause", tone: "neutral", n: (by.stopped || 0) + (by.signing_up || 0) },
  ];
  $("#status-sub").textContent = L(`${fmtNum(total)} Accounts insgesamt`, `${fmtNum(total)} accounts in total`);
  $("#status-breakdown").innerHTML = total
    ? `<div class="stat-rows">${groups.map((g) => statRow({ ...g, value: fmtNum(g.n), sub: `${pct(g.n, total)}%`, ratio: total ? g.n / total : 0 })).join("")}</div>`
    : emptyState("users", L("Noch keine Accounts", "No accounts yet"), L("Erstelle neue Accounts, um zu starten.", "Create new accounts to get started."));
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
    ${mini("percent", L("Match-Quote", "Match rate"), `${rate}<small>%</small>`)}
    ${mini("message", L("Gesendete Nachrichten", "Messages sent"), fmtNum(s.messages_sent), true)}
  </div>`;
}

function renderInfra() {
  const s = state.stats;
  const onProxy = Object.values(s.proxies_in_use || {}).reduce((a, b) => a + b, 0);
  const apkBad = apkProblem(state.config);
  $("#infra").innerHTML = `<div class="stat-rows">
    ${statRow({ iconName: "bot", tone: "accent", label: L("Worker (Accounts gleichzeitig)", "Workers (parallel accounts)"), value: fmtNum(s.parallel), sub: s.parallel === 1 ? L("nacheinander", "one by one") : "parallel" })}
    ${statRow({ iconName: "image", tone: "info", label: L("Freie Fotos", "Unused photos"), value: fmtNum((state.photos || []).filter((p) => p.status === "available").length) })}
    ${statRow({ iconName: "globe", tone: s.proxies_enabled ? "info" : "warn", label: L("Aktive Proxies", "Proxies enabled"), value: fmtNum(s.proxies_enabled), sub: L(`${onProxy} Sitzungen verbunden`, `${onProxy} sessions connected`) })}
    ${statRow({ iconName: "key", tone: apkBad ? "danger" : "ok", label: t("infra.apk"), value: apkBad ? "!" : "OK", sub: apkBad })}
    ${statRow({ iconName: "mapPin", tone: "neutral", label: t("infra.cities"), value: fmtNum(state.config ? state.config.settings.locations.length : 0) })}
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
  const dayFmt = (iso, opts) => new Date(iso + "T00:00:00").toLocaleDateString(LANG === "de" ? "de-DE" : "en-GB", opts);
  $("#chart-summary").innerHTML = [
    [L("Erstellt gesamt", "Total created"), fmtNum(total)],
    [L("Ø pro Tag", "Avg per day"), data.length ? (total / data.length).toFixed(1) : "0"],
    [L("Bester Tag", "Best day"), best && best.created ? `${best.created} <span class="muted" style="font-size:13px;font-weight:500">· ${dayFmt(best.date, { day: "numeric", month: "short" })}</span>` : "—"],
    [L("Jetzt gesperrt", "Now blocked"), `${fmtNum(blocked)} <span class="muted" style="font-size:13px;font-weight:500">· ${pct(blocked, total)}%</span>`],
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

  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${L(`Erstellte Accounts pro Tag, letzte ${data.length} Tage`, `Accounts created per day, last ${data.length} days`)}">
      <g class="grid">${grid}</g><g>${cols}</g><g class="axis">${axis}</g></svg>
    ${total ? "" : `<div class="chart-empty">${L("In diesem Zeitraum wurden keine Accounts erstellt", "No accounts created in this period")}</div>`}`;

  const tip = $("#chart-tip");
  el.querySelectorAll(".col").forEach((g) => {
    g.addEventListener("mousemove", (e) => {
      const d = data[+g.dataset.i];
      const row = (l, v) => `<div class="tip-row"><span>${l}</span><b>${fmtNum(v)}</b></div>`;
      tip.innerHTML = `<div class="tip-title">${esc(dayFmt(d.date, { weekday: "short", day: "numeric", month: "short" }))}</div>
        ${row(L("Erstellte Accounts", "Accounts created"), d.created)}<div class="tip-sep"></div>
        ${row(L("Aktiv", "Active"), d.active)}${row(L("Gesperrt", "Blocked"), d.blocked)}${row(L("Einrichtung fehlgeschlagen", "Failed setup"), d.failed)}${d.other ? row(L("Gestoppt / sonstige", "Stopped / other"), d.other) : ""}
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
  const all = [...state.runs.values()].filter((r) => r.kind !== "sync").sort((a, b) => b.id - a.id);
  const active = all.filter((r) => ACTIVE.has(r.status))
    .sort((a, b) => (a.status === b.status ? b.id - a.id : a.status === "running" ? -1 : 1));
  const recent = all.filter((r) => !ACTIVE.has(r.status)).slice(0, 12);
  $("#cnt-active").textContent = active.length;
  $("#cnt-recent").textContent = recent.length;
  const list = state.liveFilter === "active" ? active : state.liveFilter === "recent" ? recent : [...active, ...recent];
  $("#live-cards").innerHTML = list.length ? list.map(botCard).join("")
    : state.liveFilter === "active"
      ? emptyState("cpu", L("Keine Accounts in Arbeit", "No accounts in progress"), L("Anzahl wählen und auf „Accounts erstellen“ klicken.", "Choose how many accounts to create, then press Create accounts."))
      : emptyState("activity", L("Noch nichts hier", "Nothing here yet"), L("Beendete Sitzungen erscheinen hier.", "Finished sessions will show up here."));
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
  let label = stepLabel(r.step) || (r.status === "queued" ? L("In Warteschlange", "Queued") : "—");
  if (ended && r.step === "finished") label = L("Beendet", "Ended");
  const n = Math.min(flow.length, Math.max(0, idx + (running ? 1 : 0)));
  const right = r.status === "done" ? L("abgeschlossen", "complete") : ended ? statusText(r.status) : `${n} / ${flow.length}`;
  return `<div class="steps s-${esc(r.status)}">${segs}</div>
    <div class="step-label"><b>${esc(label)}</b><span>${esc(right)}</span></div>`;
}

function botCard(r) {
  const name = r.requested_name || (r.kind !== "signup" ? `Account #${r.account_id}` : L("Neuer Account", "New account"));
  const initial = (r.requested_name || "?").trim().charAt(0).toUpperCase() || "?";
  const metrics = r.kind === "sync"
    ? `<div class="bot-metrics" style="grid-template-columns:1fr"><div><b>${icon("refresh")}</b><span>${L("Stats aktualisieren", "stats refresh")}</span></div></div>`
    : r.kind === "message"
    ? `<div class="bot-metrics" style="grid-template-columns:1fr"><div><b>${r.messages_sent}</b><span>${L("Nachrichten gesendet", "messages sent")}</span></div></div>`
    : `<div class="bot-metrics">
        <div><b>${r.liked}</b><span>Likes</span></div><div><b>${r.disliked}</b><span>Dislikes</span></div>
        <div><b>${r.matches}</b><span>Matches</span></div><div><b>${r.swipes}</b><span>Swipes</span></div></div>`;
  const stop = (r.account_id ? iconBtn("externalLink", `data-account="${r.account_id}"`, L("Accountseite öffnen", "Open account page")) : "")
    + (ACTIVE.has(r.status) ? `<button class="btn small danger" data-stop="${r.id}">${icon("stop")}${L("Stoppen", "Stop")}</button>` : "");
  return `<div class="bot-card" data-run="${r.id}">
    <div class="bot-head">
      <div class="bot-avatar s-${esc(r.status)}">${esc(initial)}</div>
      <div class="bot-title">
        <div class="bot-name">${esc(name)}${r.kind === "message" ? icon("message") : ""}</div>
        <div class="bot-sub">${r.worker ? `${workerName(r.worker)} · ` : ""}#${r.id}${r.account_id ? ` · Account #${r.account_id}` : ""}</div>
      </div>
      ${badge(r.status)}
    </div>
    ${stepBar(r)}
    ${!ACTIVE.has(r.status) && r.reason ? `<div class="bot-reason" title="${esc(r.reason)}">${esc(reasonText(r.reason))}</div>` : ""}
    ${metrics}
    <div class="bot-foot">
      <div class="meta">
        <span title="${esc(r.proxy_label || L("kein Proxy", "no proxy"))}">${icon("globe")}${esc(r.proxy_label ? r.proxy_label.split(" ")[0] : L("direkt", "direct"))}</span>
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
    toast(L(`Sitzung #${stopBtn.dataset.stop} wird gestoppt`, `Stopping session #${stopBtn.dataset.stop}`));
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

function renderLaunchInfo() {
  const c = state.config;
  const s = state.stats;
  if (s) {
    const busy = s.running || s.queued;
    $("#launch-capacity").textContent = busy
      ? L(`${s.running} Worker beschäftigt — neue Accounts warten in der Warteschlange (${s.queued} wartend)`,
          `${s.running} worker${s.running === 1 ? "" : "s"} busy — new accounts wait in the queue (${s.queued} waiting)`)
      : L(`Alle Worker frei · ${s.parallel === 1 ? "nacheinander" : `${s.parallel} parallel`}`,
          `All workers free · ${s.parallel === 1 ? "one by one" : `${s.parallel} in parallel`}`);
    $("#launch-submit-label").textContent = busy ? L("In die Warteschlange", "Add to queue") : L("Accounts erstellen", "Create accounts");
  }
  if (!c) { $("#launch-config-info").innerHTML = ""; return; }
  const st = c.settings;
  const apkBad = apkProblem(c);
  const chip = (text, bad) => `<span class="chip${bad ? " bad" : ""}">${esc(text)}</span>`;
  $("#launch-config-info").innerHTML = [
    chip(apkBad || t("cfg.apkOk"), !!apkBad),
    chip(L(`${Math.round(st.like_ratio * 100)} % Likes / ${100 - Math.round(st.like_ratio * 100)} % Dislikes`,
           `${Math.round(st.like_ratio * 100)}% likes / ${100 - Math.round(st.like_ratio * 100)}% dislikes`)),
    chip(st.max_swipes ? L(`max. ${st.max_swipes} Swipes`, `max ${st.max_swipes} swipes`) : L("swipen bis gesperrt", "swipe until blocked")),
    chip(st.require_proxy ? L("Proxy erforderlich", "proxy required") : L("Proxy optional", "proxy optional"), st.require_proxy && state.stats && !state.stats.proxies_enabled),
    chip(L(`${st.photo_pool.length || "alle"} Fotos`, `${st.photo_pool.length || "all"} photos`)),
    chip(`${st.name_source === "auto" ? L("Automatische Namen", "auto names") : L("Eigene Namen", "custom names")}${c.names_unused !== undefined
      ? L(` · ${fmtNum(c.names_unused)} frei`, ` · ${fmtNum(c.names_unused)} unused`) : ""}`, c.names_unused === 0),
    ...(st.about_enabled ? [chip(t("about.chip", { n: fmtNum(c.about_unused ?? 0) }), !c.about_unused)] : []),
    ...(st.rename_after_signup ? [chip(t("rename.chip", { n: fmtNum(c.rename_unused ?? 0) }), !c.rename_unused)] : []),
    chip(L(`${fmtNum((state.photos || []).filter((p) => p.status === "available").length)} freie Fotos`, `${fmtNum((state.photos || []).filter((p) => p.status === "available").length)} unused photos`),
      !(state.photos || []).some((p) => p.status === "available")),
  ].join("");
}

$("#launch-form").addEventListener("click", (e) => {
  const b = e.target.closest("[data-step]");
  if (!b) return;
  const input = $("#launch-form").elements.count;
  input.value = Math.min(500, Math.max(1, (+input.value || 1) + +b.dataset.step));
});

$("#launch-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const body = { count: +f.get("count"), names: lines(f.get("names")) };
  const res = await api("/api/runs", { method: "POST", body });
  toast(L(`${res.run_ids.length} Account(s) werden erstellt`, `Creating ${res.run_ids.length} account(s)`));
  e.target.elements.names.value = "";
  guard(loadStats)();
  guard(loadPhotos)();
  state.liveFilter = "active";
  $$("#live-filter button").forEach((x) => x.classList.toggle("active", x.dataset.filter === "active"));
  await loadDashboardRuns();
}));

$("#stop-all-btn").onclick = guard(async () => {
  if (!confirm(L("Alles stoppen? Laufende Accounts werden gestoppt und die Warteschlange geleert.", "Stop everything? Accounts in progress stop and the queue is cleared."))) return;
  const res = await api("/api/runs/stop-all", { method: "POST" });
  toast(L(`${res.stopped} Sitzung(en) werden gestoppt`, `Stopping ${res.stopped} account session${res.stopped === 1 ? "" : "s"}`));
});

// ---------------------------------------------------------------------------
// Run detail + live log modal
// ---------------------------------------------------------------------------

async function openRunModal(id) {
  let lastId = 0, ws = null, closed = false, run = null;
  openModal(L(`Sitzung #${id}`, `Session #${id}`), `
    <div id="run-info"></div>
    <div class="log-toolbar">
      <label class="inline"><input type="checkbox" id="log-debug"> ${L("Debug anzeigen (HTTP-Antworten)", "show debug (HTTP bodies)")}</label>
      <label class="inline"><input type="checkbox" id="log-follow" checked> ${L("automatisch scrollen", "auto-scroll")}</label>
      <span class="muted" id="log-count"></span>
      <div class="actions" style="margin-left:auto">
        <button class="btn small danger hidden" id="run-stop">${L("Stoppen", "Stop")}</button>
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
    $("#log-count").textContent = L(`${count} Zeilen`, `${count} lines`);
    if ($("#log-follow")?.checked) view.scrollTop = view.scrollHeight;
  };

  const renderInfo = (r) => {
    run = { ...run, ...r };
    const isActive = ACTIVE.has(run.status);
    $("#run-stop").classList.toggle("hidden", !isActive);
    $("#run-info").innerHTML = `<dl class="kv">
      <dt>Status</dt><dd>${badge(run.status)} ${esc(reasonText(run.reason))}</dd>
      <dt>${L("Art / Schritt", "Type / step")}</dt><dd>${esc(kindText(run.kind))} · ${esc(stepLabel(run.step) || "—")}</dd>
      <dt>APK</dt><dd>${esc(run.apk_profile_name || "—")}</dd>
      <dt>Proxy</dt><dd>${esc(run.proxy_label || "—")}</dd>
      <dt>Account</dt><dd>${run.account_id ? `<a href="#account/${run.account_id}" data-close-modal>${esc(run.requested_name || "")} #${run.account_id}</a>` : esc(run.requested_name || "—")}</dd>
      <dt>${L("Foto", "Photo")}</dt><dd>${esc(run.photo || "—")}</dd>
      <dt>${L("Zähler", "Counters")}</dt><dd>Likes ${run.liked} · Dislikes ${run.disliked} · Matches ${run.matches} · Swipes ${run.swipes} · ${L("Nachrichten", "messages")} ${run.messages_sent}</dd>
      <dt>${L("Zeit", "Time")}</dt><dd>${L("erstellt", "created")} ${fmtDate(run.created_at)} · ${L("gestartet", "started")} ${fmtDate(run.started_at)} · ${L("beendet", "finished")} ${fmtDate(run.finished_at)} ${run.started_at ? "· " + duration(run) : ""}</dd>
    </dl>`;
  };

  $("#run-stop").onclick = guard(async () => {
    await api(`/api/runs/${id}/stop`, { method: "POST" });
    toast(L(`Sitzung #${id} wird gestoppt`, `Stopping session #${id}`));
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
      <th>#</th><th>${L("Art", "Type")}</th><th>Status</th><th>${L("Name / Account", "Name / account")}</th><th>Proxy</th><th>${L("Schritt", "Step")}</th>
      <th class="num">Likes</th><th class="num">Dislikes</th><th class="num">Matches</th><th class="num">${L("Nachr.", "Msgs")}</th>
      <th>${L("Erstellt", "Created")}</th><th>${L("Dauer", "Duration")}</th><th>${L("Ergebnis", "Result")}</th><th></th></tr></thead>
    <tbody>${res.items.map((r) => `<tr class="clickable" data-run="${r.id}">
      <td>${r.id}</td><td>${esc(kindText(r.kind))}</td><td>${badge(r.status)}</td>
      <td>${esc(r.requested_name || "")}${r.account_id ? ` <span class="muted">#${r.account_id}</span>` : ""}</td>
      <td class="wrapcell">${esc(r.proxy_label || "—")}</td><td>${esc(stepLabel(r.step) || "—")}</td>
      <td class="num">${r.liked}</td><td class="num">${r.disliked}</td><td class="num">${r.matches}</td><td class="num">${r.messages_sent}</td>
      <td>${fmtDate(r.created_at)}</td><td>${esc(duration(r))}</td><td class="wrapcell" title="${esc(r.reason)}">${esc(reasonText(r.reason))}</td>
      <td class="actions">${ACTIVE.has(r.status)
        ? `<button class="btn small danger" data-stop="${r.id}">${L("Stoppen", "Stop")}</button>`
        : iconBtn("trash", `data-del="${r.id}"`, L("Sitzung und Log löschen", "Delete session and its log"), "danger")}</td>
    </tr>`).join("") || `<tr><td colspan="14" class="muted">${L("Keine Sitzungen", "No sessions")}</td></tr>`}</tbody>`;
  renderPager("#runs-pager", res.total, RUNS_LIMIT, state.runsPage, (p) => { state.runsPage = p; guard(loadRuns)(); });
}

$("#runs-table").addEventListener("click", guard(async (e) => {
  const stop = e.target.closest("[data-stop]");
  const del = e.target.closest("[data-del]");
  if (stop) {
    await api(`/api/runs/${stop.dataset.stop}/stop`, { method: "POST" });
    return toast(L("Wird gestoppt …", "Stopping…"));
  }
  if (del) {
    if (!confirm(L(`Sitzung #${del.dataset.del} und ihr Log löschen?`, `Delete session #${del.dataset.del} and its log?`))) return;
    await api(`/api/runs/${del.dataset.del}`, { method: "DELETE" });
    return loadRuns();
  }
  const row = e.target.closest("[data-run]");
  if (row) openRunModal(+row.dataset.run);
}));
$("#runs-status").onchange = $("#runs-kind").onchange = () => { state.runsPage = 0; guard(loadRuns)(); };
$("#runs-refresh").onclick = guard(loadRuns);
$("#runs-cleanup").onclick = guard(async () => {
  const days = prompt(L("Logs beendeter Sitzungen löschen, die älter sind als wie viele Tage?", "Delete logs of finished sessions older than how many days?"), "7");
  if (days === null) return;
  const deleteRuns = confirm(L("Auch die Sitzungen selbst löschen? (OK = ja, Abbrechen = Sitzungen behalten, nur Logs löschen)",
                               "Also delete the sessions themselves? (OK = yes, Cancel = keep sessions, delete logs only)"));
  const res = await api("/api/runs/cleanup", { method: "POST", body: { days: +days || 0, delete_runs: deleteRuns } });
  toast(L(`${res.runs_cleaned} Sitzung(en) bereinigt`, `Cleaned ${res.runs_cleaned} session(s)`));
  loadRuns();
});

function renderPager(sel, total, limit, page, go) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const el = $(sel);
  el.innerHTML = `<span class="muted">${L(`${total} gesamt · Seite ${page + 1} / ${pages}`, `${total} total · page ${page + 1} / ${pages}`)}</span>
    <button class="btn small" data-p="${page - 1}" ${page <= 0 ? "disabled" : ""}>${icon("chevronLeft")}${L("Zurück", "Prev")}</button>
    <button class="btn small" data-p="${page + 1}" ${page + 1 >= pages ? "disabled" : ""}>${L("Weiter", "Next")}${icon("chevronRight")}</button>`;
  el.onclick = (e) => { const b = e.target.closest("[data-p]"); if (b && !b.disabled) go(+b.dataset.p); };
}

// ---------------------------------------------------------------------------
// Jaumo configuration — one configuration, edited on the pages
// Konfiguration · Nicknamen · Städte (each page saves only its own fields)
// ---------------------------------------------------------------------------

async function loadConfig() {
  state.config = await api("/api/config");
  renderLaunchInfo();
  return state.config;
}

// What is wrong with the APK keys ("" when they are fine).
function apkProblem(c) {
  const a = c && c.apk;
  if (!a) return t("cfg.apkNone");
  if (!a.enabled) return t("cfg.apkDisabled");
  if (a.health === "failing") return t("cfg.apkFailing", { n: a.fail_streak });
  return "";
}

// Save part of the settings; the server merges it into the configuration.
async function saveConfig(settings) {
  state.config = await api("/api/config", { method: "PUT", body: { settings } });
  renderLaunchInfo();
  return state.config;
}

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
    return `<p class="field-hint">${L("Jaumos eigene Auswahlliste wird bei der nächsten Account-Erstellung automatisch gespeichert",
      "Jaumo's own list of options is saved automatically at the next account creation")}
      (<code>signup/defaults</code>) ${L("und hier angezeigt.", "and will be shown here.")}</p>`;
  }
  const found = [];
  (function walk(v, path) {
    if (Array.isArray(v)) v.forEach((x, i) => walk(x, path));
    else if (v && typeof v === "object") Object.entries(v).forEach(([k, x]) => walk(x, path.concat(k)));
    else if (path.some((k) => /relationship/i.test(k)) && typeof v === "string" && /^[A-Z_]{3,}$/.test(v)) found.push(v);
  })(sd.data, []);
  const uniq = [...new Set(found)];
  const unknown = uniq.filter((v) => !(state.meta.relationship_values || []).includes(v));
  return `<div class="sent-list"><span>${L("Jaumo bietet an", "Jaumo offers")} (signup/defaults, ${esc(fmtDate(sd.received_at))}):</span>
      ${uniq.length ? uniq.map((v) => `<code>${esc(v)}</code>`).join(" ") : L("keine Beziehungswerte in der Antwort", "no relationship values found in the response")}
      ${unknown.length ? `<div class="sr-warn">${L("Noch nicht in der Auswahl", "Not in the dropdown yet")}: ${unknown.map(esc).join(", ")} — ${L("bitte dem Entwickler melden.", "tell the developer to add them.")}</div>` : ""}
      <details><summary>${L("Ganze Antwort anzeigen", "Show full response")}</summary><pre class="mono pre-json">${esc(JSON.stringify(sd.data, null, 2))}</pre></details></div>`;
}

const DELAY_TEXT = {
  after_signup: ["Nach der Registrierung", "After signup"], after_location: ["Nach dem Standort", "After location"],
  after_refresh: ["Nach der Anmeldung", "After token refresh"], after_profile: ["Nach dem Profil-Abruf", "After profile fetch"],
  before_photo: ["Vor dem Foto-Upload", "Before photo upload"], after_photo: ["Nach dem Foto-Upload", "After photo upload"],
  between_swipes: ["Zwischen Swipes", "Between swipes"], between_batches: ["Zwischen Kartenstapeln", "Between card batches"],
  before_message: ["Vor jeder Nachricht", "Before each message"],
};

const HEALTH_BADGE = { ok: "ok", warning: "warn", failing: "bad", disabled: "bad", untested: "" };

function parseLocations(text) {
  const out = lines(text).map((l, i) => {
    const [label, lat, lon, radius] = l.split(",").map((x) => x.trim());
    if (!label || !lat || !lon || isNaN(+lat) || isNaN(+lon) || Math.abs(+lat) > 90 || Math.abs(+lon) > 180
        || (radius !== undefined && radius !== "" && (isNaN(+radius) || +radius < 0 || +radius > 100))) {
      throw new Error(t("cities.bad", { i: i + 1, l }));
    }
    return { label, lat, lon, radius_km: radius === undefined || radius === "" ? null : +radius };
  });
  if (!out.length) throw new Error(t("cities.none"));
  return out;
}

function parseDevices(text) {
  return lines(text).map((l, i) => {
    const [manufacturer, model, brand] = l.split(";").map((x) => x.trim());
    if (!manufacturer || !model || !brand) throw new Error(t("devices.bad", { i: i + 1, l }));
    return { manufacturer, model, brand };
  });
}

function cfgCard(iconName, titleKey, subKey, body, extra = "") {
  return `<div class="card cfg-card"><div class="card-head"><div><h2>${icon(iconName)} ${esc(t(titleKey))}</h2>
      ${subKey ? `<p class="card-sub">${esc(t(subKey))}</p>` : ""}</div>${extra}</div>${body}</div>`;
}

function advSection(key, title, sub, body) {
  return `<details class="form-section adv" data-adv="${key}"><summary><span><b>${esc(title)}</b><small>${esc(sub)}</small></span></summary>
    ${body}</details>`;
}

function saveBar(id) {
  return `<div class="save-bar"><p class="error" id="${id}-error"></p>
    <button type="submit" class="btn primary">${icon("check")}${esc(t("cfg.save"))}</button></div>`;
}

// Submit handler shared by the three pages: shows the error in the save bar, toasts on success.
function onSave(form, id, fn) {
  form.addEventListener("invalid", (e) => { const d = e.target.closest("details"); if (d) d.open = true; }, true);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    $(`#${id}-error`).textContent = "";
    try {
      await fn(form.elements);
      toast(t("cfg.saved"));
      guard(TAB_LOADERS[state.tab])();
    } catch (err) {
      $(`#${id}-error`).textContent = err.message;
    }
  });
}

function renderApkCard(c) {
  const a = c.apk;
  const problem = apkProblem(c);
  const src = { env: t("cfg.srcEnv"), stored: t("cfg.srcStored"), none: t("cfg.srcNone") }[c.apk_source];
  const health = a ? `<span class="badge ${HEALTH_BADGE[a.health]}">${esc(t("health." + a.health))}</span>` : "";
  return cfgCard("key", "cfg.apkTitle", "cfg.apkSub", `
    ${problem ? `<div class="alert"><span class="alert-icon">${icon("alert")}</span>
        <div class="alert-body">${esc(problem)}${a && a.last_error ? `<div class="muted mono">${esc(a.last_error)}</div>` : ""}</div>
        ${a && a.fail_streak ? `<button class="btn small" type="button" id="apk-reset">${esc(t("cfg.apkReset"))}</button>` : ""}</div>` : ""}
    <dl class="kv">
      <dt>${esc(t("cfg.source"))}</dt><dd class="${c.apk_source === "env" ? "" : "sr-warn"}">${esc(src)}</dd>
      ${a ? `<dt>Client ID</dt><dd class="mono">${esc(a.client_id)}</dd>
        <dt>Sign secret</dt><dd class="mono">${esc(a.sign_secret_hint || "—")}</dd>
        <dt>User-Agent</dt><dd class="mono">${esc(a.user_agent)}</dd>
        <dt>${esc(t("cfg.lastOk"))}</dt><dd>${fmtDate(a.last_ok_at)} · ${fmtNum(a.ok_count)} OK / ${fmtNum(a.fail_count)} ${esc(t("cfg.failed"))}</dd>` : ""}
    </dl>
    <p class="field-hint">${esc(t("cfg.apkHow"))} <code>JAUMO_CLIENT_ID</code> · <code>JAUMO_SIGN_SECRET</code> · <code>JAUMO_USER_AGENT</code></p>`, health);
}

// --- Konfiguration -------------------------------------------------------------

async function loadConfigPage() {
  const [c, settings, meta] = await Promise.all([loadConfig(), api("/api/settings"), api("/api/meta"), loadPhotos()]);
  if (state.tab !== "configs") return;
  state.settings = settings;
  state.meta = meta;
  const s = c.settings, b = settings.bot;
  const photoSet = new Set(s.photo_pool);
  const photos = state.photos.filter((p) => p.status !== "rejected").map((p) => `<label class="pp-${p.status}" title="${esc(p.name)} — ${esc(photoStatusText(p.status))}">
      <input type="checkbox" name="photo_pool" value="${esc(p.name)}" ${photoSet.has(p.name) ? "checked" : ""}
        ${p.status !== "available" && !photoSet.has(p.name) ? "disabled" : ""}>
      <img src="/api/photos/${encodeURIComponent(p.name)}/thumb" loading="lazy" alt="">
      <span>${p.status === "available" ? esc(p.name) : esc(photoStatusText(p.status))}</span></label>`).join("");
  const free = state.photos.filter((p) => p.status === "available").length;
  const delays = Object.entries(DELAY_TEXT).map(([k, label]) => `<label>${esc(L(...label))}
      <span class="pair"><input type="number" step="any" min="0" name="d_${k}_0" value="${s.delays[k][0]}" required> –
      <input type="number" step="any" min="0" name="d_${k}_1" value="${s.delays[k][1]}" required> s</span></label>`).join("");
  const num = (name, key, attrs, value) => `<label>${esc(t(key))}<input type="number" name="${name}" ${attrs} value="${value}" required></label>`;

  $("#config-body").innerHTML = renderApkCard(c) + `<form id="cfg-form">
    ${cfgCard("cpu", "cfg.creation", "cfg.creationSub", `
      <div class="setting-row"><div><b>${esc(t("cfg.workers"))}</b><span>${esc(t("cfg.workersSub"))}</span></div>
        <div class="stepper sm" id="cfg-workers"><button type="button" data-step="-1" aria-label="−">−</button>
          <input type="number" name="parallel_accounts" min="1" max="20" value="${b.parallel_accounts}" required>
          <button type="button" data-step="1" aria-label="+">+</button></div></div>
      <label class="setting-row"><div><b>${esc(t("cfg.requireProxy"))}</b><span>${esc(t("cfg.requireProxySub"))}</span></div>
        <input type="checkbox" class="switch" name="require_proxy" ${s.require_proxy ? "checked" : ""}></label>`)}
    ${cfgCard("heart", "cfg.swiping", "", `<div class="form-grid">
      ${num("like_ratio", "cfg.likeRatio", 'step="any" min="0" max="1"', s.like_ratio)}
      ${num("max_swipes", "cfg.maxSwipes", 'min="0"', s.max_swipes)}
      ${num("block_threshold", "cfg.blockAfter", 'min="1"', s.block_threshold)}
      ${num("max_empty_batches", "cfg.emptyBatches", 'min="1"', s.max_empty_batches)}
      ${num("request_timeout", "cfg.timeout", 'min="5" max="300"', s.request_timeout)}</div>`)}
    ${cfgCard("user", "cfg.profile", "cfg.profileSub", `<div class="form-grid">
      ${num("age_min", "cfg.ageMin", 'min="18" max="99"', s.age_min)}
      ${num("age_max", "cfg.ageMax", 'min="18" max="99"', s.age_max)}</div>
      <label class="setting-row"><div><b>${esc(t("cfg.uniquePhotos"))}</b>
          <span>${esc(t("cfg.uniquePhotosSub", { a: fmtNum(settings.counts.photos_available), n: fmtNum(settings.counts.photos_total) }))}</span></div>
        <input type="checkbox" class="switch" name="unique_photos" ${settings.identity.unique_photos ? "checked" : ""}></label>
      <h3 class="cfg-h3">${esc(t("cfg.photoPool"))}</h3>
      <p class="field-hint">${esc(t("cfg.photoPoolSub", { n: fmtNum(free) }))} <a href="#photos">${esc(t("nav.photos"))}</a></p>
      <div class="photo-pick">${photos || `<span class="muted">${esc(t("cfg.noPhotos"))}</span>`}</div>`)}
    ${cfgCard("send", "cfg.messaging", "", `
      <label class="setting-row"><div><b>${esc(t("cfg.msgOn"))}</b><span>${esc(t("cfg.msgOnSub"))}</span></div>
        <input type="checkbox" class="switch" name="messaging_enabled" ${s.messaging_enabled ? "checked" : ""}></label>
      <label>${esc(t("cfg.templates"))}<textarea name="message_templates" rows="5">${esc(s.message_templates.join("\n"))}</textarea></label>`)}
    ${cfgCard("refresh", "cfg.sync", "cfg.syncSub", `
      <label class="setting-row"><div><b>${esc(t("cfg.syncAfter"))}</b><span>${esc(t("cfg.syncAfterSub"))}</span></div>
        <input type="checkbox" class="switch" name="sync_after_session" ${b.sync_after_session !== false ? "checked" : ""}></label>
      <div class="setting-row"><div><b>${esc(t("cfg.syncDuring"))}</b><span>${esc(t("cfg.syncDuringSub"))}</span></div>
        <input type="number" name="stats_every_swipes" min="0" max="10000" step="10" value="${b.stats_every_swipes ?? 200}" required style="width:110px"></div>
      <div class="setting-row"><div><b>${esc(t("cfg.syncEvery"))}</b><span>${esc(t("cfg.syncEverySub"))}</span></div>
        <input type="number" name="auto_sync_minutes" min="0" max="1440" step="1" value="${b.auto_sync_minutes ?? 30}" required style="width:110px"></div>
      <div class="setting-row"><div><b>${esc(t("cfg.syncDelay"))}</b><span>${esc(t("cfg.syncDelaySub"))}</span></div>
        <input type="number" name="sync_delay_seconds" min="2" max="600" step="1" value="${b.sync_delay_seconds}" required style="width:110px"></div>`)}
    <div class="adv-head">${esc(t("cfg.advanced"))}</div>
    ${advSection("signup", t("cfg.signup"), t("cfg.signupSub"), `
      <div class="form-grid" style="margin-top:4px">
        <label>${L("Geschlecht", "Gender")}<input value="${L("Weiblich (2)", "Female (2)")}" disabled></label>
        <label>${L("Sucht", "Looking for")}<select name="looking_for_gender">
          <option value="1" ${s.looking_for_gender === 1 ? "selected" : ""}>${L("Männer (1)", "Men (1)")}</option>
          <option value="2" ${s.looking_for_gender === 2 ? "selected" : ""}>${L("Frauen (2)", "Women (2)")}</option></select></label>
        <label>${L("Beziehungssuche", "Relationship search")} (relationship_search)<select name="relationship_search">${relationshipOptions(s.relationship_search)}</select></label>
        <label>${L("Dating-Beziehungssuche", "Dating relationship search")} (dating_relationship_search)<select name="dating_relationship_search">${relationshipOptions(s.dating_relationship_search)}</select></label>
      </div>
      ${offeredByJaumo()}
      <label class="toggle-row"><input type="checkbox" class="switch" name="allow_in_all_brands" ${s.allow_in_all_brands ? "checked" : ""}>
        <div><b>${L("In allen Marken erlauben", "Allow in all brands")}</b><span>${L("Gesendet als allow_in_all_brands=1 (Profil auch in Jaumos Partner-Apps sichtbar).", "Sent as allow_in_all_brands=1 (profile visible across Jaumo's partner apps).")}</span></div></label>
      <div class="sent-list">
        <span>${L("Außerdem gesendet", "Also sent")}:</span><code>name</code> ${L("aus „Nicknamen“", "from Nicknames")} · <code>birthday</code> ${L("aus dem Altersbereich", "from the age range")} ·
        <code>photo_url</code> (${L("fester Wert aus dem Original-Skript", "fixed value from the original script")}) ·
        <code>location_permission</code> ${L("und", "and")} <code>notifications_services</code> ${L("leer (wie die App)", "empty (as the app does)")}.
        ${L("Nach der Registrierung: Standort (Städte), Profilfoto, optional Profiltext und neuer Nickname.",
            "After signup: location (Cities), profile photo, optionally profile text and a new nickname.")}
      </div>`)}
    ${advSection("devices", t("cfg.devices"), t("cfg.devicesSub", { n: s.devices.length }), `
      <label><span>${L("Geräte — eine Zeile je Gerät", "Devices — one per line")}: <code>manufacturer;model;brand</code></span>
        <textarea name="devices" rows="8">${esc(s.devices.map((d) => `${d.manufacturer};${d.model};${d.brand}`).join("\n"))}</textarea></label>`)}
    ${advSection("delays", t("cfg.delays"), t("cfg.delaysSub"), `<div class="delay-grid">${delays}</div>`)}
    ${saveBar("cfg")}
  </form>`;

  const reset = $("#apk-reset");
  if (reset) reset.onclick = guard(async () => {
    await api(`/api/apk-profiles/${c.apk.id}/reset-health`, { method: "POST" });
    await loadConfigPage();
  });
  const form = $("#cfg-form");
  $("#cfg-workers").onclick = (e) => {
    const step = e.target.closest("[data-step]");
    if (!step) return;
    const inp = form.elements.parallel_accounts;
    inp.value = Math.min(20, Math.max(1, (+inp.value || 1) + +step.dataset.step));
  };
  onSave(form, "cfg", async (f) => {
    const devices = parseDevices(f.devices.value);
    const delaysOut = {};
    for (const k of Object.keys(DELAY_TEXT)) delaysOut[k] = [+f[`d_${k}_0`].value, +f[`d_${k}_1`].value];
    await saveConfig({
      require_proxy: f.require_proxy.checked,
      like_ratio: +f.like_ratio.value,
      max_swipes: +f.max_swipes.value,
      block_threshold: +f.block_threshold.value,
      max_empty_batches: +f.max_empty_batches.value,
      request_timeout: +f.request_timeout.value,
      age_min: +f.age_min.value,
      age_max: +f.age_max.value,
      photo_pool: new FormData(form).getAll("photo_pool"),
      messaging_enabled: f.messaging_enabled.checked,
      message_templates: lines(f.message_templates.value),
      looking_for_gender: +f.looking_for_gender.value,
      relationship_search: f.relationship_search.value,
      dating_relationship_search: f.dating_relationship_search.value,
      allow_in_all_brands: f.allow_in_all_brands.checked,
      devices,
      delays: delaysOut,
    });
    await api("/api/settings", { method: "PUT", body: {
      bot: { parallel_accounts: Math.min(20, Math.max(1, +f.parallel_accounts.value || 1)),
             sync_delay_seconds: Math.min(600, Math.max(2, +f.sync_delay_seconds.value || 10)),
             sync_after_session: f.sync_after_session.checked,
             stats_every_swipes: Math.max(0, Math.round(+f.stats_every_swipes.value || 0)),
             auto_sync_minutes: Math.max(0, Math.round(+f.auto_sync_minutes.value || 0)) },
      identity: { unique_names: settings.identity.unique_names, unique_photos: f.unique_photos.checked },
    } });
  });
}

// --- Nicknamen -----------------------------------------------------------------

async function loadNamesPage() {
  const [c, settings, meta] = await Promise.all([loadConfig(), api("/api/settings"), api("/api/meta")]);
  if (state.tab !== "names") return;
  state.settings = settings;
  state.meta = meta;
  const s = c.settings;
  $("#names-body").innerHTML = `<form id="names-form">
    ${cfgCard("user", "names.source", "names.sourceSub", `
      <div class="choice-cards">
        <label class="choice"><input type="radio" name="name_source" value="auto" ${s.name_source === "auto" ? "checked" : ""}>
          <div><b>${esc(t("names.auto"))}</b><span>${esc(t("names.autoSub", { n: meta.auto_names.length }))}</span></div></label>
        <label class="choice"><input type="radio" name="name_source" value="custom" ${s.name_source === "custom" ? "checked" : ""}>
          <div><b>${esc(t("names.custom"))}</b><span>${esc(t("names.customSub"))}</span></div></label>
      </div>
      <label id="custom-names-box" class="${s.name_source === "custom" ? "" : "hidden"}">${esc(t("names.list"))}
        <textarea name="name_pool" rows="10">${esc(s.name_pool.join("\n"))}</textarea></label>
      <div class="name-usage" id="name-usage"><span class="muted">…</span></div>`)}
    ${cfgCard("shieldCheck", "names.rules", "", `
      <label class="setting-row"><div><b>${esc(t("names.unique"))}</b><span>${esc(t("names.uniqueSub", { n: fmtNum(settings.counts.names_used) }))}</span></div>
        <input type="checkbox" class="switch" name="unique_names" ${settings.identity.unique_names ? "checked" : ""}></label>`)}
    ${saveBar("names")}
  </form>`;

  const form = $("#names-form");
  let usage = {};
  const render = () => {
    const custom = form.elements.name_source.value === "custom";
    $("#custom-names-box").classList.toggle("hidden", !custom);
    const seen = new Set();
    const pool = (custom ? lines(form.elements.name_pool.value) : meta.auto_names)
      .filter((n) => !seen.has(n.toLowerCase()) && seen.add(n.toLowerCase()));
    const isUsed = (n) => (usage[n.trim().toLocaleLowerCase()] || 0) > 0;
    const used = pool.filter(isUsed);
    const shown = custom ? pool : used;
    $("#name-usage").innerHTML = `<div class="name-usage-head">
        <span>${esc(t("names.stats", { u: fmtNum(pool.length - used.length), d: fmtNum(used.length), n: fmtNum(pool.length) }))}
          ${form.elements.unique_names.checked ? "" : `<span class="muted">${esc(t("names.repeat"))}</span>`}</span>
        ${custom && used.length ? `<button type="button" class="btn small" id="drop-used">${esc(t("names.dropUsed"))}</button>` : ""}
      </div>
      ${shown.length ? `<div class="name-chips">${shown.map((n) =>
        `<span class="name-chip${isUsed(n) ? " used" : ""}" title="${esc(t(isUsed(n) ? "names.usedTip" : "names.freeTip"))}">${esc(n)}</span>`).join("")}</div>`
        : `<span class="muted">${esc(t(custom ? "names.emptyCustom" : "names.noneUsed"))}</span>`}`;
    const drop = $("#drop-used");
    if (drop) drop.onclick = () => {
      form.elements.name_pool.value = lines(form.elements.name_pool.value).filter((n) => !isUsed(n)).join("\n");
      render();
    };
  };
  form.addEventListener("change", (e) => { if (["name_source", "unique_names"].includes(e.target.name)) render(); });
  form.elements.name_pool.addEventListener("input", debounce(render, 250));
  api("/api/names/usage").then((u) => { usage = u; if (document.body.contains(form)) render(); })
    .catch(() => { $("#name-usage").textContent = t("names.loadFail"); });

  onSave(form, "names", async (f) => {
    await saveConfig({ name_source: f.name_source.value, name_pool: lines(f.name_pool.value) });
    await api("/api/settings", { method: "PUT", body: {
      identity: { unique_names: f.unique_names.checked, unique_photos: settings.identity.unique_photos } } });
  });
}

// --- Nicknamen ändern ------------------------------------------------------------

async function loadRenamePage() {
  const c = await loadConfig();
  if (state.tab !== "rename") return;
  const s = c.settings;
  $("#rename-body").innerHTML = `<form id="rename-form">
    ${cfgCard("pencil", "rename.title", "rename.sub", `
      <label class="setting-row"><div><b>${esc(t("rename.after"))}</b><span>${esc(t("rename.afterSub"))}</span></div>
        <input type="checkbox" class="switch" name="rename_after_signup" ${s.rename_after_signup ? "checked" : ""}></label>
      <div class="setting-row"><div><b>${esc(t("rename.later"))}</b><span>${esc(t("rename.laterSub"))}</span></div>
        <a class="btn ghost sm" href="#accounts">${esc(t("nav.jaumo"))}</a></div>
      <label>${esc(t("rename.list"))}<textarea name="rename_pool" rows="10">${esc(s.rename_pool.join("\n"))}</textarea></label>
      <div class="name-usage" id="rename-usage"><span class="muted">…</span></div>`)}
    ${cfgCard("shieldCheck", "rename.rules", "", `
      <label class="setting-row"><div><b>${esc(t("rename.unique"))}</b><span>${esc(t("rename.uniqueSub"))}</span></div>
        <input type="checkbox" class="switch" name="rename_unique" ${s.rename_unique ? "checked" : ""}></label>`)}
    ${saveBar("rename")}
  </form>`;

  const form = $("#rename-form");
  let usage = {};
  const render = () => {
    const seen = new Set();
    const pool = lines(form.elements.rename_pool.value).filter((x) => !seen.has(x.toLowerCase()) && seen.add(x.toLowerCase()));
    const isUsed = (x) => (usage[x.trim().toLocaleLowerCase()] || 0) > 0;
    const used = pool.filter(isUsed);
    $("#rename-usage").innerHTML = `<div class="name-usage-head">
        <span>${esc(t("rename.stats", { u: fmtNum(pool.length - used.length), d: fmtNum(used.length), n: fmtNum(pool.length) }))}</span>
        ${used.length ? `<button type="button" class="btn small" id="rename-drop-used">${esc(t("rename.dropUsed"))}</button>` : ""}
      </div>
      ${pool.length ? `<div class="name-chips">${pool.map((x) =>
        `<span class="name-chip${isUsed(x) ? " used" : ""}" title="${esc(t(isUsed(x) ? "names.usedTip" : "names.freeTip"))}">${esc(x)}</span>`).join("")}</div>`
        : `<span class="muted">${esc(t("rename.empty"))}</span>`}`;
    const drop = $("#rename-drop-used");
    if (drop) drop.onclick = () => {
      form.elements.rename_pool.value = lines(form.elements.rename_pool.value).filter((x) => !isUsed(x)).join("\n");
      render();
    };
  };
  form.elements.rename_pool.addEventListener("input", debounce(render, 250));
  api("/api/rename/usage").then((u) => { usage = u; if (document.body.contains(form)) render(); })
    .catch(() => { $("#rename-usage").textContent = t("rename.loadFail"); });
  onSave(form, "rename", async (f) => {
    await saveConfig({ rename_after_signup: f.rename_after_signup.checked, rename_pool: lines(f.rename_pool.value),
                       rename_unique: f.rename_unique.checked });
  });
}

// --- Profiltexte / Über mich ----------------------------------------------------

async function loadAboutPage() {
  const c = await loadConfig();
  if (state.tab !== "about") return;
  const s = c.settings;
  $("#about-body").innerHTML = `<form id="about-form">
    ${cfgCard("fileText", "about.title", "about.sub", `
      <label class="setting-row"><div><b>${esc(t("about.on"))}</b><span>${esc(t("about.onSub"))}</span></div>
        <input type="checkbox" class="switch" name="about_enabled" ${s.about_enabled ? "checked" : ""}></label>
      <label>${esc(t("about.list"))}<textarea name="about_pool" rows="12">${esc(s.about_pool.join("\n"))}</textarea></label>
      <div class="name-usage" id="about-usage"><span class="muted">…</span></div>`)}
    ${cfgCard("shieldCheck", "about.rules", "", `
      <label class="setting-row"><div><b>${esc(t("about.unique"))}</b><span>${esc(t("about.uniqueSub"))}</span></div>
        <input type="checkbox" class="switch" name="about_unique" ${s.about_unique ? "checked" : ""}></label>`)}
    ${saveBar("about")}
  </form>`;

  const form = $("#about-form");
  let usage = {};
  const render = () => {
    const seen = new Set();
    const pool = lines(form.elements.about_pool.value).filter((x) => !seen.has(x.toLowerCase()) && seen.add(x.toLowerCase()));
    const isUsed = (x) => (usage[x.trim().toLocaleLowerCase()] || 0) > 0;
    const used = pool.filter(isUsed);
    $("#about-usage").innerHTML = `<div class="name-usage-head">
        <span>${esc(t("about.stats", { u: fmtNum(pool.length - used.length), d: fmtNum(used.length), n: fmtNum(pool.length) }))}</span>
        ${used.length ? `<button type="button" class="btn small" id="about-drop-used">${esc(t("about.dropUsed"))}</button>` : ""}
      </div>
      ${pool.length ? `<div class="about-list">${pool.map((x) =>
        `<span class="name-chip${isUsed(x) ? " used" : ""}" title="${esc(t(isUsed(x) ? "names.usedTip" : "names.freeTip"))}">${esc(x)}</span>`).join("")}</div>`
        : `<span class="muted">${esc(t("about.empty"))}</span>`}`;
    const drop = $("#about-drop-used");
    if (drop) drop.onclick = () => {
      form.elements.about_pool.value = lines(form.elements.about_pool.value).filter((x) => !isUsed(x)).join("\n");
      render();
    };
  };
  form.elements.about_pool.addEventListener("input", debounce(render, 250));
  api("/api/about/usage").then((u) => { usage = u; if (document.body.contains(form)) render(); })
    .catch(() => { $("#about-usage").textContent = t("about.loadFail"); });
  onSave(form, "about", async (f) => {
    await saveConfig({ about_enabled: f.about_enabled.checked, about_pool: lines(f.about_pool.value),
                       about_unique: f.about_unique.checked });
  });
}

// --- Städte --------------------------------------------------------------------

async function loadCitiesPage() {
  const c = await loadConfig();
  if (state.tab !== "cities") return;
  const s = c.settings;
  const text = s.locations.map((l) => `${l.label},${l.lat},${l.lon}${l.radius_km != null ? `,${l.radius_km}` : ""}`).join("\n");
  $("#cities-body").innerHTML = `<form id="cities-form">
    ${cfgCard("mapPin", "cities.title", "cities.sub", `
      <div class="setting-row"><div><b>${esc(t("cities.radius"))}</b><span>${esc(t("cities.radiusSub"))}</span></div>
        <input type="number" name="location_radius_km" min="0" max="100" step="any" value="${s.location_radius_km ?? 0}" required style="width:110px"></div>
      <label><span>${esc(t("cities.list"))} <code>Name,lat,lon</code> ${esc(t("cities.or"))} <code>Name,lat,lon,radius_km</code></span>
        <textarea name="locations" rows="14" class="mono">${esc(text)}</textarea></label>
      <div class="city-preview" id="city-preview"></div>`)}
    ${saveBar("cities")}
  </form>`;
  const form = $("#cities-form");
  const preview = () => {
    const box = $("#city-preview");
    try {
      const locs = parseLocations(form.elements.locations.value);
      const r = +form.elements.location_radius_km.value || 0;
      box.innerHTML = `<div class="muted">${esc(t("cities.count", { n: locs.length }))}</div><div class="name-chips">${locs.map((l) => {
        const radius = l.radius_km ?? r;
        return `<span class="name-chip">${icon("mapPin")}${esc(l.label)}${radius ? ` · ${radius} km` : ""}</span>`;
      }).join("")}</div>`;
    } catch (err) {
      box.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    }
  };
  preview();
  form.addEventListener("input", debounce(preview, 250));
  onSave(form, "cities", async (f) => {
    await saveConfig({ locations: parseLocations(f.locations.value), location_radius_km: +f.location_radius_km.value || 0 });
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
      <th><input type="checkbox" id="proxy-all"></th><th>#</th><th>${L("Bezeichnung", "Label")}</th><th>Host:Port</th><th>${L("Benutzer", "User")}</th>
      <th>${L("Modus", "Mode")}</th><th>${L("Aktiv", "Enabled")}</th><th class="num">${L("In Nutzung", "In use")}</th><th class="num">${L("Genutzt", "Used")}</th><th>${L("Letzter Test", "Last test")}</th><th></th></tr></thead>
    <tbody>${proxies.map((p) => {
      const test = p.last_test_at == null ? `<span class="muted">${L("nie", "never")}</span>`
        : p.last_test_ok ? `<span class="badge ok">OK</span> ${esc(p.last_test_ip)} · ${esc(p.last_test_country)}`
        : `<span class="badge bad" title="${esc(p.last_test_error)}">${L("Fehler", "fail")}</span> <span class="muted wrapcell">${esc((p.last_test_error || "").slice(0, 60))}</span>`;
      return `<tr>
        <td><input type="checkbox" data-sel="${p.id}" ${state.proxySelected.has(p.id) ? "checked" : ""}></td>
        <td>${p.id}</td><td>${esc(p.label)}</td>
        <td class="mono">${esc(p.scheme)}://${esc(p.host)}:${p.port}</td>
        <td class="mono wrapcell" title="${esc(p.username)}">${esc(p.username)}</td>
        <td>${p.shared ? `<span class="badge info">${L("geteilt", "shared")}</span>` : `<span class="badge">${L("dediziert", "dedicated")}</span>`}</td>
        <td><input type="checkbox" data-toggle="${p.id}" ${p.enabled ? "checked" : ""}></td>
        <td class="num">${p.in_use}</td><td class="num">${p.use_count}</td>
        <td title="${esc(fmtDate(p.last_test_at))}">${test}</td>
        <td class="actions">${iconBtn("zap", `data-test="${p.id}"`, L("Proxy testen", "Test proxy"))}
          ${iconBtn("pencil", `data-edit="${p.id}"`, L("Proxy bearbeiten", "Edit proxy"))}
          ${iconBtn("trash", `data-del="${p.id}"`, L("Proxy löschen", "Delete proxy"), "danger")}</td></tr>`;
    }).join("") || `<tr><td colspan="11" class="muted">${L("Noch keine Proxies", "No proxies yet")}</td></tr>`}</tbody>`;
  updateProxySelected();
}

function updateProxySelected() {
  $("#proxy-selected").textContent = L(`${state.proxySelected.size} ausgewählt`, `${state.proxySelected.size} selected`);
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
    toast(r.ok ? `OK — ${r.ip} (${r.country})` : `${L("Fehlgeschlagen", "Failed")}: ${r.error}`, !r.ok);
    return loadProxies();
  }
  if (b.dataset.edit) return openProxyEditor(proxies.find((p) => p.id === +b.dataset.edit));
  if (b.dataset.del) {
    if (!confirm(L("Diesen Proxy löschen?", "Delete this proxy?"))) return;
    await api(`/api/proxies/${b.dataset.del}`, { method: "DELETE" });
    return loadProxies();
  }
}));

$("#proxy-bulk-actions").addEventListener("click", guard(async (e) => {
  const b = e.target.closest("[data-action]");
  if (!b || !state.proxySelected.size) return;
  const action = b.dataset.action;
  if (action === "delete" && !confirm(L(`${state.proxySelected.size} Proxies löschen?`, `Delete ${state.proxySelected.size} proxies?`))) return;
  b.disabled = true;
  const res = await api("/api/proxies/bulk-action", { method: "POST", body: { ids: [...state.proxySelected], action } });
  if (action === "test") toast(L(`${res.tested} getestet: ${res.ok} OK`, `Tested ${res.tested}: ${res.ok} ok`));
  if (action === "delete") state.proxySelected.clear();
  await loadProxies();
}));

$("#proxy-test-all").onclick = guard(async () => {
  const btn = $("#proxy-test-all");
  btn.disabled = true;
  try {
    const res = await api("/api/proxies/test-all", { method: "POST" });
    toast(L(`${res.tested} getestet: ${res.ok} OK`, `Tested ${res.tested}: ${res.ok} ok`));
  } finally { btn.disabled = false; }
  await loadProxies();
});

$("#proxy-bulk-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = e.target.elements;
  if (f.replace.checked && !confirm(L("ALLE vorhandenen Proxies durch diese Zeilen ersetzen?", "Replace ALL existing proxies with these lines?"))) return;
  const res = await api("/api/proxies/bulk", { method: "POST", body: {
    text: f.text.value, shared: f.shared.value === "1", label: f.label.value.trim(), replace: f.replace.checked,
  } });
  toast(L(`${res.added} Proxy-Zeile(n) hinzugefügt`, `Added ${res.added} proxy line(s)`));
  e.target.reset();
  await loadProxies();
}));

function openProxyEditor(p) {
  openModal(L(`Proxy #${p.id} bearbeiten`, `Edit proxy #${p.id}`), `
    <form id="proxy-form">
      <div class="form-grid">
        <label>${L("Bezeichnung", "Label")}<input name="label" value="${esc(p.label)}"></label>
        <label>${L("Protokoll", "Scheme")}<select name="scheme">${["http", "https", "socks5", "socks5h", "socks4"].map((s) =>
          `<option ${s === p.scheme ? "selected" : ""}>${s}</option>`).join("")}</select></label>
        <label>Host<input name="host" value="${esc(p.host)}" required></label>
        <label>Port<input name="port" type="number" value="${p.port}" required></label>
        <label class="span-2">${L("Benutzername", "Username")}<input name="username" value="${esc(p.username)}" class="mono"></label>
        <label class="span-2">${L("Passwort", "Password")}<input name="password" value="${esc(p.password)}" class="mono"></label>
        <label class="inline"><input type="checkbox" name="shared" ${p.shared ? "checked" : ""}> ${L("Geteilt (rotierendes Gateway)", "Shared (rotating gateway)")}</label>
        <label class="inline"><input type="checkbox" name="enabled" ${p.enabled ? "checked" : ""}> ${L("Aktiv", "Enabled")}</label>
      </div>
      <p class="error" id="proxy-error"></p>
      <div class="modal-foot"><button type="button" class="btn ghost" id="proxy-cancel">${esc(t("common.cancel"))}</button>
        <button class="btn primary" type="submit">${L("Speichern", "Save")}</button></div>
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
const PHOTO_STATUS = { available: ["Frei", "Available"], reserved: ["Reserviert", "Reserved"],
                       used: ["Benutzt", "Used"], rejected: ["Abgelehnt", "Rejected"] };
const photoStatusText = (s) => (PHOTO_STATUS[s] ? L(...PHOTO_STATUS[s]) : s);

async function loadPhotos() {
  state.photos = await api("/api/photos");
  const names = new Set(state.photos.map((p) => p.name));
  state.photoSelected = new Set([...state.photoSelected].filter((n) => names.has(n)));
  if (state.tab === "photos") renderPhotos();
}

function renderPhotos() {
  const all = state.photos;
  const count = (st) => all.filter((p) => p.status === st).length;
  const avail = count("available"), used = count("used"), reserved = count("reserved"), rejected = count("rejected");
  $("#photo-stats").innerHTML = [
    kpiTile({ label: L("Fotos in der Bibliothek", "Photos in library"), iconName: "image", tone: "accent", value: fmtNum(all.length),
      foot: L("jedes Foto bekommt nur ein Account", "each one goes to a single account") }),
    kpiTile({ label: L("Frei", "Available"), iconName: "checkCircle", tone: "ok", value: fmtNum(avail),
      foot: avail ? L(`reicht für ${fmtNum(avail)} weitere Account(s)`, `enough for ${fmtNum(avail)} more account${avail === 1 ? "" : "s"}`)
        : `<span class="sr-danger">${L("mehr hochladen, um weiter Accounts zu erstellen", "upload more to keep creating accounts")}</span>` }),
    kpiTile({ label: L("Reserviert", "Reserved"), iconName: "clock", tone: "info", value: fmtNum(reserved),
      foot: L("von Accounts in der Warteschlange gehalten", "held by accounts waiting in the queue") }),
    kpiTile({ label: L("Benutzt", "Used"), iconName: "userCheck", tone: "warn", value: fmtNum(used),
      foot: L("bleibt für den Verlauf des Accounts", "kept for the account's history") }),
    kpiTile({ label: L("Abgelehnt", "Rejected"), iconName: "ban", tone: rejected ? "danger" : "", value: fmtNum(rejected),
      foot: L("von Jaumo abgelehnt — wird nie wieder vergeben", "refused by Jaumo — never given out again") }),
  ].join("");
  $$("#photo-filter button").forEach((b) => {
    const f = b.dataset.filter;
    b.classList.toggle("active", f === state.photoFilter);
    const n = f === "all" ? all.length : count(f);
    b.querySelector(".seg-count").textContent = n;
  });
  const list = state.photoFilter === "all" ? all : all.filter((p) => p.status === state.photoFilter);
  $("#photo-grid").innerHTML = list.length ? list.map(photoCard).join("")
    : emptyState("image", all.length ? L("Keine Fotos in diesem Filter", "No photos in this filter") : L("Die Fotobibliothek ist leer", "Your photo library is empty"),
      all.length ? L("Oben einen anderen Filter wählen.", "Choose another filter above.")
        : L("Fotos, einen Ordner oder eine ZIP-Datei oben ablegen, um zu starten.", "Drop photos, a folder or a ZIP file above to get started."));
  updatePhotoSelection();
}

function photoCard(p) {
  const selectable = p.status === "available";
  const owner = p.account
    ? `<a href="#account/${p.account.id}" class="pc-owner">${icon("user")}${esc(p.account.name)} <span class="muted">#${p.account.id}</span></a>`
    : p.status === "reserved" ? `<span class="pc-owner muted">${icon("clock")}${L("wartet in der Warteschlange", "waiting in queue")}</span>` : "";
  return `<div class="photo-card s-${p.status}${state.photoSelected.has(p.name) ? " selected" : ""}" data-name="${esc(p.name)}">
    <div class="pc-img" data-view="${esc(p.name)}">
      <img src="${thumbUrl(p.name)}" loading="lazy" alt="">
      ${selectable ? `<label class="pc-check" title="${L("Auswählen", "Select")}"><input type="checkbox" data-sel="${esc(p.name)}" ${state.photoSelected.has(p.name) ? "checked" : ""}></label>` : ""}
      <span class="pc-status ${p.status}">${esc(photoStatusText(p.status))}</span>
    </div>
    <div class="pc-body">
      <div class="pc-name" title="${esc(p.original_name || p.name)}">${esc(p.name)}</div>
      <div class="pc-meta">${p.width}×${p.height} · ${fmtNum(Math.round(p.size / 1024))} KB</div>
      ${p.rejected_reason ? `<div class="pc-reason" title="${esc(photoReasonText(p.rejected_reason))}">${icon("ban")}${esc(photoReasonText(p.rejected_reason))}</div>` : ""}
      <div class="pc-foot">${owner || `<span class="pc-owner muted">${icon("checkCircle")}${L("noch nicht benutzt", "not used yet")}</span>`}
        ${p.rejected_reason ? `<button type="button" class="btn small ghost" data-release="${esc(p.name)}" title="${L("Wieder vergeben lassen (z. B. nach Bearbeitung)", "Allow it again (e.g. after editing)")}">${L("Freigeben", "Release")}</button>` : ""}
        ${selectable ? iconBtn("trash", `data-del="${esc(p.name)}"`, L("Foto löschen", "Delete photo"), "danger") : ""}</div>
    </div>
  </div>`;
}

function updatePhotoSelection() {
  const n = state.photoSelected.size;
  $("#photo-selected").textContent = n ? L(`${n} ausgewählt`, `${n} selected`) : "";
  $("#photo-bulk-delete").disabled = !n;
  if ($("#photo-add-text")) $("#photo-add-text").disabled = !n;
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
    if (!confirm(L(`${del.dataset.del} löschen?`, `Delete ${del.dataset.del}?`))) return;
    await api(`/api/photos/${encodeURIComponent(del.dataset.del)}`, { method: "DELETE" });
    state.photoSelected.delete(del.dataset.del);
    toast(L("Foto gelöscht", "Photo deleted"));
    return loadPhotos();
  }
  const release = e.target.closest("[data-release]");
  if (release) {
    if (!confirm(L("Dieses von Jaumo abgelehnte Foto wieder vergeben lassen?", "Allow this photo again although Jaumo refused it?"))) return;
    await api(`/api/photos/${encodeURIComponent(release.dataset.release)}/release`, { method: "POST" });
    toast(L("Foto freigegeben", "Photo released"));
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
  if (!names.length || !confirm(L(`${names.length} Foto(s) löschen? Das kann nicht rückgängig gemacht werden.`, `Delete ${names.length} photo(s)? This cannot be undone.`))) return;
  const res = await api("/api/photos/bulk-delete", { method: "POST", body: { names } });
  state.photoSelected.clear();
  toast(L(`${res.deleted.length} Foto(s) gelöscht${res.blocked.length ? ` · ${res.blocked.length} behalten (in Benutzung)` : ""}`,
          `Deleted ${res.deleted.length} photo(s)${res.blocked.length ? ` · ${res.blocked.length} kept (in use)` : ""}`));
  await loadPhotos();
});

function openPhotoViewer(name) {
  const p = state.photos.find((x) => x.name === name);
  if (!p) return;
  openModal(p.name, `<div class="viewer">
      <img src="/api/photos/${encodeURIComponent(p.name)}/file" alt="">
      <dl class="kv">
        <dt>Status</dt><dd><span class="badge ${p.status === "rejected" ? "bad" : ""}">${esc(photoStatusText(p.status))}</span></dd>
        ${p.rejected_reason ? `<dt>${L("Grund", "Reason")}</dt><dd class="sr-danger">${esc(photoReasonText(p.rejected_reason))} · ${fmtDate(p.rejected_at)}</dd>` : ""}
        <dt>${L("Größe", "Size")}</dt><dd>${p.width}×${p.height} · ${fmtNum(Math.round(p.size / 1024))} KB</dd>
        <dt>${L("Hochgeladen", "Uploaded")}</dt><dd>${fmtDate(p.created_at)}</dd>
        <dt>${L("Original", "Original")}</dt><dd>${esc(p.original_name)}</dd>
        <dt>Account</dt><dd>${p.account ? `<a href="#account/${p.account.id}" data-close>${esc(p.account.name)} #${p.account.id}</a> ${badge(p.account.status)}` : "—"}</dd>
      </dl>
      ${p.status !== "used" ? `<button class="btn small" id="pv-text">${icon("pencil")}${L("Text hinzufügen", "Add text")}</button>` : ""}</div>`);
  if ($("#pv-text")) $("#pv-text").onclick = () => { closeModal(); openPhotoText([p.name]); };
  $("#modal-body [data-close]")?.addEventListener("click", closeModal);
}

// --- Add text onto photos (caption overlay, WYSIWYG via canvas) ---------------------------------
// The preview and the saved image are the SAME canvas, so what you see is exactly what gets saved.
const POSITIONS = [["tl", "↖"], ["tc", "↑"], ["tr", "↗"], ["ml", "←"], ["mc", "●"], ["mr", "→"],
                   ["bl", "↙"], ["bc", "↓"], ["br", "↘"]];
const MAX_TEXT_LINES = 6;
// a new text line starts at the first free spot of these, so it does not land on top of the previous one
const NEW_LINE_SPOTS = ["mc", "tc", "bc", "ml", "mr", "tl", "tr", "bl", "br"];

function newTextLine(used) {
  const pos = NEW_LINE_SPOTS.find((s) => !used.includes(s)) || "mc";
  return { text: "", sizePct: 7, pos, color: "#ffffff", bold: true, outline: true, outlineColor: "#000000" };
}

// Draw every text line onto the photo. One line can have several rows (Enter); they are stacked at its anchor.
function drawCaption(canvas, img, lines) {
  const W = img.naturalWidth, H = img.naturalHeight;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, W, H);
  for (const o of lines) {
    const rows = String(o.text || "").split("\n").map((r) => r.trim()).filter(Boolean);
    if (!rows.length) continue;
    const m = Math.round(H * 0.04);
    const setFont = (px) => { ctx.font = `${o.bold ? "700" : "500"} ${px}px Inter, Arial, sans-serif`; };
    let size = Math.round((o.sizePct / 100) * H);
    setFont(size);
    // the size is a maximum: a long text shrinks (all rows of the line together) until it fits the photo width
    const widest = Math.max(...rows.map((r) => ctx.measureText(r).width));
    const room = W - 2 * m - (o.outline ? size * 0.14 : 0);
    if (widest > room) { size = Math.max(8, Math.floor((size * room) / widest)); setFont(size); }
    const lead = Math.round(size * 1.2);
    ctx.textAlign = o.pos[1] === "l" ? "left" : o.pos[1] === "r" ? "right" : "center";
    ctx.textBaseline = "middle";
    const x = o.pos[1] === "l" ? m : o.pos[1] === "r" ? W - m : W / 2;
    const block = lead * rows.length;
    const top = o.pos[0] === "t" ? m : o.pos[0] === "b" ? H - m - block : (H - block) / 2;
    rows.forEach((row, n) => {
      const y = top + lead * n + lead / 2;
      if (o.outline) {
        ctx.lineJoin = "round";
        ctx.lineWidth = Math.max(2, size * 0.14);
        ctx.strokeStyle = o.outlineColor;
        ctx.strokeText(row, x, y);
      }
      ctx.fillStyle = o.color;
      ctx.fillText(row, x, y);
    });
  }
}

function canvasToBlob(canvas) {
  return new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.92));
}

async function openPhotoText(names) {
  names = names.filter((n) => {
    const p = state.photos.find((x) => x.name === n);
    return p && p.status !== "used";   // a photo already on an account is kept for its history
  });
  if (!names.length) return toast(L("Keine bearbeitbaren Fotos ausgewählt (benutzte Fotos bleiben unverändert).",
                                    "No editable photos selected (used photos are kept)."), true);
  const lines = [newTextLine([])];
  let cur = 0;
  openModal(L("Text auf Fotos", "Add text to photos"), `
    <div class="txt-editor">
      <div class="txt-preview"><canvas id="txt-canvas"></canvas>
        <div class="txt-nav">${names.length > 1 ? `<button class="btn ghost sm" id="txt-prev">${icon("chevronLeft")}</button>
          <span id="txt-count" class="muted"></span>
          <button class="btn ghost sm" id="txt-next">${icon("chevronRight")}</button>` : ""}</div></div>
      <div class="txt-controls">
        <div><div class="lbl">${L("Textzeilen", "Text lines")}</div><div class="txt-lines" id="txt-lines"></div></div>
        <label>${L("Text (Enter = neue Reihe)", "Text (Enter = new row)")}
          <textarea id="txt-text" rows="2" placeholder="${L("z. B. @SofiheyTelegram", "e.g. @SofiheyTelegram")}"></textarea></label>
        <div class="txt-row">
          <label>${L("Größe", "Size")}<input type="range" id="txt-size" min="3" max="18" value="7"></label>
          <label class="txt-check"><input type="checkbox" id="txt-bold" checked> ${L("Fett", "Bold")}</label>
        </div>
        <div class="txt-row">
          <label>${L("Farbe", "Colour")}<input type="color" id="txt-color" value="#ffffff"></label>
          <label class="txt-check"><input type="checkbox" id="txt-outline" checked> ${L("Umrandung", "Outline")}</label>
          <label>${L("Umrandungsfarbe", "Outline colour")}<input type="color" id="txt-ocolor" value="#000000"></label>
        </div>
        <div><div class="lbl">${L("Position dieser Zeile", "Position of this line")}</div>
          <div class="txt-grid" id="txt-grid">${POSITIONS.map(([k, s]) => `<button type="button" data-pos="${k}">${s}</button>`).join("")}</div></div>
        <p class="field-hint">${L(`Wird auf ${names.length} ausgewählte(s) Foto(s) angewendet und überschreibt sie.`,
                                 `Applied to ${names.length} selected photo(s), overwriting them.`)}</p>
        <p class="error" id="txt-error"></p>
        <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
          <button class="btn primary" id="txt-apply">${icon("check")}${L("Anwenden", "Apply")}</button></div>
      </div>
    </div>`);

  const canvas = $("#txt-canvas");
  const imgs = {};
  let idx = 0;
  const loadImg = (name) => new Promise((res) => {
    if (imgs[name]) return res(imgs[name]);
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => { imgs[name] = im; res(im); };
    im.onerror = () => res(null);
    im.src = `/api/photos/${encodeURIComponent(name)}/file`;
  });
  const render = async () => {
    if ($("#txt-count")) $("#txt-count").textContent = `${idx + 1} / ${names.length}`;   // at once, not after the load
    const shown = idx;
    const im = await loadImg(names[shown]);
    if (im && shown === idx) drawCaption(canvas, im, lines);   // ignore a late image if the user already moved on
  };
  // controls <-> the selected text line
  const fill = () => {
    const o = lines[cur];
    $("#txt-text").value = o.text;
    $("#txt-size").value = o.sizePct;
    $("#txt-bold").checked = o.bold;
    $("#txt-color").value = o.color;
    $("#txt-outline").checked = o.outline;
    $("#txt-ocolor").value = o.outlineColor;
    $$("#txt-grid button").forEach((b) => b.classList.toggle("on", b.dataset.pos === o.pos));
  };
  const read = () => {
    const o = lines[cur];
    o.text = $("#txt-text").value;
    o.sizePct = +$("#txt-size").value;
    o.bold = $("#txt-bold").checked;
    o.color = $("#txt-color").value;
    o.outline = $("#txt-outline").checked;
    o.outlineColor = $("#txt-ocolor").value;
  };
  const renderLines = () => {
    $("#txt-lines").innerHTML = lines.map((o, n) => {
      const label = (o.text.trim().split("\n")[0] || "").slice(0, 14);
      return `<button type="button" class="txt-line${n === cur ? " on" : ""}" data-line="${n}">${n + 1}${label ? ` · ${esc(label)}` : ""}</button>`;
    }).join("") + (lines.length < MAX_TEXT_LINES
      ? `<button type="button" class="txt-line add" id="txt-add" title="${L("Weitere Textzeile", "Another text line")}">${icon("plus")}</button>` : "")
      + (lines.length > 1 ? `<button type="button" class="txt-line del" id="txt-del" title="${L("Diese Zeile entfernen", "Remove this line")}">${icon("trash")}</button>` : "");
  };
  const refresh = () => { renderLines(); fill(); render(); };

  $("#txt-text").oninput = $("#txt-size").oninput = () => { read(); renderLines(); render(); };
  ["txt-bold", "txt-color", "txt-outline", "txt-ocolor"].forEach((id) => { $(`#${id}`).onchange = () => { read(); render(); }; });
  $("#txt-grid").onclick = (e) => {
    const b = e.target.closest("[data-pos]");
    if (!b) return;
    lines[cur].pos = b.dataset.pos;
    $$("#txt-grid button").forEach((x) => x.classList.toggle("on", x === b));
    render();
  };
  $("#txt-lines").onclick = (e) => {
    if (e.target.closest("#txt-add")) {
      read();
      lines.push(newTextLine(lines.map((l) => l.pos)));
      cur = lines.length - 1;
      return refresh();
    }
    if (e.target.closest("#txt-del")) {
      lines.splice(cur, 1);
      cur = Math.min(cur, lines.length - 1);
      return refresh();
    }
    const b = e.target.closest("[data-line]");
    if (b) { read(); cur = +b.dataset.line; refresh(); }
  };
  if ($("#txt-prev")) $("#txt-prev").onclick = () => { idx = (idx - 1 + names.length) % names.length; render(); };
  if ($("#txt-next")) $("#txt-next").onclick = () => { idx = (idx + 1) % names.length; render(); };
  refresh();

  $("#txt-apply").onclick = guard(async () => {
    read();
    if (!lines.some((o) => o.text.trim())) { $("#txt-error").textContent = L("Bitte einen Text eingeben.", "Please enter some text."); return; }
    const btn = $("#txt-apply");
    btn.disabled = true;
    let done = 0;
    const fails = [];
    for (const name of names) {
      const im = await loadImg(name);
      if (!im) { fails.push(`${name}: load`); continue; }
      drawCaption(canvas, im, lines);
      const blob = await canvasToBlob(canvas);
      const fd = new FormData();
      fd.append("file", blob, name);
      try {
        await api(`/api/photos/${encodeURIComponent(name)}/overwrite`, { method: "POST", body: fd });
        done++;
      } catch (err) { fails.push(`${name}: ${err.message}`); }
    }
    closeModal();
    toast(L(`${done} Foto(s) mit Text gespeichert${fails.length ? ` · ${fails.length} fehlgeschlagen` : ""}`,
            `${done} photo(s) saved with text${fails.length ? ` · ${fails.length} failed` : ""}`), fails.length && !done);
    state.photoSelected.clear();
    await loadPhotos();
  });
}
$("#photo-add-text").onclick = guard(() => openPhotoText([...state.photoSelected]));

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
      if (xhr.status === 401) { showLogin(); return reject(new Error(L("Nicht angemeldet", "Not authenticated"))); }
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      xhr.status < 400 ? resolve(data) : reject(new Error(data.detail || L(`Upload fehlgeschlagen (HTTP ${xhr.status})`, `Upload failed (HTTP ${xhr.status})`)));
    };
    xhr.onerror = () => reject(new Error(L("Netzwerkfehler beim Hochladen", "Network error during upload")));
    xhr.send(fd);
  });
}

let uploading = false;
async function uploadPhotos(fileList) {
  const files = [...fileList].filter((f) => PHOTO_EXTS.test(f.name));
  const skipped = fileList.length - files.length;
  if (!files.length) return toast(L("In der Auswahl sind keine Bilder oder ZIP-Dateien", "No images or ZIP files found in that selection"), true);
  if (uploading) return toast(L("Es läuft bereits ein Upload — bitte warten", "An upload is already running — wait for it to finish"), true);
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
          <span>${fmtNum(files.length)} ${L("Datei(en)", files.length === 1 ? "file" : "files")} · ${(totalBytes / 1048576).toFixed(1)} MB${skipped ? L(` · ${skipped} Nicht-Bild-Datei(en) ignoriert`, ` · ${skipped} non-image file(s) ignored`) : ""}</span></div>
        <div class="up-counts"><span class="sr-ok">${icon("checkCircle")}${totals.saved} ${L("hinzugefügt", "added")}</span>
          <span class="muted">${icon("copy")}${totals.duplicate} ${L("Duplikate", "duplicates")}</span>
          <span class="sr-danger">${icon("alert")}${totals.error} ${L("fehlgeschlagen", "failed")}</span></div>
      </div>
      <div class="meter up-bar"><span style="width:${pctDone}%"></span></div>
      ${problems.length ? `<details class="up-problems"${totals.error ? " open" : ""}><summary>${L(`${problems.length} Datei(en) nicht hinzugefügt`, `${problems.length} file(s) not added`)}</summary>
        <ul>${problems.map((r) => `<li><span class="badge ${r.status === "duplicate" ? "" : "bad"}">${r.status}</span>
          <span class="mono">${esc(r.name)}</span> <span class="muted">— ${esc(r.detail)}</span></li>`).join("")}</ul></details>` : ""}`;
  };
  try {
    const batches = batchFiles(files);
    for (let i = 0; i < batches.length; i++) {
      const b = batches[i];
      const bBytes = b.reduce((a, f) => a + f.size, 0);
      const label = b.length === 1 && /\.zip$/i.test(b[0].name) ? L(`${b[0].name} wird entpackt …`, `Unpacking ${b[0].name}…`)
        : L(`Teil ${i + 1} von ${batches.length} wird hochgeladen …`, `Uploading batch ${i + 1} of ${batches.length}…`);
      render(label, Math.round((doneBytes / totalBytes) * 100));
      const res = await postWithProgress(b, (loaded) => render(label, Math.min(99, Math.round(((doneBytes + loaded) / totalBytes) * 100))));
      doneBytes += bBytes;
      for (const k of Object.keys(totals)) totals[k] += res[k] || 0;
      problems.push(...(res.results || []).filter((r) => r.status !== "saved"));
      render(label, Math.round((doneBytes / totalBytes) * 100));
    }
    render(L(`Fertig — ${totals.saved} Foto(s) hinzugefügt`, `Done — ${totals.saved} photo${totals.saved === 1 ? "" : "s"} added`), 100);
    toast(L(`${totals.saved} hinzugefügt · ${totals.duplicate} Duplikate übersprungen · ${totals.error} fehlgeschlagen`,
            `${totals.saved} added · ${totals.duplicate} duplicates skipped · ${totals.error} failed`), totals.saved === 0 && totals.error > 0);
  } catch (e) {
    render(L(`Upload abgebrochen: ${e.message}`, `Upload stopped: ${e.message}`), Math.round((doneBytes / totalBytes) * 100));
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

const ACC_STATUSES = ["active", "blocked", "verification_required", "limit_reached", "photo_failed", "failed", "stopped", "signing_up", "legacy"];
const SORTS = {
  newest: ["id", "desc"], activity: ["last_activity_at", "desc"], likes: ["liked_count", "desc"],
  matches: ["matches_count", "desc"], oldest: ["id", "asc"],
};
const STATE_STYLE = {
  active: { cls: "ok", icon: "checkCircle" }, working: { cls: "working", icon: "refresh" },
  queued: { cls: "queued", icon: "clock" },
  blocked: { cls: "bad", icon: "ban" }, error: { cls: "warn", icon: "alert" }, stopped: { cls: "", icon: "pause" },
  verification: { cls: "verify", icon: "shieldCheck" },
  limit: { cls: "limit", icon: "clock" },
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

// Session reasons come from the server in English; show them in German when the panel is German.
const DIALOG_DE = { rate_app: "Bewertungs-Dialog", vip: "Premium-Dialog", dialog: "Dialog" };
const REASON_DE = [
  [/^max swipes reached \((\d+)\)$/, (m) => `Max. Swipes erreicht (${m[1]})`],
  [/^no more cards$/, () => "Keine Karten mehr"],
  [/^no more profiles/, () => "Keine Profile mehr in der Nähe"],
  [/^Jaumo lock: cards locked for (\d+) s \((.+)\)$/, (m) => `Jaumo-Sperre ${m[1]} s (${DIALOG_DE[m[2]] || m[2]})`],
  [/^Jaumo lock: cards locked \((.+)\)$/, (m) => `Jaumo-Sperre (${DIALOG_DE[m[1]] || m[1]})`],
  [/^Jaumo pause repeated (\d+) times without new cards \((.+)\)$/,
    (m) => `Jaumo-Pause ${m[1]}× hintereinander ohne neue Karten (${DIALOG_DE[m[2]] || m[2]})`],
  [/^swipe limit reached(.*)$/, (m) => `Jaumo-Sperre${m[1].replace("unlock expires in", "endet in")}`],
  [/^renamed to (.+)$/, (m) => `Umbenannt in ${m[1]}`],
  [/^name not accepted \(HTTP (\d+)\)$/, (m) => `Name von Jaumo nicht akzeptiert (HTTP ${m[1]})`],
  [/^Verification required ?(— )?/i, (m) => m.input.replace(/^Verification required ?(— )?/i, "").trim() || "Verifizierung nötig"],
  [/^stopped by admin$/, () => "Vom Admin gestoppt"],
  [/^stopped before start$/, () => "Aus der Warteschlange entfernt"],
  [/^stopped while waiting for proxy$/, () => "Beim Warten auf einen Proxy gestoppt"],
  [/^(like|dislike) HTTP (\d+)$/, (m) => `${m[1] === "like" ? "Like" : "Dislike"} abgelehnt (HTTP ${m[2]})`],
  [/^zapping HTTP (\d+)$/, (m) => `Karten nicht abrufbar (HTTP ${m[1]})`],
  [/^consecutive failures$/, () => "Mehrere Fehler hintereinander"],
  [/^photo rejected: (.+)$/, (m) => `Foto abgelehnt: ${photoReasonText(m[1])}`],
  [/^photo failed: (.+)$/, (m) => `Foto-Problem: ${photoReasonText(m[1])}`],
  [/^photo upload not accepted$/, () => "Foto von Jaumo nicht akzeptiert"],
  [/^photo not registered by server$/, () => "Foto von Jaumo nicht übernommen"],
  [/^network error: (.+)$/, (m) => `Netzwerkfehler (${m[1]})`],
  [/^interrupted/, () => "Durch Server-Neustart unterbrochen"],
  [/^([A-Z]\w+Error): (.+)$/, (m) => `Absturz: ${m[1]}: ${m[2]}`],
];
function reasonText(reason) {
  if (!reason || LANG !== "de") return reason || "";
  for (const [re, fmt] of REASON_DE) { const m = re.exec(reason); if (m) return fmt(m); }
  return serverText(reason);
}

// Why a photo failed (engine reasons) — German when the panel is German.
const PHOTO_REASON_DE = [
  [/^upload refused \(HTTP (\d+)\):? ?(.*)$/, (m) => `Upload abgelehnt (HTTP ${m[1]})${m[2] ? ": " + m[2] : ""}`],
  [/^confirmation refused \(HTTP (\d+)\):? ?(.*)$/, (m) => `Bestätigung abgelehnt (HTTP ${m[1]})${m[2] ? ": " + m[2] : ""}`],
  [/^profile photo refused \(HTTP (\d+)\):? ?(.*)$/, (m) => `Profilfoto abgelehnt (HTTP ${m[1]})${m[2] ? ": " + m[2] : ""}`],
  [/^Jaumo warning: (.*)$/, (m) => `Jaumo-Warnung: ${m[1]}`],
  [/^not in the gallery after upload \((.*)\)$/, (m) => `nach dem Upload nicht in der Galerie (${m[1]})`],
  [/^Jaumo did not make it the profile photo$/, () => "Jaumo hat es nicht als Profilfoto übernommen"],
  [/^rejected by Jaumo$/, () => "von Jaumo abgelehnt"],
  [/^file not found$/, () => "Datei nicht gefunden"],
  [/^image file is empty$/, () => "Bilddatei ist leer"],
  [/^Jaumo gave no (upload|gallery|profile-photo) link$/,
    (m) => `Jaumo lieferte keinen ${{ upload: "Upload", gallery: "Galerie", "profile-photo": "Profilfoto" }[m[1]]}-Link`],
  [/^(upload|confirmation) answer (was not readable|had no image URL|was not a photo)$/, (m) =>
    `${m[1] === "upload" ? "Upload" : "Bestätigung"}: Antwort ${m[2] === "had no image URL" ? "ohne Bild-URL" : "nicht lesbar"}`],
];
function photoReasonText(r) {
  if (!r || LANG !== "de") return r || "";
  for (const [re, fmt] of PHOTO_REASON_DE) { const m = re.exec(r); if (m) return fmt(m); }
  return r;
}

// Common messages from the server (errors, skip reasons, start check) — German when the panel is German.
const NOUN_DE = { photos: "Fotos", names: "Namen", "profile texts": "Profiltexte", "new nicknames": "neue Nicknamen" };
const SERVER_DE = [
  [/^already working$/, () => "arbeitet bereits"],
  [/^blocked by Jaumo$/, () => "von Jaumo gesperrt"],
  [/^account was never fully set up/, () => "Account wurde nie vollständig eingerichtet"],
  [/^no login token stored$/, () => "kein Login gespeichert"],
  [/^a refresh for this account is already queued or running$/, () => "für diesen Account läuft schon eine Aktualisierung"],
  [/^account is working — /, () => "Account arbeitet — die Sitzung liest ihre Stats selbst"],
  [/^refreshed a moment ago — wait (\d+)s$/, (m) => `gerade aktualisiert — noch ${m[1]} s warten`],
  [/^refreshed recently$/, () => "kürzlich aktualisiert"],
  [/^nothing is running or queued for this account$/, () => "für diesen Account läuft und wartet nichts"],
  [/^Not enough unused (photos|names|profile texts|new nicknames): only (\d+) of (\d+)/,
    (m) => `Nicht genug freie ${NOUN_DE[m[1]]}: nur ${m[2]} von ${m[3]} verfügbar.`],
  [/^No photos in the library/, () => "Keine Fotos in der Bibliothek — zuerst Fotos hochladen (Seite Fotos)"],
  [/^The name list is empty/, () => "Die Namensliste ist leer — Namen eintragen oder automatische Namen wählen"],
  [/^The profile text list is empty/, () => "Die Profiltext-Liste ist leer — Texte eintragen oder Profiltexte ausschalten"],
  [/^The list of new nicknames is empty/, () => "Die Liste der neuen Nicknamen ist leer — Namen auf der Seite „Nicknamen ändern“ eintragen"],
  [/^Names must be unique \(Settings\) — (.*)$/, (m) => `Namen müssen eindeutig sein — ${m[1]
    .replace("already used", "bereits vergeben").replace("typed more than once", "doppelt eingegeben")}`],
  [/^Messaging is turned off/, () => t("msg.off")],
  [/^Invalid username or password$/, () => "Benutzername oder Passwort falsch"],
  [/^config has no APK profile/, () => "Keine APK-Schlüssel hinterlegt (Konfiguration)"],
  [/^APK profile '.+' is disabled/, () => "Die APK-Schlüssel sind deaktiviert"],
  [/^No enabled proxy/, () => "Kein aktiver Proxy — die Konfiguration verlangt einen (Seite Proxies)"],
  [/^no enabled proxies/, () => "Kein aktiver Proxy (die Konfiguration verlangt einen)"],
  [/^photo is used by an account/, () => "Das Foto gehört zu einem Account und bleibt für dessen Verlauf"],
  [/^run is not active$/, () => "Die Sitzung läuft nicht"],
  [/^Not found: (.+) — if the panel was just updated, restart the server$/, (m) => `Nicht gefunden: ${m[1]} — nach einem Update den Server neu starten`],
  [/^name already exists$/, () => "Name existiert bereits"],
  [/^(.+): not accepted \(HTTP (\d+)\)$/, (m) => `${m[1]}: nicht akzeptiert (HTTP ${m[2]})`],
  [/^not set \(HTTP (\S+)\)$/, (m) => `nicht gesetzt (HTTP ${m[1]})`],
  [/^could not read counters \(HTTP (\S+)\)$/, (m) => `Zähler nicht lesbar (HTTP ${m[1]})`],
  [/^no usable (login )?token$/, () => "kein gültiger Login"],
];
function serverText(msg) {
  if (!msg || LANG !== "de") return msg || "";
  for (const [re, fmt] of SERVER_DE) { const m = re.exec(msg); if (m) return fmt(m); }
  return photoReasonText(msg);
}
const RESULT_TONE = { done: "", stopped: "", blocked: "bad", failed: "warn", interrupted: "warn",
  verification_required: "warn", limit_reached: "" };

// "Fertig: Max. Swipes erreicht (100)" under the status badge (nothing while the account works).
function resultLine(a, cls = "state-reason") {
  const r = a.last_result;
  if (a.working || !r) return "";
  const text = `${t("res." + r.status)}: ${reasonText(r.reason) || "—"}`;
  return `<div class="${cls} ${RESULT_TONE[r.status] || ""}" title="${esc(text)}${r.finished_at ? " · " + esc(fmtDate(r.finished_at)) : ""}">${esc(text)}</div>`;
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
    <td>${stateBadge(a.active_run && a.active_run.status === "queued" ? "queued" : a.state)}${resultLine(a)}</td>
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
  $("#acc-pages").innerHTML = `<button class="pg" data-pg="${a.page - 1}" ${a.page <= 0 ? "disabled" : ""} aria-label="${L("Zurück", "Previous")}">${icon("chevronLeft")}</button>
    ${nums.map((n) => n === "…" ? `<span class="pg-gap">…</span>`
      : `<button class="pg${n === a.page ? " active" : ""}" data-pg="${n}">${n + 1}</button>`).join("")}
    <button class="pg" data-pg="${a.page + 1}" ${a.page + 1 >= pages ? "disabled" : ""} aria-label="${L("Weiter", "Next")}">${icon("chevronRight")}</button>`;
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

// Accounts that were set up and are not working / blocked can continue swiping.
// An account that is set up (has a login) can be retried — also after a block or a verification wall,
// because a daily like-limit clears and a verification done in the app lets it swipe again.
const RETRYABLE = ["active", "legacy", "stopped", "blocked", "verification_required", "limit_reached"];
function canSwipe(a) {
  return !a.working && a.has_token !== false && RETRYABLE.includes(a.status);
}

async function stopAccounts(ids) {
  if (ids.length > 1 && !confirm(t("acc.stopConfirm", { n: ids.length }))) return;
  const res = await api("/api/accounts/stop", { method: "POST", body: { account_ids: ids } });
  toast(t("acc.stopped", { n: res.stopped }), !res.stopped);
  guard(loadStats)();
  if (state.tab === "accounts") reloadAccountsSoon();
  if (state.tab === "account") refreshAccountSoon();
}

async function startRename(ids) {
  if (ids.length > 1 && !confirm(t("rename.confirm", { n: ids.length }))) return;
  const res = await api("/api/accounts/rename", { method: "POST", body: { account_ids: ids } });
  if (res.run_ids.length) toast(t("rename.started", { n: res.run_ids.length }));
  if (res.skipped.length) {
    const why = [...new Set(res.skipped.map((x) => serverText(x.reason)))].join(", ");
    toast(t("rename.skipped", { n: res.skipped.length, r: why }), !res.run_ids.length);
  }
  if (state.tab === "accounts") reloadAccountsSoon();
  if (state.tab === "account") refreshAccountSoon();
}

async function startSwiping(ids) {
  const res = await api("/api/accounts/swipe", { method: "POST", body: { account_ids: ids } });
  if (res.run_ids.length) toast(t("swipe.started", { n: res.run_ids.length }));
  if (res.skipped.length) {
    const why = [...new Set(res.skipped.map((x) => serverText(x.reason)))].join(", ");
    toast(t("swipe.skipped", { n: res.skipped.length, r: why }), !res.run_ids.length);
  }
  guard(loadStats)();
  if (state.tab === "accounts") reloadAccountsSoon();
  if (state.tab === "account") refreshAccountSoon();
}

function openAccountMenu(btn, id) {
  $$(".menu").forEach((m) => m.remove());
  const a = state.acc.items.find((x) => x.id === id);
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.innerHTML = `
    ${a.active_run ? `<button data-act="stop" class="danger">${icon("stop")}${esc(t(a.active_run.status === "queued" ? "acc.dequeue" : "acc.stop"))}</button><hr>` : ""}
    <button data-act="rename" ${canSwipe(a) ? "" : "disabled"}>${icon("pencil")}${esc(t("rename.btn"))}</button>
    <button data-act="swipe" ${canSwipe(a) ? "" : "disabled"} title="${esc(t("swipe.tip"))}">${icon("play")}${esc(t("swipe.btn"))}</button>
    <button data-act="sync" ${a.has_token === false ? "disabled" : ""}>${icon("refresh")}${esc(t("sync.refresh"))}</button>
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
    if (act === "stop") return stopAccounts([id]);
    if (act === "swipe") return startSwiping([id]);
    if (act === "rename") return startRename([id]);
    if (act === "sync") {
      await api(`/api/accounts/${id}/sync`, { method: "POST" });
      toast(t("sync.started", { n: 1 }));
      return reloadAccountsSoon();
    }
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
  if (!state.config || !state.config.settings.messaging_enabled) {
    openModal(t("msg.title"), `<div class="narrow-form">
        <p>${esc(t("msg.off"))}</p>
        <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
          <a class="btn primary" href="#configs" data-close-modal>${icon("settings")}${esc(t("nav.config"))}</a></div></div>`);
    return;
  }
  openModal(t("msg.title"), `<form id="msg-form" class="narrow-form">
      <p class="muted">${ids.length ? esc(t("bulk.selected", { n: ids.length })) : ""}</p>
      <p>${esc(t("msg.confirm"))}</p>
      <div class="modal-foot"><button type="button" class="btn ghost" data-close-modal>${esc(t("common.cancel"))}</button>
        <button class="btn primary">${icon("send")}${esc(t("msg.start"))}</button></div></form>`);
  $("#msg-form").addEventListener("submit", guard(async (e) => {
    e.preventDefault();
    const res = await api("/api/messages", { method: "POST", body: { account_ids: ids } });
    closeModal();
    toast(res.run_ids.length ? `${res.run_ids.length} ✓` : L("Keine passenden Accounts (offene Matches und Login nötig)", "No eligible accounts (need pending matches and a login token)"), !res.run_ids.length);
  }));
}

$("#bulk-message").onclick = () => openMessageDialog([...state.accSelected]);
$("#bulk-swipe").onclick = guard(() => startSwiping([...state.accSelected]));
$("#bulk-rename").onclick = guard(() => startRename([...state.accSelected]));
$("#bulk-stop").onclick = guard(() => stopAccounts([...state.accSelected]));
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
      const why = [...new Set(res.skipped.map((x) => serverText(x.reason)))].join("; ");
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
  openModal(t("new.title"), `<form id="new-acc-form" class="narrow-form">
      <p class="muted">${esc(stats.running || stats.queued ? t("new.busy", { w: stats.running, q: stats.queued }) : t("new.idle"))}</p>
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
    renderLaunchInfo();
    $("#new-config-info").innerHTML = $("#launch-config-info").innerHTML;
  };
  // Ask the server whether this start would be refused, so the reason is shown here instead of a toast.
  let checkSeq = 0;
  const check = async () => {
    const seq = ++checkSeq, f = form.elements;
    let res;
    try {
      res = await api("/api/runs/check", { method: "POST",
        body: { count: Math.min(500, Math.max(1, +f.count.value || 1)), names: lines(f.names.value) } });
    } catch { return; }
    if (seq !== checkSeq || !$("#new-problems")) return;
    const box = $("#new-problems");
    box.classList.toggle("hidden", res.ok);
    $("#new-submit").disabled = !res.ok;
    box.innerHTML = res.ok ? "" : `<b>${icon("alert")}${esc(t("new.blocked"))}</b><ul>${res.problems.map((p) =>
      `<li><span>${esc(t("new.p." + p.code))} <small>${esc(serverText(p.message))}</small></span>
        <a href="#${p.page}" data-close-modal class="btn ghost sm">${esc(t("new.fix"))}</a></li>`).join("")}</ul>`;
  };
  const checkSoon = throttle(check, 400);
  showInfo();
  check();
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
    const res = await api("/api/runs", { method: "POST", body: { count: +f.count.value, names: lines(f.names.value) } });
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
  created: { icon: "userPlus", tone: "accent", text: () => L("Account erstellt", "Account created") },
  status: { icon: "activity", tone: "info", text: () => L("Status geändert", "Status changed") },
  like: { icon: "thumbsUp", tone: "info", text: (e) => L(`User ${e.user_id} geliked`, `Liked user ${e.user_id}`) },
  match: { icon: "heart", tone: "danger", text: (e) => L(`User ${e.user_id} geliked — Match!`, `Liked user ${e.user_id} — it's a match!`) },
  dislike: { icon: "thumbsDown", tone: "neutral", text: (e) => L(`User ${e.user_id} abgelehnt`, `Disliked user ${e.user_id}`) },
  message: { icon: "message", tone: "ok", text: (e) => L(`User ${e.user_id} angeschrieben`, `Messaged user ${e.user_id}`) },
  message_failed: { icon: "alert", tone: "danger", text: (e) => L(`Nachricht an ${e.user_id} fehlgeschlagen`, `Message to ${e.user_id} failed`) },
  sync: { icon: "refresh", tone: "info", text: () => L("Stats von Jaumo gelesen", "Stats read from Jaumo") },
  renamed: { icon: "pencil", tone: "accent", text: () => L("Nickname geändert", "Nickname changed") },
  photo_rejected: { icon: "ban", tone: "danger", text: () => L("Foto von Jaumo abgelehnt", "Photo rejected by Jaumo") },
  photo_failed: { icon: "alert", tone: "warn", text: () => L("Foto-Schritt fehlgeschlagen", "Photo step failed") },
  verification: { icon: "shieldCheck", tone: "warn", text: () => L("Jaumo verlangt Verifizierung", "Jaumo requires verification") },
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
  $("#account-page").innerHTML = `<div class="empty">${icon("clock")}<b>${L("Account wird geladen …", "Loading account…")}</b></div>`;
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
    <a href="#accounts" class="back-link">${icon("chevronLeft")}${L("Alle Accounts", "All accounts")}</a>
    <div id="acc-hero"></div>
    <div id="acc-sync-bar" class="sync-bar"></div>
    <div id="acc-kpis" class="kpi-grid eight"></div>
    <div id="acc-live"></div>
    <div class="grid-12">
      <div class="card span-7">
        <div class="card-head"><div><h2>${L("Aktivität", "Activity")}</h2><p class="card-sub">${L("Jeder Like, Match, jede Nachricht und Statusänderung — live", "Every like, match, message and status change — updates live")}</p></div></div>
        <div id="acc-timeline" class="timeline"></div>
        <div class="timeline-more"><button class="btn small" id="acc-more">${L("Ältere Aktivität laden", "Load older activity")}</button></div>
      </div>
      <div class="span-5 stack">
        <div class="card">
          <div class="card-head"><div><h2>${L("Personen", "People")}</h2></div>
            <div class="seg" id="acc-list-tabs">
              <button data-list="matches">Matches <span class="seg-count" id="cnt-matches"></span></button>
              <button data-list="liked">${L("Geliked", "Liked")} <span class="seg-count" id="cnt-liked"></span></button>
              <button data-list="disliked">${L("Abgelehnt", "Disliked")} <span class="seg-count" id="cnt-disliked"></span></button>
            </div></div>
          <div id="acc-people"></div>
        </div>
        <div class="card">
          <div class="card-head"><div><h2>${L("Profil &amp; Gerät", "Profile &amp; device")}</h2></div></div>
          <div id="acc-details"></div>
        </div>
      </div>
    </div>
    <div class="card table-card">
      <div class="card-head padded"><div><h2>${L("Sitzungen", "Sessions")}</h2><p class="card-sub">${L("Alle Sitzungen dieses Accounts", "All sessions of this account")}</p></div></div>
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
  const dev = a.device_info ? `${a.device_info.manufacturer} ${a.device_info.model}` : L("Unbekanntes Gerät", "Unknown device");
  const photoRejected = a.photo && (state.photos || []).some((p) => p.name === a.photo && p.status === "rejected");
  const msgOff = !state.config || !state.config.settings.messaging_enabled;
  $("#acc-hero").innerHTML = `<div class="card acc-hero">
    <div class="acc-photo">${a.photo ? `<img src="${thumbUrl(a.photo)}" alt="" data-full="${esc(a.photo)}">` : icon("user")}</div>
    <div class="acc-main">
      <div class="acc-title"><h1>${esc(a.name)}</h1>${badge(a.status)}
        ${(a.name_history || []).length ? `<span class="acc-formerly" title="${esc(a.name_history.join(" → "))}">${esc(t("rename.formerly", { n: a.name_history.join(", ") }))}</span>` : ""}
        ${run ? `<span class="live-chip on"><span class="pulse"></span>${esc(workerName(run.worker))} ${esc(t("state.working").toLowerCase())}</span>` : ""}</div>
      <div class="acc-sub">Account #${a.id}${a.jaumo_id ? ` · Jaumo ${esc(a.jaumo_id)}` : ""} · ${esc(workerName(a.worker))}${age !== null ? L(` · ${age} Jahre`, ` · ${age} years`) : ""} · ${esc(a.location || "—")} · ${L("erstellt", "joined")} ${fmtDate(a.created_at)}</div>
      ${!run && a.last_result ? `<div class="acc-result">${esc(t("res.last"))} · ${fmtDate(a.last_result.finished_at)}${resultLine(a, "acc-result-text")}</div>` : ""}
      ${a.about_me ? `<p class="acc-about" title="${esc(t("about.label"))}">${icon("fileText")}<span><b>${esc(t("about.textLabel"))}</b> ${esc(a.about_me)}</span></p>`
        : a.about_me_error ? `<p class="acc-about bad">${icon("alert")}<span>${esc(t("about.notSet"))} — ${esc(serverText(a.about_me_error))}</span></p>` : ""}
      ${a.rename_error ? `<p class="acc-about bad">${icon("alert")}<span>${esc(t("rename.notSet"))} — ${esc(serverText(a.rename_error))}</span></p>` : ""}
      ${a.verify_info ? `<p class="acc-about bad" title="${esc(t("verify.sub"))}"><span>${icon("shieldCheck")}</span><span><b>${esc(t("verify.title"))}:</b> ${esc(a.verify_info)}<br><small>${esc(t("verify.sub"))}</small></span></p>` : ""}
      ${a.photo_error ? `<p class="acc-about bad">${icon(photoRejected ? "ban" : "image")}<span><b>${photoRejected ? L("Foto abgelehnt:", "Photo rejected:") : L("Foto-Problem:", "Photo problem:")}</b>
        ${esc(a.photo || "")} — ${esc(photoReasonText(a.photo_error))}</span></p>` : ""}
      <div class="acc-chips">
        <span class="chip">${icon("smartphone")}${esc(dev)}</span>
        ${a.config_id ? "" : `<span class="chip">${icon("archive")}${L("importiert", "legacy import")}</span>`}
        <span class="chip">${icon("globe")}${a.proxy_id ? `Proxy #${a.proxy_id}` : L("kein Proxy", "no proxy")}</span>
        <span class="chip ${a.has_token ? "" : "bad"}">${icon("key")}${a.has_token ? L("Login gespeichert", "login token stored") : L("kein Login gespeichert", "no login token")}</span>
      </div>
    </div>
    <div class="acc-actions">
      ${run ? `<button class="btn danger-soft" id="acc-stop">${icon("stop")}${esc(t(run.status === "queued" ? "acc.dequeue" : "acc.stop"))}</button>` : ""}
      <button class="btn" id="acc-rename" ${canSwipe({ ...a, working: !!run }) ? "" : "disabled"}>${icon("pencil")}${esc(t("rename.btn"))}</button>
      <button class="btn" id="acc-swipe" ${canSwipe({ ...a, working: !!run }) ? "" : "disabled"} title="${esc(t("swipe.tip"))}">${icon("play")}${esc(t("swipe.btn"))}</button>
      ${msgOff ? `<a class="field-hint" href="#configs">${esc(t("msg.off"))}</a>` : ""}
      <button class="btn primary" id="acc-msg" ${a.pending_messages && !msgOff ? "" : "disabled"}>${icon("send")}${L(`${a.pending_messages || ""} offene Matches anschreiben`, `Message ${a.pending_messages || ""} pending`)}</button>
    </div>
  </div>`;
  $("#acc-hero [data-full]")?.addEventListener("click", () => openPhotoViewer(a.photo));
  $("#acc-swipe").onclick = guard(() => startSwiping([a.id]));
  $("#acc-rename").onclick = guard(() => startRename([a.id]));
  if ($("#acc-stop")) $("#acc-stop").onclick = guard(() => stopAccounts([a.id]));
  $("#acc-msg").onclick = guard(async () => {
    const res = await api("/api/messages", { method: "POST", body: { account_ids: [a.id] } });
    toast(res.run_ids.length ? L("Anschreiben eingereiht", "Messaging session queued")
      : L("Nichts zu senden (keine offenen Matches oder es läuft schon eine Sitzung)", "Nothing to send (no pending matches or a session is already running)"), !res.run_ids.length);
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

  const lf = { 1: L("Männer", "Men"), 2: L("Frauen", "Women") }[a.looking_for_gender] || a.looking_for_gender;
  $("#acc-details").innerHTML = `<dl class="kv">
      <dt>Name</dt><dd>${esc(a.name)}${(a.name_history || []).length ? ` <span class="muted">(${esc(t("rename.formerly", { n: a.name_history.join(", ") }))})</span>` : ""}</dd>
      <dt>${L("Geburtstag", "Birthday")}</dt><dd>${esc(a.birthday || "—")}${age !== null ? ` (${age})` : ""}</dd>
      <dt>${L("Geschlecht / sucht", "Gender / looking for")}</dt><dd>${L("Weiblich", "Female")} · ${esc(lf)}</dd>
      <dt>${L("Beziehung (Registrierung)", "Relationship (signup)")}</dt><dd>${a.relationship_search ? `${esc(a.relationship_search)} · dating ${esc(a.dating_relationship_search || "—")}` : "—"}</dd>
      <dt>${L("Standort", "Location")}</dt><dd>${esc(a.location || "—")}${a.latitude ? ` <span class="muted">(${esc(a.latitude)}, ${esc(a.longitude)})</span>` : ""}</dd>
      <dt>${L("Profilfoto", "Profile photo")}</dt><dd>${esc(a.photo || "—")} · ${a.photo_uploaded ? L("hochgeladen", "uploaded") : L("nicht hochgeladen", "not uploaded")} · ${L("Galerie", "gallery")} ${a.gallery_count}</dd>
      <dt>${L("Registrierungs-photo_url", "Signup photo_url")}</dt><dd class="mono">${esc(a.photo_url || "—")}</dd>
      <dt>${L("Gerät", "Device")}</dt><dd>${esc(dev)}</dd>
      <dt>Android ID</dt><dd class="mono">${esc(a.android_id || "—")}</dd>
      <dt>${L("Letzte Änderung", "Last update")}</dt><dd>${fmtDate(a.updated_at)}</dd>
    </dl>
    <div class="form-grid" style="margin:0">
      <label>Status<select id="acc-status">${ACC_STATUSES.map((s) => `<option value="${s}" ${s === a.status ? "selected" : ""}>${esc(statusText(s))}</option>`).join("")}</select></label>
      <label class="span-2">${L("Notizen", "Notes")}<textarea id="acc-notes" rows="2" placeholder="${L("Alles, was man sich zu diesem Account merken sollte", "Anything worth remembering about this account")}">${esc(a.notes)}</textarea></label>
    </div>
    <div class="actions">
      <button class="btn small primary" id="acc-save">${icon("check")}${L("Speichern", "Save")}</button>
      <button class="btn small danger" id="acc-delete" ${run ? `disabled title="${L("Zuerst die laufende Sitzung stoppen", "Stop the running session first")}"` : ""}>${icon("trash")}${L("Account löschen", "Delete account")}</button>
    </div>`;
  $("#acc-save").onclick = guard(async () => {
    await api(`/api/accounts/${a.id}`, { method: "PATCH", body: { status: $("#acc-status").value, notes: $("#acc-notes").value } });
    toast(L("Account gespeichert", "Account saved"));
    refreshAccountSoon();
  });
  $("#acc-delete").onclick = guard(async () => {
    if (!confirm(L(`Account „${a.name}“ (#${a.id}) aus der Datenbank löschen? Login und Verlauf gehen verloren.`,
                   `Delete account "${a.name}" (#${a.id}) from the database? Its tokens and history will be lost.`))) return;
    await api(`/api/accounts/${a.id}`, { method: "DELETE" });
    toast(L("Account gelöscht", "Account deleted"));
    location.hash = "#accounts";
  });

  $("#acc-runs").innerHTML = `<thead><tr><th>#</th><th>${L("Art", "Type")}</th><th>Status</th><th>${L("Schritt", "Step")}</th>
      <th class="num">Likes</th><th class="num">Dislikes</th><th class="num">Matches</th><th class="num">${L("Nachr.", "Msgs")}</th>
      <th>${L("Gestartet", "Started")}</th><th>${L("Dauer", "Duration")}</th><th>${L("Ergebnis", "Result")}</th><th></th></tr></thead>
    <tbody>${acct.runs.map((r) => `<tr>
      <td>${r.id}</td><td>${esc(kindText(r.kind))}</td><td>${badge(r.status)}</td>
      <td>${esc(stepLabel(r.step) || "—")}</td>
      <td class="num">${r.liked}</td><td class="num">${r.disliked}</td><td class="num">${r.matches}</td><td class="num">${r.messages_sent}</td>
      <td>${fmtDate(r.started_at)}</td><td>${esc(duration(r))}</td><td class="wrapcell" title="${esc(r.reason)}">${esc(reasonText(r.reason) || "—")}</td>
      <td class="actions">${iconBtn("terminal", `data-log="${r.id}"`, L("Log öffnen", "Open log"))}</td></tr>`).join("")
      || `<tr><td colspan="12" class="muted">${L("Keine Sitzungen (importierter Account)", "No sessions recorded (legacy account)")}</td></tr>`}</tbody>`;
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
        ${a.stats_sync_error ? `<span class="sr-danger">${esc(t("sync.error", { e: serverText(a.stats_sync_error) }))}</span>` : ""}</div>
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
      <div class="card-head"><div><h2>${icon("cpu")} ${L(`${esc(workerName(run.worker))} arbeitet an diesem Account`, `${esc(workerName(run.worker))} is working on this account`)}</h2>
        <p class="card-sub" id="acc-live-sub"></p></div>
        <div class="actions">${iconBtn("terminal", `data-log="${run.id}"`, L("Ganzes Log öffnen", "Open full log"))}
          <button class="btn small danger" id="acc-stop">${icon("stop")}${L("Stoppen", "Stop")}</button></div></div>
      <div id="acc-live-steps"></div>
      <div class="log-view compact" id="acc-live-log"></div>
    </div>`;
    $("#acc-stop").onclick = guard(async () => { await api(`/api/runs/${run.id}/stop`, { method: "POST" }); toast(L("Wird gestoppt …", "Stopping…")); });
    box.querySelector("[data-log]").onclick = () => openRunModal(run.id);
    streamRunLog(run.id);
  }
  $("#acc-live-sub").textContent = `${L("Sitzung", "Session")} #${run.id} · ${kindText(run.kind)} · ${duration(run) || L("startet", "starting")} · Proxy ${run.proxy_label || "—"}`;
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
        ? (messaged.has(String(uid)) ? `<span class="badge ok">${L("angeschrieben", "messaged")}</span>` : `<span class="badge warn">${L("offen", "pending")}</span>`) : "";
      return `<div class="person">${icon(acct.listTab === "matches" ? "heart" : acct.listTab === "liked" ? "thumbsUp" : "thumbsDown")}
        <span class="mono">${esc(uid)}</span>${tag}</div>`;
    }).join("")}</div>`
    : emptyState(acct.listTab === "matches" ? "heart" : "users", L("Noch nichts hier", "Nothing here yet"),
      acct.listTab === "matches" ? L("Matches erscheinen, wenn ein gelikter User zurück liked.", "Matches appear when a liked user likes back.")
        : L("Mit diesem Account wurde noch nicht geswiped.", "No swipes with this account yet."));
}

function timelineItem(e) {
  const st = EVENT_STYLE[e.kind] || { icon: "activity", tone: "neutral", text: () => e.kind };
  return `<div class="tl-item" data-ev="${e.id}">
    <span class="tl-icon icon-bubble ${st.tone}">${icon(st.icon)}</span>
    <div class="tl-body"><div class="tl-text">${esc(st.text(e))}</div>
      ${e.detail ? `<div class="tl-detail">${esc(e.detail)}</div>` : ""}</div>
    <time title="${esc(fmtDate(e.ts))}">${esc(fmtTime(e.ts))}<span>${esc(new Date(e.ts).toLocaleDateString(LANG, { day: "numeric", month: "short" }))}</span></time>
  </div>`;
}

function renderTimeline() {
  $("#acc-timeline").innerHTML = acct.events.length ? acct.events.map(timelineItem).join("")
    : emptyState("activity", L("Noch keine Aktivität", "No activity yet"), L("Likes, Matches und Nachrichten erscheinen hier, sobald sie passieren.", "Likes, matches and messages will show up here as they happen."));
}

function prependTimeline(e) {
  const tl = $("#acc-timeline");
  if (!tl) return;
  if (tl.querySelector(".empty")) tl.innerHTML = "";
  tl.insertAdjacentHTML("afterbegin", timelineItem(e));
  tl.firstElementChild.classList.add("fresh");
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
