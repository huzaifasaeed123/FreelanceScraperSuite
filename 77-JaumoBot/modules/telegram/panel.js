"use strict";

// Telegram module UI. Loaded by the panel (frontend/app.js, "Bot modules") the first time a Telegram tab opens.
// Each tab is a function (el) that renders into the tab's <section>; tabs are filled in phase by phase.
(() => {
  const K = window.PanelKit;
  const { L, esc, icon } = K;
  const API = "/api/telegram";

  // --- helpers -----------------------------------------------------------------------------

  // The server sends its messages in English; the panel shows them in German when it is set to German.
  const DE = [
    [/^Invalid phone number$/, "Ungültige Telefonnummer"],
    [/^API ID and API Hash are required/, "API-ID und API-Hash werden benötigt (my.telegram.org)"],
    [/^API ID \/ API Hash are not valid/, "API-ID / API-Hash sind ungültig (my.telegram.org prüfen)"],
    [/^This phone number is banned by Telegram$/, "Diese Nummer ist von Telegram gesperrt"],
    [/^Too many code requests/, "Zu viele Code-Anfragen für diese Nummer, später erneut versuchen"],
    [/^The code is wrong$/, "Der Code ist falsch"],
    [/^Enter the code$/, "Bitte den Code eingeben"],
    [/^The code has expired/, "Der Code ist abgelaufen, bitte einen neuen anfordern"],
    [/^Wrong two-step verification password$/, "Falsches Passwort der Zwei-Schritt-Bestätigung"],
    [/^Too many password attempts/, "Zu viele Passwort-Versuche, später erneut versuchen"],
    [/^Telegram ended this session/, "Telegram hat diese Sitzung beendet, bitte neu anmelden"],
    [/^This Telegram account was deactivated$/, "Dieses Telegram-Konto wurde deaktiviert"],
    [/^This Telegram account was banned$/, "Dieses Telegram-Konto wurde gesperrt"],
    [/^Telegram asks to wait (\d+) s/, (m) => `Telegram verlangt eine Wartezeit von ${m[1]} s`],
    [/^Could not reach Telegram/, "Telegram ist nicht erreichbar (Netzwerkproblem)"],
    [/^The login has expired/, "Die Anmeldung ist abgelaufen, bitte neu starten"],
    [/^Enter the code first$/, "Bitte zuerst den Code eingeben"],
    [/^This account is already linked and online$/, "Dieses Konto ist bereits verbunden und online"],
    [/^This account is not logged in yet/, "Dieses Konto ist noch nicht angemeldet, bitte zuerst anmelden"],
    [/^This account has an active run/, "Für dieses Konto läuft ein Durchlauf, bitte zuerst stoppen"],
    [/^This account is not online$/, "Dieses Konto ist nicht online"],
    [/^Chat not found$/, "Chat nicht gefunden"],
    [/^Invalid chat status$/, "Ungültiger Chat-Status"],
    [/^Invalid date$/, "Ungültiges Datum"],
    [/^No chats selected$/, "Keine Chats ausgewählt"],
    [/^Notes are too long/, "Die Notiz ist zu lang (höchstens 2000 Zeichen)"],
    [/^The label is too long \((\d+)/, (m) => `Die Bezeichnung ist zu lang (höchstens ${m[1]} Zeichen)`],
    [/The text contains invalid characters$/i, "Der Text enthält ungültige Zeichen"],
    [/^Number out of range$/, "Zahl außerhalb des gültigen Bereichs"],
    [/^A workflow can have (\d+) steps at most$/, (m) => `Ein Ablauf kann höchstens ${m[1]} Schritte haben`],
    [/^A workflow needs at least one step$/, "Ein Ablauf braucht mindestens einen Schritt"],
    [/^The workflow name must be 1 to 80/, "Der Name des Ablaufs muss 1 bis 80 Zeichen lang sein"],
    [/^A workflow with this name already exists$/, "Ein Ablauf mit diesem Namen existiert bereits"],
    [/^Workflow not found$/, "Ablauf nicht gefunden"],
    [/^This workflow has an active run/, "Für diesen Ablauf läuft ein Durchlauf, bitte zuerst stoppen"],
    [/^Step (\d+): (.+)$/, (m) => `Schritt ${m[1]}: ${errText(m[2])}`],
    [/^blocking the user is only allowed as the last step$/, "„Nutzer blockieren“ ist nur als letzter Schritt erlaubt"],
    [/^invalid step$/, "ungültiger Schritt"],
    [/^unknown step type$/, "unbekannter Schritttyp"],
    [/^the pause must be a whole number of seconds/, "die Pause muss eine ganze Zahl von 0 bis 86400 Sekunden sein"],
    [/^text is required$/, "der Text darf nicht leer sein"],
    [/^text is too long \((\d+)/, (m) => `der Text ist zu lang (höchstens ${m[1]} Zeichen)`],
    [/^a (\w+) file is required$/, "eine Datei ist erforderlich"],
    [/^the file is not a (\w+) file$/, "die Datei hat nicht den passenden Typ"],
    [/^the uploaded file does not exist/, "die hochgeladene Datei existiert nicht mehr, bitte neu hochladen"],
    [/^Converting this audio file needs ffmpeg/, "Zum Umwandeln dieser Audiodatei wird ffmpeg benötigt, das auf dem Server fehlt. Bitte eine OGG/Opus-Datei hochladen."],
    [/^Invalid file name$/, "Ungültiger Dateiname"],
    [/^The file has no extension/, "Die Datei hat keine Endung (erlaubt: jpg, png, webp, ogg, opus, mp3, m4a, wav, aac)"],
    [/^The file is empty$/, "Die Datei ist leer"],
    [/^Unsupported file type/, "Dateityp nicht unterstützt (erlaubt: jpg, png, webp, ogg, opus, mp3, m4a, wav, aac)"],
    [/^The file content does not match its extension/, "Der Inhalt der Datei passt nicht zur Dateiendung"],
    [/^The file is too large \((\d+) MB/, (m) => `Die Datei ist zu groß (höchstens ${m[1]} MB für diesen Typ)`],
    [/^The image is damaged/, "Das Bild ist beschädigt oder kein echtes Bild"],
    [/^The audio file could not be converted/, "Die Audiodatei konnte nicht umgewandelt werden, sie ist vielleicht beschädigt"],
    [/^The audio conversion failed/, "Die Audio-Umwandlung ist fehlgeschlagen (ffmpeg konnte nicht gestartet werden)"],
    [/^File not found$/, "Datei nicht gefunden"],
    [/^This file is used by: (.+)$/, (m) => `Diese Datei wird verwendet von: ${m[1]}`],
    [/^Run not found$/, "Durchlauf nicht gefunden"],
    [/^Invalid run status$/, "Ungültiger Durchlauf-Status"],
    [/^This account already has an active run/, "Für dieses Konto läuft bereits ein Durchlauf"],
    [/^This account is not online, connect/, "Dieses Konto ist nicht online, bitte zuerst verbinden"],
    [/^The run cannot be (\w+), it is (\w+)/, "Das ist im aktuellen Zustand des Durchlaufs nicht möglich"],
    [/^The run is still active/, "Der Durchlauf läuft noch, bitte zuerst stoppen"],
    [/^Some of the chats do not belong/, "Einige Chats gehören nicht zu diesem Konto"],
    [/^Account offline$/, "Konto offline, bitte verbinden und fortsetzen"],
    [/^Connection to Telegram lost$/, "Verbindung zu Telegram verloren, das Konto verbindet sich neu"],
    [/^Server restarted$/, "Der Server wurde neu gestartet, bitte fortsetzen"],
    [/^Unexpected error: (.+)$/, (m) => `Unerwarteter Fehler (${m[1]})`],
    [/^The user's privacy settings/, "Die Datenschutz-Einstellungen des Nutzers erlauben diese Nachricht nicht"],
    [/^Telegram limited this account/, "Telegram hat dieses Konto für Nachrichten an neue Kontakte eingeschränkt (PeerFlood)"],
    [/^The user's account was deleted$/, "Das Konto des Nutzers wurde gelöscht"],
    [/^The user has blocked this account$/, "Der Nutzer hat dieses Konto blockiert"],
    [/^This account has blocked the user$/, "Dieses Konto hat den Nutzer blockiert"],
    [/^The user only accepts messages from contacts$/, "Der Nutzer nimmt nur Nachrichten von Kontakten an"],
    [/^Invalid recipient/, "Ungültiger Empfänger (der Chat wurde nicht gefunden)"],
    [/^Writing to this chat is not allowed$/, "Schreiben in diesem Chat ist nicht erlaubt"],
    [/^The user does not accept voice messages$/, "Der Nutzer nimmt keine Sprachnachrichten an"],
    [/^Telegram rejected the media file$/, "Telegram hat die Mediendatei abgelehnt"],
    [/^The media file is missing on the server$/, "Die Mediendatei fehlt auf dem Server"],
    [/^Telegram keeps asking to wait \(FloodWait (\d+) s\)/, (m) => `Telegram verlangt immer wieder eine Wartezeit (FloodWait ${m[1]} s)`],
    [/^The chat has no access key/, "Der Chat hat keinen Zugriffsschlüssel, bitte die Chats neu synchronisieren"],
    [/^Telegram error: (.+)$/, (m) => `Telegram-Fehler: ${m[1]}`],
  ];
  function errText(msg) {
    if (K.lang !== "de") return msg;
    for (const [re, de] of DE) {
      const m = re.exec(msg);
      if (m) return typeof de === "function" ? de(m) : de;
    }
    return msg;
  }
  const act = (fn) => async (...args) => {
    try { await fn(...args); } catch (e) { if (e.message !== "Not authenticated") K.toast(errText(e.message), true); }
  };

  const head = (title, sub, actions = "") => `
    <div class="page-head"><div><h1>${esc(title)}</h1>${sub ? `<p>${esc(sub)}</p>` : ""}</div>
    ${actions ? `<div class="page-actions">${actions}</div>` : ""}</div>`;

  const iconBtn = (name, attrs, title) =>
    `<button type="button" class="icon-btn sm" ${attrs} title="${esc(title)}" aria-label="${esc(title)}">${icon(name)}</button>`;

  // --- Konten (accounts) --------------------------------------------------------------------

  const st = { settings: { configured: false } };
  let accountsEl = null;   // the open Konten tab (null when another tab is open)
  let sock = null;

  const STATUS = {   // status -> [badge class, German, English]
    online: ["ok", "Online", "Online"],
    connecting: ["info", "Verbindet …", "Connecting …"],
    offline: ["queued", "Offline", "Offline"],
    error: ["bad", "Fehler", "Error"],
  };
  const badge = (status) => {
    const [cls, de, en] = STATUS[status] || STATUS.offline;
    return `<span class="badge ${cls}">${esc(L(de, en))}</span>`;
  };

  function accountRow(a) {
    const buttons = [];
    if (a.status === "online" || (a.status === "connecting" && a.has_session)) {   // while connecting, Trennen also ends the reconnect attempts
      buttons.push(`<button class="btn small" data-act="disconnect">${esc(L("Trennen", "Disconnect"))}</button>`);
    } else if (a.has_session) {
      buttons.push(`<button class="btn small primary" data-act="connect" ${a.status === "connecting" ? "disabled" : ""}>${esc(L("Verbinden", "Connect"))}</button>`);
      buttons.push(`<button class="btn small" data-act="login">${esc(L("Neu anmelden", "Log in again"))}</button>`);
    } else {
      buttons.push(`<button class="btn small primary" data-act="login">${esc(L("Anmelden", "Log in"))}</button>`);
    }
    buttons.push(iconBtn("pencil", 'data-act="rename"', L("Umbenennen", "Rename")));
    buttons.push(iconBtn("trash", 'data-act="delete"', L("Entfernen", "Remove")));
    return `<tr data-id="${a.id}">
      <td><b>${esc(a.label || a.phone)}</b><div class="muted">${esc(a.phone)}${a.tg_username ? " · @" + esc(a.tg_username) : ""}</div></td>
      <td>${badge(a.status)}${a.status_msg ? `<div class="muted">${esc(errText(a.status_msg))}</div>` : ""}</td>
      <td>${K.fmtNum(a.chats)}</td>
      <td>${a.last_connected_at ? esc(K.relTime(a.last_connected_at)) : "—"}</td>
      <td><div class="actions">${buttons.join("")}</div></td></tr>`;
  }

  async function renderAccounts() {
    const [list, settings] = await Promise.all([K.api(`${API}/accounts`), K.api(`${API}/settings`)]);
    st.settings = settings;
    const el = accountsEl;
    if (!el) return;
    const add = `<button class="btn primary" data-act="add">${icon("plus")}<span>${esc(L("Telegram-Konto verbinden", "Link Telegram account"))}</span></button>`;
    el.innerHTML = head(L("Konten", "Accounts"), L("Telegram-Konten verbinden und verwalten", "Link and manage Telegram accounts"), add) +
      (list.length
        ? `<div class="card table-card"><div style="overflow-x:auto"><table class="table"><thead><tr>
            <th>${esc(L("Konto", "Account"))}</th><th>${esc(L("Status", "Status"))}</th><th>${esc(L("Chats", "Chats"))}</th>
            <th>${esc(L("Zuletzt verbunden", "Last connected"))}</th><th></th></tr></thead>
            <tbody>${list.map(accountRow).join("")}</tbody></table></div></div>`
        : `<div class="empty">${icon("send")}<b>${esc(L("Noch kein Konto verbunden", "No account linked yet"))}</b>
            <span>${esc(L("Verbinde ein Telegram-Konto mit seiner Telefonnummer.", "Link a Telegram account with its phone number."))}</span></div>`);
    K.hydrateIcons(el);
    el.onclick = act(async (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn || btn.disabled) return;
      const row = btn.closest("tr");
      const acc = row ? list.find((a) => a.id === +row.dataset.id) : null;
      const kind = btn.dataset.act;
      if (kind === "add") return wizard("");
      if (kind === "login") return wizard(acc.phone);
      if (kind === "rename") return renameDialog(acc);
      if (kind === "delete") {
        if (!confirm(L(`Konto ${acc.label || acc.phone} entfernen? Alle erfassten Chats und Durchläufe dieses Kontos werden gelöscht.`,
                       `Remove account ${acc.label || acc.phone}? All captured chats and runs of this account are deleted.`))) return;
        await K.api(`${API}/accounts/${acc.id}`, { method: "DELETE" });
      } else {
        btn.disabled = true;
        await K.api(`${API}/accounts/${acc.id}/${kind}`, { method: "POST" });   // connect | disconnect
      }
      await renderAccounts();
    });
  }
  const refreshAccounts = K.throttle(() => renderAccounts().catch(() => {}), 500);

  function renameDialog(acc) {
    K.openModal(L("Konto umbenennen", "Rename account"), `
      <form id="tg-rename"><label><span>${esc(L("Bezeichnung", "Label"))}</span>
        <input name="label" value="${esc(acc.label)}" maxlength="60" required></label>
        <div class="actions"><button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>
        <button class="btn primary" type="submit">${esc(L("Speichern", "Save"))}</button></div></form>`);
    const form = K.$("#tg-rename");
    form.label.focus();
    form.onsubmit = act(async (e) => {
      e.preventDefault();
      await K.api(`${API}/accounts/${acc.id}`, { method: "PATCH", body: { label: form.label.value } });
      K.closeModal();
      await renderAccounts();
    });
  }

  // The linking dialog: 1 phone number (+ API access the first time) -> 2 code -> 3 password (only with two-step verification).
  function wizard(phone) {
    const w = { id: null, phone, showApi: false, finished: false };
    const body = () => K.$("#modal-body");

    // renders one step; onSubmit(formData) throws to show the message under the form
    const show = (title, html, onSubmit) => {
      K.$("#modal-title").textContent = title;
      body().innerHTML = `<form>${html}</form>`;
      const form = body().querySelector("form");
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submit = form.querySelector("[type=submit]"), err = form.querySelector(".error");
        submit.disabled = true;
        err.textContent = "";
        try {
          await onSubmit(new FormData(form), form);
        } catch (ex) {
          if (ex.message !== "Not authenticated") { err.textContent = errText(ex.message); submit.disabled = false; }
        }
      });
      const first = form.querySelector("input");
      if (first) first.focus();
      return form;
    };
    const buttons = (back, submitLabel) => `<p class="error"></p>
      <div class="actions">${back
        ? `<button class="btn" type="button" data-back>${esc(L("Zurück", "Back"))}</button>`
        : `<button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>`}
        <button class="btn primary" type="submit">${esc(submitLabel)}</button></div>`;
    const cancelLogin = async () => {
      if (w.id) { const id = w.id; w.id = null; await K.api(`${API}/accounts/${id}/cancel`, { method: "POST" }).catch(() => {}); }
    };
    const goBack = (form) => form.querySelector("[data-back]").addEventListener("click", async () => { await cancelLogin(); stepPhone(); });

    function stepPhone() {
      const saved = st.settings.configured && !w.showApi;
      const form = show(L("Telegram-Konto verbinden", "Link Telegram account"), `
        <p class="hint">${esc(L("Schritt 1: Telefonnummer", "Step 1: phone number"))}</p>
        <label><span>${esc(L("Telefonnummer des Telegram-Kontos", "Phone number of the Telegram account"))}</span>
          <input name="phone" type="tel" autocomplete="tel" placeholder="+49 151 12345678" value="${esc(w.phone)}" required></label>
        ${saved
          ? `<p class="hint">${esc(L("API-Zugang gespeichert", "API access saved"))} (ID ${esc(st.settings.api_id)}, ${esc(st.settings.api_hash_hint)})
              · <a href="#" data-api>${esc(L("ändern", "change"))}</a></p>`
          : `<div class="form-grid">
               <label><span>API ID</span><input name="api_id" inputmode="numeric" pattern="[0-9]+" required></label>
               <label><span>API Hash</span><input name="api_hash" autocomplete="off" required></label></div>
             <p class="hint">${esc(L("Einmalig nötig: unter", "Needed once: sign in at"))}
               <a href="https://my.telegram.org" target="_blank" rel="noopener">my.telegram.org</a>
               → API development tools ${esc(L("anmelden und die beiden Werte kopieren. Sie werden für weitere Konten gespeichert.",
                 "and copy the two values. They are remembered for further accounts."))}</p>`}
        ${buttons(false, L("Code senden", "Send code"))}`,
      async (f) => {
        const payload = { phone: f.get("phone") };
        if (f.get("api_id")) { payload.api_id = +f.get("api_id"); payload.api_hash = f.get("api_hash"); }
        const r = await K.api(`${API}/accounts/start`, { method: "POST", body: payload });
        w.id = r.id;
        w.phone = r.phone;
        if (payload.api_id) st.settings = await K.api(`${API}/settings`);
        stepCode();
      });
      const change = form.querySelector("[data-api]");
      if (change) change.addEventListener("click", (e) => { e.preventDefault(); w.phone = form.phone.value; w.showApi = true; stepPhone(); });
    }

    function stepCode() {
      const form = show(L("Code eingeben", "Enter the code"), `
        <p class="hint">${esc(L("Schritt 2: Code", "Step 2: code"))}</p>
        <p>${esc(L("Telegram hat einen Code gesendet an", "Telegram sent a code to"))} <b>${esc(w.phone)}</b>.
          ${esc(L("Er kommt als Nachricht in der Telegram-App (Chat „Telegram“) auf einem Gerät, auf dem das Konto angemeldet ist – sonst per SMS.",
                  "It arrives as a message in the Telegram app (the \"Telegram\" chat) on a device where the account is signed in – otherwise by SMS."))}</p>
        <label><span>${esc(L("Code", "Code"))}</span>
          <input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="12" placeholder="12345" required></label>
        ${buttons(true, L("Bestätigen", "Confirm"))}`,
      async (f) => {
        const r = await K.api(`${API}/accounts/${w.id}/code`, { method: "POST", body: { code: f.get("code") } });
        r.step === "password" ? stepPassword() : done(r.account);
      });
      goBack(form);
    }

    function stepPassword() {
      const form = show(L("Zwei-Schritt-Bestätigung", "Two-step verification"), `
        <p class="hint">${esc(L("Schritt 3: Passwort", "Step 3: password"))}</p>
        <p>${esc(L("Dieses Konto ist mit einem zusätzlichen Passwort (Cloud-Passwort) geschützt.", "This account is protected by an additional (cloud) password."))}</p>
        <label><span>${esc(L("Passwort", "Password"))}</span><input name="password" type="password" autocomplete="current-password" required></label>
        ${buttons(true, L("Fertig", "Finish"))}`,
      async (f) => {
        const r = await K.api(`${API}/accounts/${w.id}/password`, { method: "POST", body: { password: f.get("password") } });
        done(r.account);
      });
      goBack(form);
    }

    function done(account) {
      w.finished = true;
      K.closeModal();
      K.toast(L(`Konto verbunden: ${account.label || account.phone}`, `Account linked: ${account.label || account.phone}`));
      if (accountsEl) renderAccounts().catch(() => {});
    }

    K.openModal("", "", () => { if (!w.finished) cancelLogin(); });   // closing the dialog drops the unfinished login
    stepPhone();
  }

  // --- Chats: a reusable table with filters and a selection ----------------------------------------
  // chatTable(host, opts) draws the account selector, search, date range, status chips, the chat table with
  // checkboxes, the selection bar and the pager into `host`. The Chats tab uses it as it is; the Sending tab
  // reuses it to pick the chats of a run.
  //   opts.accounts  the list from /accounts (account selector, account column)
  //   opts.account   id of one account: the table shows only its chats and has no account selector
  //   opts.editable  per-chat edit button + "set status" for the selection (default true)
  //   opts.onChange  called with the selection (a Set of chat ids) whenever it changes
  // Returns { reload(), selectedIds(), account(), selectStatus(status, replace), destroy() }.
  // The selection survives paging and filter changes.

  const CHAT_STATUS = [   // key, emoji, German, English
    ["pending", "🟢", "Noch nicht bearbeitet", "Not processed yet"],
    ["in_progress", "🔵", "In Bearbeitung", "In progress"],
    ["done", "✅", "Bearbeitet", "Processed"],
    ["error", "❌", "Fehler", "Error"],
    ["paused", "⏸️", "Pausiert", "Paused"],
  ];
  const statusLabel = (key) => {
    const [, emoji, de, en] = CHAT_STATUS.find((x) => x[0] === key) || CHAT_STATUS[0];
    return `${emoji} ${L(de, en)}`;
  };
  const fmtN = (n) => Number(n || 0).toLocaleString(K.lang === "de" ? "de-DE" : "en-GB");   // 1.248 / 1,248
  const countText = (n) => (K.lang === "de"
    ? `${fmtN(n)} ${n === 1 ? "Chat" : "Chats"} ausgewählt`
    : `${fmtN(n)} ${n === 1 ? "chat" : "chats"} selected`);

  function injectStyles() {
    if (document.getElementById("tg-style")) return;
    const style = document.createElement("style");
    style.id = "tg-style";
    style.textContent = `
      .tg-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
      .tg-chip { display: inline-flex; align-items: center; gap: 7px; height: 34px; padding: 0 12px; border-radius: 99px;
        border: 1px solid var(--border); background: var(--surface); color: var(--text-2); font: inherit; font-size: 13px; cursor: pointer; }
      .tg-chip:hover { border-color: var(--accent); }
      .tg-chip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 600; }
      .tg-date { display: flex; flex-direction: row; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-2); }
      .tg-date input { height: 38px; }
      .tg-banner { padding: 9px 20px; font-size: 13px; text-align: center; background: var(--surface-2); border-bottom: 1px solid var(--border); }
      .tg-wait svg.ic { animation: tg-spin 1.2s linear infinite; }
      .tg-sort { cursor: pointer; user-select: none; }
      .tg-sort:hover { color: var(--text); }
      .tg-st { white-space: nowrap; font-weight: 600; font-size: 12.5px; }
      .tg-sync { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--info); background: var(--info-soft);
        border-radius: 10px; padding: 9px 14px; margin-bottom: 12px; }
      .tg-sync svg.ic { width: 15px; height: 15px; animation: tg-spin 1.2s linear infinite; }
      @keyframes tg-spin { to { transform: rotate(360deg); } }
      .tg-bar select { padding-top: 5px; padding-bottom: 5px; font-size: 12.5px; }
      .tg-table th, .tg-table td { padding: 10px 8px; }
      .tg-table td.nowrap { white-space: nowrap; }
      .tg-table td.tg-name { min-width: 150px; overflow-wrap: anywhere; }
      .tg-msg { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      @media (max-width: 760px) { .tg-opt { display: none; } .tg-date { flex: 1; } .tg-date input { flex: 1; min-width: 0; } }`;
    document.head.appendChild(style);
  }

  function chatTable(host, opts) {
    injectStyles();
    const editable = opts.editable !== false;
    const accounts = opts.accounts;
    const f = { account: opts.account ? String(opts.account) : "", status: new Set(), q: "", from: "", to: "" };
    const v = { sort: "last_contact_at", order: "desc", page: 0, per: 50, total: 0, items: [], counts: null, allKey: null };
    const selected = new Set();
    let seq = 0, gone = false;
    const $h = (sel) => host.querySelector(sel);
    const accountName = (id) => { const a = accounts.find((x) => x.id === id); return a ? (a.label || a.phone) : "—"; };

    host.innerHTML = `
      <div class="acc-toolbar">
        ${opts.account ? "" : `<select data-f="account" aria-label="${esc(L("Konto", "Account"))}">
          <option value="">${esc(L("Alle Konten", "All accounts"))}</option>
          ${accounts.map((a) => `<option value="${a.id}">${esc(a.label || a.phone)}</option>`).join("")}</select>`}
        <div class="tb-search">${icon("search")}<input type="search" data-f="q" autocomplete="off"
          placeholder="${esc(L("Name, @Benutzername oder Telegram-ID suchen", "Search name, @username or Telegram ID"))}"></div>
        <label class="tg-date"><span>${esc(L("von", "from"))}</span><input type="date" data-f="from"></label>
        <label class="tg-date"><span>${esc(L("bis", "to"))}</span><input type="date" data-f="to"></label>
        <button class="btn ghost" type="button" data-act="reset">${esc(L("Filter zurücksetzen", "Reset filters"))}</button>
      </div>
      <div class="tg-chips" data-chips></div>
      <div class="card table-card">
        <div class="bulk-bar tg-bar">
          <b data-count></b>
          <button class="btn small" type="button" data-act="select-pending">${esc(L("Alle unbearbeiteten auswählen", "Select all not processed"))}</button>
          <button class="btn small ghost" type="button" data-act="clear">${icon("x")}<span>${esc(L("Auswahl aufheben", "Clear selection"))}</span></button>
          ${editable ? `<select data-bulk aria-label="Status">${CHAT_STATUS.map(([k]) => `<option value="${k}">${esc(statusLabel(k))}</option>`).join("")}</select>
            <button class="btn small" type="button" data-act="bulk-status">${esc(L("Status setzen", "Set status"))}</button>` : ""}
        </div>
        <div class="tg-banner hidden" data-banner></div>
        <div style="overflow-x:auto"><table class="table tg-table"><thead data-head></thead><tbody data-rows></tbody></table></div>
        <div class="acc-foot"><span data-showing></span><div class="pages" data-pages></div><select data-per aria-label="${esc(L("Pro Seite", "Per page"))}">
          ${[25, 50, 100, 200].map((n) => `<option value="${n}" ${n === v.per ? "selected" : ""}>${n} ${esc(L("pro Seite", "per page"))}</option>`).join("")}</select></div>
      </div>`;

    // --- query ---
    const filterParams = () => {
      const p = new URLSearchParams();
      if (f.account) p.set("account_id", f.account);
      if (f.status.size) p.set("status", [...f.status].join(","));
      if (f.q.trim()) p.set("q", f.q.trim());
      if (f.from) p.set("date_from", new Date(f.from + "T00:00:00").toISOString());          // the operator's local day
      if (f.to) p.set("date_to", new Date(f.to + "T23:59:59.999").toISOString());
      return p;
    };
    async function load() {
      const my = ++seq;
      const p = filterParams();
      p.set("sort", v.sort); p.set("order", v.order); p.set("limit", v.per); p.set("offset", v.page * v.per);
      const [list, counts] = await Promise.all([
        K.api(`${API}/chats?${p}`),
        K.api(`${API}/chats/summary${f.account ? "?account_id=" + f.account : ""}`)]);
      if (gone || my !== seq) return;     // a newer request has been started meanwhile
      v.items = list.items; v.total = list.total; v.counts = counts;
      const pages = Math.max(1, Math.ceil(v.total / v.per));
      if (v.page >= pages) { v.page = pages - 1; return load(); }
      render();
    }
    const refilter = () => { v.page = 0; return load(); };
    const changed = () => { render(); if (opts.onChange) opts.onChange(selected); };

    // --- drawing ---
    const repliedBadge = (c) => c.replied_at ? ` <span class="badge ok" title="${esc(L("Dieser Kontakt hat geantwortet", "This contact answered"))}">↩ ${esc(L("geantwortet", "replied"))}</span>` : "";
    const blockedBadge = (c) => c.blocked ? ` <span class="badge bad" title="${esc(L("Der Ablauf hat diesen Nutzer in Telegram blockiert", "A workflow blocked this user on Telegram"))}">🚫 ${esc(L("blockiert", "blocked"))}</span>` : "";
    function row(c) {
      const showAccount = !f.account && accounts.length > 1;
      return `<tr data-id="${c.id}">
        <td class="cb"><input type="checkbox" data-sel ${selected.has(c.id) ? "checked" : ""} aria-label="${esc(L("Chat auswählen", "Select chat"))}"></td>
        <td class="tg-name"><b>${esc(c.display_name)}</b>${blockedBadge(c)}${repliedBadge(c)}${c.username ? `<div class="muted">@${esc(c.username)}</div>` : ""}</td>
        <td class="mono">${esc(c.telegram_id)}</td>
        ${showAccount ? `<td class="tg-opt nowrap">${esc(accountName(c.account_id))}</td>` : ""}
        <td><span class="tg-st">${esc(statusLabel(c.chat_status))}</span>${c.chat_status === "error" && c.error_reason
          ? `<div class="muted">${esc(errText(c.error_reason))}</div>` : ""}</td>
        <td class="tg-opt"><div class="tg-msg" title="${esc(c.last_message)}">${esc(c.last_message) || "—"}</div></td>
        <td class="nowrap">${esc(K.fmtDate(c.last_contact_at))}<div class="muted tg-opt" title="${esc(L("Erster Kontakt", "First contact"))}">${esc(K.fmtDate(c.first_contact_at))}</div></td>
        <td class="num nowrap">${fmtN(c.messages_sent)}<div class="muted tg-opt" title="${esc(L("Zuletzt bearbeitet", "Last processed"))}">${esc(K.fmtDate(c.last_processed_at))}</div></td>
        <td>${editable ? iconBtn("pencil", 'data-act="edit"', L("Bearbeiten", "Edit")) : ""}</td></tr>`;
    }
    function render() {
      $h("[data-chips]").innerHTML = CHAT_STATUS.map(([k, emoji, de, en]) =>
        `<button type="button" class="tg-chip${f.status.has(k) ? " on" : ""}" data-status="${k}" aria-pressed="${f.status.has(k)}">
          ${emoji} ${esc(L(de, en))}<span class="seg-count">${fmtN(v.counts.by_status[k])}</span></button>`).join("");
      const showAccount = !f.account && accounts.length > 1;
      const sortLink = (key, label, cls = "") => {   // a header label that sorts by `key`
        const on = v.sort === key;
        return `<span class="tg-sort ${cls}" data-sort="${key}" role="button" tabindex="0">${esc(label)}${on ? (v.order === "asc" ? " ▲" : " ▼") : ""}</span>`;
      };
      const th = (key, label, cls = "") => `<th class="${cls}" aria-sort="${v.sort === key ? (v.order === "asc" ? "ascending" : "descending") : "none"}">${sortLink(key, label)}</th>`;
      $h("[data-head]").innerHTML = `<tr><th class="cb"><input type="checkbox" data-all aria-label="${esc(L("Alle auf dieser Seite auswählen", "Select all on this page"))}"></th>
        ${th("display_name", L("Name", "Name"))}<th>Telegram-ID</th>${showAccount ? `<th class="tg-opt">${esc(L("Konto", "Account"))}</th>` : ""}
        ${th("chat_status", "Status")}<th class="tg-opt">${esc(L("Letzte Nachricht", "Last message"))}</th>
        <th>${sortLink("last_contact_at", L("Letzter Kontakt", "Last contact"))}<div class="tg-opt">${sortLink("first_contact_at", L("Erster Kontakt", "First contact"))}</div></th>
        <th class="num">${sortLink("messages_sent", L("Gesendet", "Sent"))}<div class="tg-opt">${esc(L("Zuletzt bearbeitet", "Last processed"))}</div></th><th></th></tr>`;
      const cols = 8 + (showAccount ? 1 : 0);
      $h("[data-rows]").innerHTML = v.items.length ? v.items.map(row).join("")
        : `<tr><td colspan="${cols}"><div class="empty">${icon("message")}<b>${esc(L("Keine Chats gefunden", "No chats found"))}</b>
            <span>${esc(L("Passe die Filter an oder synchronisiere die Chats des Kontos.", "Change the filters or sync the account's chats."))}</span></div></td></tr>`;
      const ids = v.items.map((c) => c.id);
      const all = $h("[data-all]");
      all.checked = ids.length > 0 && ids.every((id) => selected.has(id));
      all.indeterminate = !all.checked && ids.some((id) => selected.has(id));

      const from = v.total ? v.page * v.per + 1 : 0, to = Math.min(v.total, (v.page + 1) * v.per);
      $h("[data-showing]").textContent = L(`${fmtN(from)}–${fmtN(to)} von ${fmtN(v.total)}`, `${fmtN(from)}–${fmtN(to)} of ${fmtN(v.total)}`);
      const pages = Math.max(1, Math.ceil(v.total / v.per)), nums = [];
      for (let i = 0; i < pages; i++) {
        if (i === 0 || i === pages - 1 || Math.abs(i - v.page) <= 2) nums.push(i);
        else if (nums[nums.length - 1] !== "…") nums.push("…");
      }
      $h("[data-pages]").innerHTML = `<button class="pg" data-pg="${v.page - 1}" ${v.page <= 0 ? "disabled" : ""} aria-label="${esc(L("Zurück", "Previous"))}">${icon("chevronLeft")}</button>
        ${nums.map((n) => n === "…" ? '<span class="pg-gap">…</span>'
          : `<button class="pg${n === v.page ? " active" : ""}" data-pg="${n}">${n + 1}</button>`).join("")}
        <button class="pg" data-pg="${v.page + 1}" ${v.page + 1 >= pages ? "disabled" : ""} aria-label="${esc(L("Weiter", "Next"))}">${icon("chevronRight")}</button>`;
      renderBanner(ids);
      renderBar();
    }
    // Gmail-style offer: the whole page is ticked, there are more matches on other pages -> select them all
    function renderBanner(ids) {
      const banner = $h("[data-banner]");
      const pageFull = ids.length > 0 && ids.every((id) => selected.has(id));
      const more = v.total > ids.length;
      if (!pageFull || !more) { banner.classList.add("hidden"); return; }
      banner.classList.remove("hidden");
      banner.innerHTML = v.allKey === filterParams().toString() && selected.size >= v.total
        ? esc(L(`Alle ${fmtN(v.total)} passenden Chats sind ausgewählt.`, `All ${fmtN(v.total)} matching chats are selected.`))
        : `${esc(L(`Alle ${fmtN(ids.length)} Chats dieser Seite sind ausgewählt.`, `All ${fmtN(ids.length)} chats on this page are selected.`))}
           <button class="btn small ghost" type="button" data-act="select-matching">${esc(L(`Alle ${fmtN(v.total)} passenden Chats auswählen`, `Select all ${fmtN(v.total)} matching chats`))}</button>`;
    }
    function renderBar() {
      $h("[data-count]").textContent = countText(selected.size);
      host.querySelectorAll('[data-act="clear"], [data-act="bulk-status"]').forEach((b) => (b.disabled = !selected.size));
    }

    // --- actions ---
    const addIds = async (params, remember, replace = false) => {
      const r = await K.api(`${API}/chats/ids?${params}`);
      if (replace) selected.clear();
      r.ids.forEach((id) => selected.add(id));
      v.allKey = remember ? params.toString() : null;
      changed();
    };
    // select every chat of the account that has this status ("" = all of them); replace = drop the old selection first
    const selectStatus = (status, replace) => {
      const p = new URLSearchParams();
      if (status) p.set("status", status);
      if (f.account) p.set("account_id", f.account);
      return addIds(p, false, replace);
    };
    function editDialog(c) {
      K.openModal(L("Chat bearbeiten", "Edit chat"), `
        <form id="tg-chat-edit" class="narrow-form" style="max-width:none">
          <p><b>${esc(c.display_name)}</b> <span class="muted">${c.username ? "@" + esc(c.username) + " · " : ""}ID ${esc(c.telegram_id)}</span></p>
          ${c.error_reason ? `<p class="error">${esc(errText(c.error_reason))}</p>` : ""}
          <label><span>Status</span><select name="status">${CHAT_STATUS.map(([k]) =>
            `<option value="${k}" ${k === c.chat_status ? "selected" : ""}>${esc(statusLabel(k))}</option>`).join("")}</select></label>
          <label><span>${esc(L("Notiz", "Note"))}</span><textarea name="notes" rows="4" maxlength="2000">${esc(c.notes)}</textarea></label>
          <div class="actions"><button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>
          <button class="btn primary" type="submit">${esc(L("Speichern", "Save"))}</button></div></form>`);
      const form = K.$("#tg-chat-edit");
      form.onsubmit = act(async (e) => {
        e.preventDefault();
        await K.api(`${API}/chats/${c.id}`, { method: "PATCH", body: { chat_status: form.status.value, notes: form.notes.value } });
        K.closeModal();
        await load();
      });
    }

    host.addEventListener("click", act(async (e) => {
      const t = e.target;
      const chip = t.closest("[data-status]");
      if (chip) {
        const k = chip.dataset.status;
        f.status.has(k) ? f.status.delete(k) : f.status.add(k);
        return refilter();
      }
      const sort = t.closest("[data-sort]");
      if (sort) {
        const key = sort.dataset.sort;
        v.order = v.sort === key && v.order === "desc" ? "asc" : "desc";
        v.sort = key;
        return refilter();
      }
      const pg = t.closest("button[data-pg]");
      if (pg && !pg.disabled) { v.page = +pg.dataset.pg; return load(); }
      const btn = t.closest("[data-act]");
      if (!btn || btn.disabled) return;
      const kind = btn.dataset.act;
      if (kind === "reset") {
        Object.assign(f, { status: new Set(), q: "", from: "", to: "" });
        host.querySelectorAll("[data-f]").forEach((i) => { if (i.dataset.f !== "account") i.value = ""; });
        return refilter();
      }
      if (kind === "select-matching") return addIds(filterParams(), true);
      if (kind === "select-pending") return selectStatus("pending", false);
      if (kind === "clear") { selected.clear(); v.allKey = null; return changed(); }
      if (kind === "bulk-status") {
        const status = $h("[data-bulk]").value;
        if (!confirm(L(`${countText(selected.size)}: Status auf „${statusLabel(status)}“ setzen?`,
                       `${countText(selected.size)}: set status to "${statusLabel(status)}"?`))) return;
        const r = await K.api(`${API}/chats/bulk-status`, { method: "POST", body: { ids: [...selected], status } });
        K.toast(L(`${fmtN(r.updated)} Chats aktualisiert`, `${fmtN(r.updated)} chats updated`));
        return load();
      }
      if (kind === "edit") editDialog(v.items.find((c) => c.id === +btn.closest("tr").dataset.id));
    }));
    host.addEventListener("change", act(async (e) => {
      const t = e.target;
      if (t.matches("[data-sel]")) {
        const id = +t.closest("tr").dataset.id;
        if (t.checked) selected.add(id); else { selected.delete(id); v.allKey = null; }
        return changed();
      }
      if (t.matches("[data-all]")) {
        v.items.forEach((c) => (t.checked ? selected.add(c.id) : selected.delete(c.id)));
        if (!t.checked) v.allKey = null;
        return changed();
      }
      if (t.matches("[data-per]")) { v.per = +t.value; return refilter(); }
      if (t.matches("[data-f]") && t.dataset.f !== "q") { f[t.dataset.f] = t.value; return refilter(); }
    }));
    host.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-sort]")) { e.preventDefault(); e.target.click(); }
    });
    const search = K.debounce(act(() => refilter()), 300);
    host.addEventListener("input", (e) => {
      if (e.target.matches('[data-f="q"]')) { f.q = e.target.value; search(); }
    });

    return {
      reload: load,
      selectedIds: () => [...selected],
      account: () => f.account,
      selectStatus,
      destroy() { gone = true; },
    };
  }

  // --- Chats tab ------------------------------------------------------------------------------

  let chatsEl = null, chatsCtl = null, accountList = [];
  let formCtl = null;   // the chat table of the Versand start form (declared here, drawn in the Versand section)
  const syncing = {};   // account id -> the latest "sync" event of its running chat import
  const accountLabel = (id) => { const a = accountList.find((x) => x.id === id); return a ? (a.label || a.phone) : String(id); };
  const refreshChats = K.throttle(() => { if (chatsCtl) chatsCtl.reload().catch(() => {}); }, 1500);

  function renderSync() {
    const box = chatsEl && chatsEl.querySelector("[data-sync]");
    if (!box) return;
    box.innerHTML = Object.values(syncing).map((s) => `<div class="tg-sync">${icon("refresh")}<span>${esc(s.state === "waiting"
      ? L(`${accountLabel(s.account_id)}: Telegram verlangt eine Pause, es geht in ${s.wait} s weiter …`,
          `${accountLabel(s.account_id)}: Telegram asks for a pause, continuing in ${s.wait} s …`)
      : L(`${accountLabel(s.account_id)}: Chats werden synchronisiert … ${fmtN(s.scanned)} Dialoge geprüft, ${fmtN(s.imported)} Chats übernommen`,
          `${accountLabel(s.account_id)}: syncing chats … ${fmtN(s.scanned)} dialogs checked, ${fmtN(s.imported)} chats imported`))}</span></div>`).join("");
  }

  const syncNow = act(async () => {
    const wanted = chatsCtl.account();
    const targets = wanted ? accountList.filter((a) => String(a.id) === wanted) : accountList.filter((a) => a.status === "online");
    if (!targets.length) { K.toast(L("Kein Konto ist online", "No account is online"), true); return; }
    for (const a of targets) {
      const r = await K.api(`${API}/accounts/${a.id}/sync-chats`, { method: "POST" });
      if (r.started) syncing[a.id] = { account_id: a.id, state: "running", scanned: 0, imported: 0 };
    }
    renderSync();
  });

  function onSync(m) {
    if (m.state === "running" || m.state === "waiting") {
      syncing[m.account_id] = m;
      if (m.state === "running") refreshChats();
    } else {
      delete syncing[m.account_id];
      if (m.state === "done") K.toast(L(`${accountLabel(m.account_id)}: ${fmtN(m.imported)} Chats synchronisiert`, `${accountLabel(m.account_id)}: ${fmtN(m.imported)} chats synced`));
      else K.toast(`${accountLabel(m.account_id)}: ${errText(m.message)}`, true);
      if (chatsCtl) chatsCtl.reload().catch(() => {});
    }
    renderSync();
  }

  // One module WebSocket serves every tab and the "run active" badge. It opens with the first tab (or with the
  // login, see start() below) and closes at logout; it reconnects by itself and re-reads the runs when it does.
  function onEvent(m) {
    if (m.type === "account") {
      if (accountsEl) refreshAccounts();
      const a = accountList.find((x) => x.id === m.account_id);
      if (a) { a.status = m.status; paintAccountBar(); if (formCtl) paintForm(); }
    } else if (m.type === "sync" && chatsCtl) onSync(m);
    else if (m.type === "chat") { if (chatsCtl) refreshChats(); if (formCtl) refreshForm(); if (dashEl) reloadDash(); }
    else if (m.type === "run") onRun(m);
    else if (m.type === "flood") {
      const acc = accountOf(m.account_id), who = acc ? (acc.label || acc.phone) : "";
      if (m.kind === "peer") K.toast(L(`${who}: Telegram hat das Konto für neue Kontakte eingeschränkt (PeerFlood)`, `${who}: Telegram limited the account for new contacts (PeerFlood)`), true);
      else K.toast(L(`${who}: Telegram verlangt eine Wartezeit von ${m.seconds} s (FloodWait)`, `${who}: Telegram asks to wait ${m.seconds} s (FloodWait)`));
    }
  }
  const watch = () => { if (!sock) sock = K.moduleSocket("telegram", onEvent, syncRuns); };

  // --- Abläufe (workflows): saved list and the step editor ---------------------------------------
  // Each step type is ONE entry here (icon, label, upload rules) and one entry in STEP_TYPES of api.py.
  // `media` marks a type that sends an uploaded file; `limit` is its size limit in MB; `action` a final step without content.

  const STEP_KINDS = {
    text: { emoji: "📝", de: "Text", en: "Text" },
    image: { emoji: "🖼️", de: "Bild", en: "Image", media: "image", limit: 10,
      accept: ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" },
    voice: { emoji: "🎤", de: "Sprachmemo", en: "Voice memo", media: "voice", limit: 50,
      accept: ".ogg,.opus,.oga,.mp3,.m4a,.wav,.aac,audio/*" },
    // an action, not a message: it has no content or pause and may only end a workflow (`action`)
    block: { emoji: "🚫", de: "Nutzer blockieren", en: "Block user", action: true },
  };
  const kindName = (type) => L(STEP_KINDS[type].de, STEP_KINDS[type].en);
  // Telegram's own "how long should the media be shown after opening" choices (an image has all, a voice message only "once")
  const selfDestructChoices = (type) => [["", "Nicht löschen", "Don't delete"], ["once", "Einmalig zeigen", "Show once"],
    ...(type === "image" ? [["3", "3 Sekunden", "3 seconds"], ["10", "10 Sekunden", "10 seconds"], ["30", "30 Sekunden", "30 seconds"]] : [])];
  const PAUSES = [0, 10, 30, 60, 120, 300, 600];     // the quick choices, in seconds
  const UNITS = { s: 1, min: 60, h: 3600 };
  const MAX_PAUSE = 86400, MAX_TEXT = 4096;

  const fmtDur = (sec) => {
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60, parts = [];
    if (h) parts.push(`${h} h`);
    if (m) parts.push(`${m} ${L("Min", "min")}`);
    if (s || !parts.length) parts.push(`${s} s`);
    return parts.join(" ");
  };
  // pauses after every step but the last one (nothing waits after the final message)
  const pauseTotal = (steps) => steps.slice(0, -1).reduce((sum, s) => sum + (Number.isInteger(s.pause_after) ? s.pause_after : 0), 0);

  function injectWorkflowStyles() {
    if (document.getElementById("tg-wf-style")) return;
    const style = document.createElement("style");
    style.id = "tg-wf-style";
    style.textContent = `
      .tg-wf-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }
      .tg-wf-card { padding: 16px; display: flex; flex-direction: column; gap: 12px; cursor: pointer; min-width: 0; }
      .tg-wf-card:hover { border-color: var(--accent); }
      .tg-wf-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
      .tg-wf-top b { overflow-wrap: anywhere; font-size: 15px; }
      .tg-wf-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 20px; line-height: 1.2; }
      .tg-wf-gap { font-size: 11px; color: var(--text-2); background: var(--surface-3); border-radius: 99px; padding: 2px 8px; white-space: nowrap; }
      .tg-editor { max-width: 820px; }
      .tg-unused { margin: 0 0 14px; padding: 0; list-style: none; max-height: 260px; overflow-y: auto; font-size: 13px; }
      .tg-unused li { display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); }
      .tg-unused li span:first-of-type { flex: 1; overflow-wrap: anywhere; }
      .tg-meta { padding: 16px 18px; margin-bottom: 18px; display: grid; gap: 10px; }
      .tg-meta label { display: grid; gap: 6px; }
      .tg-total { font-size: 13px; color: var(--text-2); }
      .tg-dirty { font-size: 12.5px; color: var(--warn); font-weight: 600; }
      .tg-step { padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow-sm); }
      .tg-step.dragging { opacity: .4; }
      .tg-step.drop-before { box-shadow: 0 -4px 0 0 var(--accent); }
      .tg-step.drop-after { box-shadow: 0 4px 0 0 var(--accent); }
      .tg-step-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
      .tg-grip { cursor: grab; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 7px; color: var(--muted);
        font-size: 18px; user-select: none; touch-action: none; }
      .tg-grip:hover { background: var(--surface-3); color: var(--text); }
      .tg-step-num { width: 24px; height: 24px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); font-size: 12px;
        font-weight: 700; display: grid; place-items: center; }
      .tg-step-type { font-weight: 600; }
      .tg-step-tools { margin-left: auto; display: flex; gap: 4px; }
      .tg-step textarea { width: 100%; font-family: inherit; font-size: 14px; min-height: 76px; }
      .tg-once { margin-top: 12px; max-width: 340px; }
      .tg-count { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); margin-top: 4px; }
      .tg-count .error { min-height: 0; font-size: 12.5px; }
      .tg-media { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
      .tg-media img { max-height: 150px; max-width: 100%; border-radius: 8px; border: 1px solid var(--border); background: var(--surface-3); }
      .tg-media audio { max-width: 100%; width: 320px; }
      .tg-drop { border: 1px dashed var(--border-strong); border-radius: 10px; padding: 16px; color: var(--muted); font-size: 13px; flex: 1; text-align: center; }
      .tg-pause { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
      .tg-pause label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-2); }
      .tg-pause select, .tg-pause input { padding-top: 6px; padding-bottom: 6px; }
      .tg-custom { display: inline-flex; gap: 6px; }
      .tg-custom input { width: 90px; }
      .tg-pause .error { flex-basis: 100%; min-height: 0; font-size: 12.5px; }
      .tg-arrow { text-align: center; color: var(--muted); font-size: 13px; padding: 5px 0; }
      .tg-arrow b { color: var(--accent); font-size: 17px; }
      .tg-add { position: relative; margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-start; }
      .tg-menu { position: absolute; top: 100%; left: 0; margin-top: 6px; z-index: 5; min-width: 220px; background: var(--surface);
        border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow-lg); padding: 6px; display: grid; gap: 2px; }
      .tg-menu button { text-align: left; padding: 9px 12px; border: 0; background: transparent; color: var(--text); font: inherit; border-radius: 7px; cursor: pointer; }
      .tg-menu button:hover, .tg-menu button:focus-visible { background: var(--surface-3); outline: none; }
      .tg-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
      .tg-invalid { border-color: var(--danger) !important; }
      @media (max-width: 760px) { .tg-step-tools { margin-left: 0; width: 100%; } .tg-media > div { flex: 1 1 100%; } .tg-media audio { width: 100%; } }`;
    document.head.appendChild(style);
  }

  let wfEl = null;       // the open Abläufe tab (null when another tab is open)
  let ed = null;         // the workflow being edited; kept while the operator visits other tabs, so nothing is lost
  let uid = 0;

  // --- list ---

  async function renderWorkflowList() {
    injectWorkflowStyles();
    const list = await K.api(`${API}/workflows`);
    const el = wfEl;
    if (!el || ed) return;
    const add = `<button class="btn" data-act="cleanup">${icon("trash")}<span>${esc(L("Ungenutzte Dateien", "Unused files"))}</span></button>
      <button class="btn primary" data-act="new">${icon("plus")}<span>${esc(L("Neuer Ablauf", "New workflow"))}</span></button>`;
    const card = (w) => {
      const flow = w.steps.map((s, i) => `<span role="img" aria-label="${esc(kindName(s.type))}" title="${esc(kindName(s.type))}">${STEP_KINDS[s.type] ? STEP_KINDS[s.type].emoji : "?"}</span>`
        + (i < w.steps.length - 1 ? `<span class="tg-wf-gap" title="${esc(L("Pause danach", "Pause after"))}">${esc(fmtDur(s.pause_after))}</span>` : "")).join("");
      const n = w.steps.length;
      return `<div class="card tg-wf-card" data-id="${w.id}" tabindex="0" role="button" aria-label="${esc(L("Ablauf bearbeiten", "Edit workflow"))}: ${esc(w.name)}">
        <div class="tg-wf-top"><b>${esc(w.name)}</b><div class="actions">
          ${iconBtn("pencil", 'data-act="rename"', L("Umbenennen", "Rename"))}${iconBtn("copy", 'data-act="duplicate"', L("Duplizieren", "Duplicate"))}${iconBtn("trash", 'data-act="delete"', L("Löschen", "Delete"))}
        </div></div>
        <div class="tg-wf-flow">${flow}</div>
        <div class="muted">${esc(L(`${n} ${n === 1 ? "Schritt" : "Schritte"}`, `${n} ${n === 1 ? "step" : "steps"}`))} · ${esc(L("Pausen", "Pauses"))}: ${esc(fmtDur(pauseTotal(w.steps)))}</div></div>`;
    };
    el.innerHTML = head(L("Abläufe", "Workflows"), L("Nachrichtenabläufe erstellen und speichern", "Build and save message workflows"), add) +
      (list.length ? `<div class="tg-wf-grid">${list.map(card).join("")}</div>`
        : `<div class="empty">${icon("sliders")}<b>${esc(L("Noch kein Ablauf gespeichert", "No workflow saved yet"))}</b>
            <span>${esc(L("Ein Ablauf ist eine Folge aus Sprachmemo, Text und Bild mit Pausen dazwischen.", "A workflow is a sequence of voice memo, text and image with pauses in between."))}</span></div>`);
    K.hydrateIcons(el);
    el.onclick = act(async (e) => {
      const btn = e.target.closest("[data-act]"), cardEl = e.target.closest(".tg-wf-card");
      const w = cardEl ? list.find((x) => x.id === +cardEl.dataset.id) : null;
      if (btn && btn.dataset.act === "new") return openEditor(null);
      if (btn && btn.dataset.act === "cleanup") return unusedFilesDialog();
      if (!w) return;
      const kind = btn ? btn.dataset.act : "edit";
      if (kind === "edit") return openEditor(w);
      if (kind === "rename") return renameWorkflowDialog(w);
      if (kind === "duplicate") {
        const taken = new Set(list.map((x) => x.name.toLowerCase()));
        let name = "", n = 1;
        do {
          const suffix = ` (${L("Kopie", "copy")}${n > 1 ? " " + n : ""})`;
          name = w.name.slice(0, 80 - suffix.length) + suffix;
          n++;
        } while (taken.has(name.toLowerCase()));
        await K.api(`${API}/workflows/${w.id}/duplicate`, { method: "POST", body: { name } });
        K.toast(L("Ablauf dupliziert", "Workflow duplicated"));
      } else if (kind === "delete") {
        if (!confirm(L(`Ablauf „${w.name}“ löschen?`, `Delete workflow "${w.name}"?`))) return;
        await K.api(`${API}/workflows/${w.id}`, { method: "DELETE" });
      }
      await renderWorkflowList();
    });
    el.onkeydown = (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("tg-wf-card")) { e.preventDefault(); e.target.click(); }
    };
  }

  function renameWorkflowDialog(w) {
    K.openModal(L("Ablauf umbenennen", "Rename workflow"), `
      <form id="tg-wf-rename"><label><span>${esc(L("Name", "Name"))}</span>
        <input name="name" value="${esc(w.name)}" maxlength="80" required></label><p class="error"></p>
        <div class="actions"><button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>
        <button class="btn primary" type="submit">${esc(L("Speichern", "Save"))}</button></div></form>`);
    const form = K.$("#tg-wf-rename");
    form.name.focus();
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await K.api(`${API}/workflows/${w.id}`, { method: "PATCH", body: { name: form.name.value } });
      } catch (ex) {
        if (ex.message !== "Not authenticated") form.querySelector(".error").textContent = errText(ex.message);
        return;
      }
      K.closeModal();
      await renderWorkflowList();
    };
  }

  // Uploaded files that no workflow (and no unfinished run) uses any more. The server spares files younger than an hour
  // by default (an open editor may be about to save them); this list is only reachable while no editor is open.
  async function unusedFilesDialog() {
    const { items, bytes } = await K.api(`${API}/media/unused?min_age_minutes=0`);
    const size = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
    K.openModal(L("Ungenutzte Dateien", "Unused files"), `
      <p class="hint">${esc(L("Bilder und Sprachmemos, die in keinem Ablauf mehr vorkommen. Sie belegen nur Speicherplatz und können gelöscht werden.",
        "Images and voice memos that no workflow uses any more. They only take up space and can be deleted."))}</p>
      ${items.length
        ? `<p><b>${esc(L(`${items.length} ${items.length === 1 ? "Datei" : "Dateien"}, ${size(bytes)}`, `${items.length} ${items.length === 1 ? "file" : "files"}, ${size(bytes)}`))}</b></p>
           <ul class="tg-unused">${items.map((i) => `<li>${STEP_KINDS[i.kind] ? STEP_KINDS[i.kind].emoji : ""} <span>${esc(i.name)}</span> <span class="muted">${esc(size(i.size))}</span></li>`).join("")}</ul>`
        : `<div class="empty"><b>${esc(L("Keine ungenutzten Dateien", "No unused files"))}</b></div>`}
      <div class="actions" style="margin-top:14px;justify-content:flex-end"><button class="btn" type="button" data-close-modal>${esc(L("Schließen", "Close"))}</button>
        ${items.length ? `<button class="btn danger" type="button" data-clean>${esc(L("Alle löschen", "Delete all"))}</button>` : ""}</div>`);
    const clean = K.$("#modal [data-clean]");
    if (clean) {
      clean.onclick = act(async () => {
        clean.disabled = true;
        const done = await K.api(`${API}/media/cleanup`, { method: "POST", body: { min_age_minutes: 0 } });
        K.closeModal();
        K.toast(L(`${done.deleted} ${done.deleted === 1 ? "Datei" : "Dateien"} gelöscht`, `${done.deleted} ${done.deleted === 1 ? "file" : "files"} deleted`));
      });
    }
  }

  // --- editor: state ---

  const pauseUnit = (sec) => (sec && sec % 3600 === 0 ? "h" : sec && sec % 60 === 0 ? "min" : "s");
  function stepFrom(src) {   // an editor step from a server step or from just a type
    const s = { uid: ++uid, type: src.type, content: src.content || "", file: src.file || "", self_destruct: src.self_destruct === undefined ? "" : String(src.self_destruct),
      pause_after: STEP_KINDS[src.type].action ? 0 : src.pause_after === undefined ? 10 : src.pause_after };
    s.custom = !PAUSES.includes(s.pause_after);
    s.unit = pauseUnit(s.pause_after);
    s.pauseText = String(s.pause_after / UNITS[s.unit]);
    return s;
  }
  const payloadSteps = () => ed.steps.map((s) => ({ type: s.type, ...(STEP_KINDS[s.type].action ? {} : STEP_KINDS[s.type].media ? { file: s.file, ...(s.self_destruct ? { self_destruct: s.self_destruct === "once" ? "once" : Number(s.self_destruct) } : {}) } : { content: s.content }), pause_after: s.pause_after }));
  const signature = () => JSON.stringify([ed.name, payloadSteps()]);
  const isDirty = () => !!ed && signature() !== ed.saved;

  function openEditor(w) {
    ed = { id: w ? w.id : null, name: w ? w.name : "", steps: w ? w.steps.map(stepFrom) : [], media: w ? { ...w.media } : {},
      saved: "", touched: false };
    ed.saved = w ? signature() : JSON.stringify(["", []]);
    renderEditor();
  }

  function validate() {
    const e = { name: "", top: "", steps: {}, count: 0 };
    if (!ed.name.trim()) { e.name = L("Bitte einen Namen eingeben.", "Enter a name."); e.count++; }
    if (!ed.steps.length) { e.top = L("Füge mindestens einen Schritt hinzu.", "Add at least one step."); e.count++; }
    for (const s of ed.steps) {
      const se = {};
      if (STEP_KINDS[s.type].action) {
        if (s !== ed.steps[ed.steps.length - 1]) se.content = L("„Nutzer blockieren“ muss der letzte Schritt sein.", "“Block user” must be the last step.");
      } else if (STEP_KINDS[s.type].media) {
        if (!s.file) se.content = L("Bitte eine Datei hochladen.", "Upload a file.");
        else if (ed.media[s.file] && ed.media[s.file].missing) se.content = L("Die Datei fehlt auf dem Server, bitte ersetzen.", "The file is missing on the server, please replace it.");
      } else if (!s.content.trim()) se.content = L("Der Text darf nicht leer sein.", "The text must not be empty.");
      else if (s.content.length > MAX_TEXT) se.content = L(`Der Text ist zu lang (${fmtN(s.content.length)} von höchstens ${fmtN(MAX_TEXT)} Zeichen).`, `The text is too long (${fmtN(s.content.length)} of at most ${fmtN(MAX_TEXT)} characters).`);
      if (!Number.isInteger(s.pause_after) || s.pause_after < 0 || s.pause_after > MAX_PAUSE) {
        se.pause = L("Die Pause muss eine ganze Zahl sein, höchstens 24 Stunden.", "The pause must be a whole number, 24 hours at most.");
      }
      if (se.content || se.pause) { e.steps[s.uid] = se; e.count += Object.keys(se).length; }
    }
    return e;
  }

  // --- editor: drawing ---

  const $e = (sel) => wfEl.querySelector(sel);

  function pauseControl(s) {
    const preset = (p) => `<option value="${p}" ${!s.custom && s.pause_after === p ? "selected" : ""}>${esc(p === 0 ? L("0 s (direkt)", "0 s (immediately)") : fmtDur(p))}</option>`;
    return `<div class="tg-pause"><label><span>${esc(L("Pause danach", "Pause after"))}</span>
        <select data-pause>${PAUSES.map(preset).join("")}<option value="custom" ${s.custom ? "selected" : ""}>${esc(L("Eigene Zeit …", "Custom time …"))}</option></select></label>
      ${s.custom ? `<span class="tg-custom"><input type="number" min="0" step="1" inputmode="numeric" data-pause-n value="${esc(s.pauseText)}" aria-label="${esc(L("Pause (Zahl)", "Pause (number)"))}">
        <select data-pause-unit aria-label="${esc(L("Einheit", "Unit"))}">${Object.keys(UNITS).map((u) =>
          `<option value="${u}" ${s.unit === u ? "selected" : ""}>${esc(u === "s" ? L("Sekunden", "seconds") : u === "min" ? L("Minuten", "minutes") : L("Stunden", "hours"))}</option>`).join("")}</select></span>` : ""}
      <span class="error" data-err="pause" role="alert"></span></div>`;
  }

  function stepBody(s) {
    const kind = STEP_KINDS[s.type];
    if (kind.action) {
      return `<div class="tg-warn">${esc(L("Nach diesem Schritt wird der Nutzer in Telegram blockiert und kann diesem Konto nicht mehr schreiben. Es wird nur blockiert: ohne Spam-Meldung und ohne den Chat zu löschen. Entsperren geht nur von Hand in Telegram.",
        "After this step the user is blocked on Telegram and can no longer write to this account. It only blocks: no spam report and the chat is not deleted. Unblocking is only possible by hand in Telegram."))}</div>
        <div class="tg-count"><span class="error" data-err="content" role="alert"></span></div>`;
    }
    if (!kind.media) {
      return `<textarea data-content rows="3" placeholder="${esc(L("Nachrichtentext …", "Message text …"))}" aria-label="${esc(L("Nachrichtentext", "Message text"))}">${esc(s.content)}</textarea>
        <div class="tg-count"><span class="error" data-err="content" role="alert"></span><span data-count>${fmtN(s.content.length)} / ${fmtN(MAX_TEXT)}</span></div>`;
    }
    const info = ed.media[s.file];
    const url = `${API}/media/${encodeURIComponent(s.file)}`;
    let shown = `<div class="tg-drop">${esc(L("Noch keine Datei", "No file yet"))}</div>`;
    if (s.file && info && !info.missing) {
      shown = s.type === "image"
        ? `<img src="${url}" alt="${esc(L("Vorschau", "Preview"))}">`
        : `<div><audio controls preload="metadata" src="${url}"></audio>${info.duration ? `<div class="muted">${esc(L("Dauer", "Length"))}: ${esc(String(info.duration).replace(".", K.lang === "de" ? "," : "."))} s</div>` : ""}</div>`;
    } else if (s.file) {
      shown = `<div class="tg-drop">${esc(L("Datei fehlt auf dem Server", "File is missing on the server"))}</div>`;
    }
    return `<div class="tg-media">${shown}<div>
        <input type="file" hidden data-file accept="${esc(kind.accept)}">
        <button type="button" class="btn small" data-act="pick">${icon("upload")}<span>${esc(s.file
          ? L(s.type === "image" ? "Bild ersetzen" : "Sprachmemo ersetzen", s.type === "image" ? "Replace image" : "Replace voice memo")
          : L("Datei wählen", "Choose file"))}</span></button>
        <div class="muted" data-up>${s.busy ? esc(L("Wird hochgeladen …", "Uploading …")) : `${esc(L("höchstens", "up to"))} ${kind.limit} MB`}</div></div></div>
      <label class="tg-once"><span>${esc(L("Anzeigedauer nach dem Öffnen", "Display time after opening"))}</span>
        <select data-selfdestruct>${selfDestructChoices(s.type).map(([v, de, en]) =>
          `<option value="${v}" ${s.self_destruct === v ? "selected" : ""}>${esc(L(de, en))}</option>`).join("")}</select></label>
      <div class="tg-count"><span class="error" data-err="content" role="alert"></span></div>`;
  }

  function stepCard(s, i, last) {
    return `<div class="tg-step" data-i="${i}" data-uid="${s.uid}">
        <div class="tg-step-head">
          <span class="tg-grip" data-grip title="${esc(L("Ziehen zum Verschieben", "Drag to reorder"))}" aria-hidden="true">⠿</span>
          <span class="tg-step-num">${i + 1}</span>
          <span class="tg-step-type"><span aria-hidden="true">${STEP_KINDS[s.type].emoji}</span> ${esc(kindName(s.type))}</span>
          <span class="tg-step-tools">
            ${iconBtn("arrowUp", `data-act="up" ${i === 0 ? "disabled" : ""}`, L("Schritt nach oben", "Move step up"))}
            ${iconBtn("arrowDown", `data-act="down" ${last ? "disabled" : ""}`, L("Schritt nach unten", "Move step down"))}
            ${iconBtn("trash", 'data-act="remove"', L("Schritt löschen", "Delete step"))}
          </span></div>
        ${stepBody(s)}${STEP_KINDS[s.type].action ? "" : pauseControl(s)}</div>`;
  }

  function renderSteps() {
    const n = ed.steps.length;
    $e("[data-steps]").innerHTML = n
      ? ed.steps.map((s, i) => stepCard(s, i, i === n - 1) + (i < n - 1
        ? `<div class="tg-arrow" data-arrow="${i}" data-after="${i}"><b aria-hidden="true">↓</b> <span data-arrow-text></span></div>` : "")).join("")
      : `<div class="empty">${icon("message")}<b>${esc(L("Noch keine Schritte", "No steps yet"))}</b><span>${esc(L("Füge unten die erste Nachricht hinzu.", "Add the first message below."))}</span></div>`;
    K.hydrateIcons($e("[data-steps]"));
    paint();
  }

  // Everything that changes while typing is updated in place, so a text field never loses focus.
  function paint() {
    ed.steps.forEach((s, i) => {
      const arrow = $e(`[data-arrow="${i}"] [data-arrow-text]`);
      if (arrow) arrow.textContent = Number.isInteger(s.pause_after) && s.pause_after >= 0 && s.pause_after <= MAX_PAUSE
        ? (s.pause_after === 0 ? L("direkt weiter", "next one immediately") : L(`${fmtDur(s.pause_after)} Pause`, `${fmtDur(s.pause_after)} pause`)) : "?";
    });
    const n = ed.steps.length;
    $e("[data-total]").textContent = n
      ? L(`${n} ${n === 1 ? "Schritt" : "Schritte"} · Pausen pro Chat: ${fmtDur(pauseTotal(ed.steps))} (ohne die Sendezeit der Nachrichten)`,
          `${n} ${n === 1 ? "step" : "steps"} · pauses per chat: ${fmtDur(pauseTotal(ed.steps))} (not counting the time to send the messages)`)
      : "";
    $e("[data-dirty]").classList.toggle("hidden", !isDirty());
    const err = ed.touched ? validate() : { name: "", top: "", steps: {} };
    const setErr = (box, msg, field) => {
      if (!box) return;
      box.textContent = msg || "";
      if (field) { field.classList.toggle("tg-invalid", !!msg); field.setAttribute("aria-invalid", msg ? "true" : "false"); }
    };
    setErr($e('[data-err="name"]'), err.name, $e("[data-name]"));
    setErr($e('[data-err="top"]'), err.top);
    wfEl.querySelectorAll(".tg-step").forEach((card) => {
      const se = err.steps[card.dataset.uid] || {};
      setErr(card.querySelector('[data-err="content"]'), se.content, card.querySelector("[data-content]"));
      setErr(card.querySelector('[data-err="pause"]'), se.pause, card.querySelector("[data-pause-n]") || card.querySelector("[data-pause]"));
    });
  }

  function renderEditor() {
    injectWorkflowStyles();
    injectRunStyles();      // the warning box of the "block user" step lives there
    const el = wfEl;
    const actions = `<button class="btn" data-act="back">${icon("chevronLeft")}<span>${esc(L("Zurück zu den Abläufen", "Back to workflows"))}</span></button>
      <span class="tg-dirty hidden" data-dirty>● ${esc(L("Ungespeicherte Änderungen", "Unsaved changes"))}</span>
      <button class="btn primary" data-act="save">${icon("check")}<span>${esc(L("Ablauf speichern", "Save workflow"))}</span></button>`;
    el.innerHTML = head(ed.id ? L("Ablauf bearbeiten", "Edit workflow") : L("Neuer Ablauf", "New workflow"),
      L("Schritte anordnen, Pausen festlegen und speichern", "Arrange the steps, set the pauses and save"), actions) + `
      <div class="tg-editor">
        <div class="card tg-meta"><label><span>${esc(L("Name des Ablaufs", "Workflow name"))}</span>
          <input data-name maxlength="80" value="${esc(ed.name)}" placeholder="${esc(L("z. B. Workflow 1 – Neukontakt", "e.g. Workflow 1 – first contact"))}"></label>
          <p class="error" data-err="name" role="alert"></p><div class="tg-total" data-total></div></div>
        <p class="error" data-err="top" role="alert"></p>
        <div data-steps></div>
        <div class="tg-add">
          <button class="btn" type="button" data-act="add-toggle" aria-haspopup="menu" aria-expanded="false">${icon("plus")}<span>${esc(L("Nachricht hinzufügen", "Add message"))}</span></button>
        </div>
        <div class="tg-sr" aria-live="polite" data-live></div>
      </div>`;
    K.hydrateIcons(el);
    renderSteps();
    wireEditor(el);
  }

  const say = (text) => { const box = $e("[data-live]"); if (box) box.textContent = text; };

  function moveStep(from, to) {
    if (from === to || to < 0 || to >= ed.steps.length) return;
    const [s] = ed.steps.splice(from, 1);
    ed.steps.splice(to, 0, s);
    renderSteps();
    say(L(`Schritt ${from + 1} steht jetzt an Position ${to + 1}`, `Step ${from + 1} is now at position ${to + 1}`));
  }

  async function uploadFor(s, file) {
    const kind = STEP_KINDS[s.type];
    if (file.size > kind.limit * 1024 * 1024) throw new Error(`The file is too large (${kind.limit} MB at most for this type)`);
    s.busy = true;
    renderSteps();
    try {
      const fd = new FormData();
      fd.append("files", file);
      const info = (await K.api(`${API}/media`, { method: "POST", body: fd })).saved[0];
      if (info.kind !== kind.media) throw new Error(`The file is not a ${kind.media} file`);
      s.file = info.name;
      ed.media[info.name] = info;
    } finally {
      s.busy = false;
      renderSteps();
    }
  }

  async function saveWorkflow() {
    ed.touched = true;
    const e = validate();
    paint();
    if (e.count) {
      K.toast(L(`Bitte ${e.count === 1 ? "das markierte Feld" : "die markierten Felder"} korrigieren`, `Please fix the highlighted ${e.count === 1 ? "field" : "fields"}`), true);
      const first = wfEl.querySelector(".tg-invalid") || $e('[data-err="top"]');
      if (first && first.scrollIntoView) first.scrollIntoView({ block: "center" });
      if (first && first.focus) first.focus();
      return;
    }
    const body = { name: ed.name.trim(), steps: payloadSteps() };
    let saved;
    try {
      saved = ed.id ? await K.api(`${API}/workflows/${ed.id}`, { method: "PUT", body })
        : await K.api(`${API}/workflows`, { method: "POST", body });
    } catch (ex) {
      if (ex.message === "Not authenticated") return;
      if (/already exists/.test(ex.message)) { setNameError(errText(ex.message)); return; }
      throw ex;
    }
    ed.id = saved.id;
    ed.name = saved.name;
    ed.media = { ...ed.media, ...saved.media };
    ed.steps.forEach((s, i) => { s.content = saved.steps[i].content || s.content; });
    ed.saved = signature();
    ed.touched = false;
    $e("[data-name]").value = ed.name;
    K.toast(L("Ablauf gespeichert", "Workflow saved"));
    paint();
  }
  function setNameError(msg) {
    const box = $e('[data-err="name"]'), field = $e("[data-name]");
    box.textContent = msg;
    field.classList.add("tg-invalid");
    field.focus();
  }

  function leaveEditor() {
    if (isDirty() && !confirm(L("Ungespeicherte Änderungen verwerfen?", "Discard the unsaved changes?"))) return;
    ed = null;
    return renderWorkflowList();
  }

  function wireEditor(el) {
    const stepOf = (node) => { const c = node.closest(".tg-step"); return c ? ed.steps.find((s) => s.uid === +c.dataset.uid) : null; };
    const closeMenu = () => {
      const menu = el.querySelector(".tg-menu"), toggle = $e('[data-act="add-toggle"]');
      if (menu) menu.remove();
      if (toggle) toggle.setAttribute("aria-expanded", "false");
    };

    el.onclick = act(async (e) => {
      const btn = e.target.closest("[data-act], [data-add]");
      if (!e.target.closest(".tg-add")) closeMenu();
      if (!btn || btn.disabled) return;
      if (btn.dataset.add) {
        closeMenu();
        const added = stepFrom({ type: btn.dataset.add }), end = ed.steps[ed.steps.length - 1];
        if (end && STEP_KINDS[end.type].action && !STEP_KINDS[added.type].action) ed.steps.splice(ed.steps.length - 1, 0, added);   // "block user" stays last
        else ed.steps.push(added);
        renderSteps();
        const card = el.querySelector(`.tg-step[data-uid="${added.uid}"]`);
        card.scrollIntoView({ block: "center" });
        const first = card.querySelector("textarea, [data-act=pick]");
        if (first) first.focus();
        return;
      }
      const kind = btn.dataset.act;
      if (kind === "back") return leaveEditor();
      if (kind === "save") return saveWorkflow();
      if (kind === "add-toggle") {
        if (el.querySelector(".tg-menu")) return closeMenu();
        btn.setAttribute("aria-expanded", "true");
        btn.insertAdjacentHTML("afterend", `<div class="tg-menu" role="menu">${Object.entries(STEP_KINDS).filter(([t, k]) => !(k.action && ed.steps.some((x) => x.type === t))).map(([t, k]) =>
          `<button type="button" role="menuitem" data-add="${t}">${k.emoji} ${esc(L(k.de, k.en))}</button>`).join("")}</div>`);
        return el.querySelector(".tg-menu button").focus();
      }
      const s = stepOf(btn);
      if (!s) return;
      const i = ed.steps.indexOf(s);
      if (kind === "up" || kind === "down") {
        const to = i + (kind === "up" ? -1 : 1);
        moveStep(i, to);
        const moved = el.querySelector(`.tg-step[data-i="${to}"]`);
        const same = moved && moved.querySelector(`[data-act="${kind}"]`);
        (same && !same.disabled ? same : moved.querySelector('[data-act="up"]:not([disabled]), [data-act="down"]:not([disabled])')).focus();
      } else if (kind === "remove") {
        const filled = STEP_KINDS[s.type].action ? "" : STEP_KINDS[s.type].media ? s.file : s.content.trim();
        if (filled && !confirm(L(`Schritt ${i + 1} (${kindName(s.type)}) löschen?`, `Delete step ${i + 1} (${kindName(s.type)})?`))) return;
        ed.steps.splice(i, 1);
        renderSteps();
        say(L(`Schritt ${i + 1} gelöscht`, `Step ${i + 1} deleted`));
      } else if (kind === "pick") {
        btn.closest(".tg-media").querySelector("[data-file]").click();
      }
    });
    el.onkeydown = (e) => { if (e.key === "Escape" && el.querySelector(".tg-menu")) { closeMenu(); $e('[data-act="add-toggle"]').focus(); } };

    el.oninput = (e) => {
      const t = e.target;
      if (t.matches("[data-name]")) ed.name = t.value;
      else if (t.matches("[data-content]")) {
        const s = stepOf(t);
        s.content = t.value;
        t.closest(".tg-step").querySelector("[data-count]").textContent = `${fmtN(s.content.length)} / ${fmtN(MAX_TEXT)}`;
      } else if (t.matches("[data-pause-n]")) {
        const s = stepOf(t);
        s.pauseText = t.value;
        s.pause_after = /^\d+$/.test(t.value.trim()) ? Number(t.value.trim()) * UNITS[s.unit] : null;
      } else return;
      paint();
    };
    el.onchange = act(async (e) => {
      const t = e.target;
      const s = stepOf(t);
      if (t.matches("[data-pause]")) {
        if (t.value === "custom") {
          s.custom = true;
          s.unit = pauseUnit(s.pause_after);
          s.pauseText = String(s.pause_after / UNITS[s.unit]);
        } else {
          s.custom = false;
          s.pause_after = +t.value;
        }
        renderSteps();
        const again = el.querySelector(`.tg-step[data-uid="${s.uid}"] [data-pause-n]`);
        if (again) again.focus();
      } else if (t.matches("[data-pause-unit]")) {
        s.unit = t.value;
        s.pause_after = /^\d+$/.test(s.pauseText.trim()) ? Number(s.pauseText.trim()) * UNITS[s.unit] : null;
        paint();
      } else if (t.matches("[data-selfdestruct]")) {
        s.self_destruct = t.value;
        paint();
      } else if (t.matches("[data-file]") && t.files.length) {
        const file = t.files[0];
        t.value = "";
        await uploadFor(s, file);
      }
    });

    // Drag and drop (native HTML5). A card is only draggable while its grip is held, so text can still be selected.
    let from = null;
    const clearMarks = () => el.querySelectorAll(".dragging, .drop-before, .drop-after").forEach((n) => n.classList.remove("dragging", "drop-before", "drop-after"));
    const dropSpot = (e) => {   // {index, after} of the card (or arrow) under the pointer
      const card = e.target.closest(".tg-step"), arrow = e.target.closest(".tg-arrow");
      if (card) {
        const r = card.getBoundingClientRect();
        return { node: card, index: +card.dataset.i, after: e.clientY > r.top + r.height / 2 };
      }
      return arrow ? { node: el.querySelector(`.tg-step[data-i="${arrow.dataset.after}"]`), index: +arrow.dataset.after, after: true } : null;
    };
    el.onmousedown = (e) => { const c = e.target.closest(".tg-step"); if (c) c.draggable = !!e.target.closest("[data-grip]"); };
    el.onmouseup = () => el.querySelectorAll(".tg-step[draggable=true]").forEach((c) => { c.draggable = false; });
    el.ondragstart = (e) => {
      const card = e.target.closest ? e.target.closest(".tg-step") : null;
      if (!card || !card.draggable) { e.preventDefault(); return; }
      from = +card.dataset.i;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(from));
      card.classList.add("dragging");
    };
    el.ondragover = (e) => {
      if (from === null) return;
      e.preventDefault();
      const spot = dropSpot(e);
      el.querySelectorAll(".drop-before, .drop-after").forEach((n) => n.classList.remove("drop-before", "drop-after"));
      if (spot && spot.node) spot.node.classList.add(spot.after ? "drop-after" : "drop-before");
    };
    el.ondrop = (e) => {
      if (from === null) return;
      e.preventDefault();
      const spot = dropSpot(e), start = from;
      from = null;
      clearMarks();
      if (!spot) return;
      let to = spot.index + (spot.after ? 1 : 0);      // insert position before removal
      if (to > start) to--;
      moveStep(start, to);
    };
    el.ondragend = () => { from = null; clearMarks(); el.querySelectorAll(".tg-step[draggable=true]").forEach((c) => { c.draggable = false; }); };
  }

  // An unsaved workflow survives a tab change (the draft stays in memory); closing or reloading the page asks first.
  window.addEventListener("beforeunload", (e) => { if (isDirty()) { e.preventDefault(); e.returnValue = ""; } });

  // --- Versand (runs): the start form and the live panel -------------------------------------------
  // For the selected account the tab shows the LIVE PANEL while a run is active or paused (and after it ended, until
  // the operator starts something new), otherwise the START form. State lives in `rs`; events from the module
  // WebSocket update it, and every (re)connect re-reads it from GET /runs, so a reload or a dropped socket loses nothing.

  const RUN_ACTIVE = ["queued", "running", "paused"];
  const RUN_STATUS = {   // run status -> [badge class, German, English]
    queued: ["ok", "AKTIV", "ACTIVE"], running: ["ok", "AKTIV", "ACTIVE"], paused: ["warn", "PAUSIERT", "PAUSED"],
    stopped: ["bad", "GESTOPPT", "STOPPED"], done: ["info", "FERTIG", "FINISHED"], error: ["bad", "ABGEBROCHEN", "ABORTED"],
  };
  const RUN_CHAT_STATUS = {   // run chat status -> [badge class, German, English]
    pending: ["queued", "Wartet", "Waiting"], running: ["info", "In Arbeit", "Working"], done: ["ok", "Fertig", "Done"],
    error: ["bad", "Fehler", "Error"], skipped: ["warn", "Übersprungen", "Skipped"],
  };
  const RUN_LIST = 100;       // rows of the result list per page
  const stepEmoji = (type) => (STEP_KINDS[type] ? STEP_KINDS[type].emoji : "?");

  const rs = { account: null, workflows: [], run: null, recvAt: 0, listOffset: null, onlyErrors: false, listSeq: 0,
    form: { workflow: "", onError: "next", retries: 3, autoResume: false, markRead: true } };
  const activeRuns = new Map();   // run id -> state, for every run that is not finished (feeds the sidebar badge)
  let runsEl = null, tickTimer = null, listTimer = null;

  function injectRunStyles() {
    if (document.getElementById("tg-run-style")) return;
    const style = document.createElement("style");
    style.id = "tg-run-style";
    style.textContent = `
      .tg-section { padding: 16px 18px; margin-bottom: 16px; }
      .tg-section h3 { margin: 0 0 12px; font-size: 15px; }
      .tg-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
      .tg-flow-box { margin-top: 12px; padding: 12px 14px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--border); }
      .tg-row { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; }
      .tg-row label { display: grid; gap: 6px; }
      .tg-start { position: sticky; bottom: 0; z-index: 3; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
        padding: 14px 18px; margin-top: 16px; background: var(--surface); border: 1px solid var(--border-strong, var(--border));
        border-radius: var(--radius); box-shadow: var(--shadow-lg); }
      .tg-start-info { flex: 1; min-width: 200px; }
      .tg-start-info b { font-size: 16px; }
      .tg-start .error { min-height: 0; margin: 4px 0 0; }
      .tg-go { min-width: 180px; justify-content: center; font-size: 17px; letter-spacing: .06em; font-weight: 700; padding: 14px 28px; }
      .tg-warn { padding: 10px 14px; border-radius: 10px; margin-bottom: 14px; background: var(--warn-soft); color: var(--warn); font-size: 13.5px; }
      .tg-risk { display: grid; gap: 4px; padding: 11px 14px; border-radius: 10px; margin-top: 16px; background: var(--info-soft);
        color: var(--text); border: 1px solid var(--border); font-size: 13px; }
      .tg-risk span:empty { display: none; }
      .tg-flood { padding: 10px 14px; border-radius: 10px; margin: 0 0 14px; font-size: 13.5px; background: var(--danger-soft); color: var(--danger); }
      .tg-sum { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; margin: 0 0 14px; }
      .tg-sum dt { color: var(--muted); }
      .tg-sum dd { margin: 0; overflow-wrap: anywhere; }
      .tg-live { padding: 18px 20px; margin-bottom: 16px; }
      .tg-live-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
      .tg-live-top > div { min-width: 0; overflow-wrap: anywhere; }
      .tg-live-top .badge { font-size: 14px; padding: 6px 14px; font-weight: 700; letter-spacing: .05em; }
      .tg-note { padding: 10px 14px; border-radius: 10px; margin: 0 0 14px; font-size: 13.5px; background: var(--warn-soft); color: var(--warn); }
      .tg-now { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
      .tg-tile { padding: 12px 14px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--border); min-width: 0; }
      .tg-tile small { display: block; color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
      .tg-tile b { font-size: 15px; overflow-wrap: anywhere; }
      .tg-tile .muted { font-size: 12.5px; }
      .tg-count { font-variant-numeric: tabular-nums; }
      .tg-progress { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
      .tg-track { flex: 1; height: 14px; border-radius: 99px; background: var(--surface-3); overflow: hidden; }
      .tg-track i { display: block; height: 100%; width: 0; border-radius: 99px; background: var(--accent); transition: width .4s ease; }
      .tg-progress b { min-width: 48px; text-align: right; font-size: 18px; }
      .tg-counts { display: flex; gap: 8px 22px; flex-wrap: wrap; font-size: 14px; }
      .tg-counts .ok { color: var(--ok); }
      .tg-counts .bad { color: var(--danger); }
      .tg-meta-line { margin-top: 10px; font-size: 12.5px; color: var(--muted); }
      tr.tg-cur td { background: var(--accent-soft); }
      .tg-list-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 14px 16px 10px; }
      .tg-list-head h3 { margin: 0; font-size: 15px; }
      .tg-ls { overflow-x: auto; max-height: 460px; overflow-y: auto; }
      .tg-section .tb-search { min-width: 0; }
      @media (max-width: 900px) { .tg-now { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 760px) {
        .tg-now { grid-template-columns: 1fr; }
        .tg-section .acc-toolbar { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
        .tg-section .tg-date { min-width: 0; }
        .tg-start { flex-direction: column; align-items: stretch; }
        .tg-go { width: 100%; }
        .tg-live { padding: 14px; }
        .tg-live-top .actions { width: 100%; }
        .tg-live-top .actions .btn { flex: 1; justify-content: center; }
      }`;
    document.head.appendChild(style);
  }

  const estimate = (steps, n) => {   // seconds of pauses for n chats; sending time is not counted
    const per = steps.reduce((sum, s) => sum + (s.pause_after || 0), 0);
    return n > 0 ? per * n - (steps.length ? steps[steps.length - 1].pause_after || 0 : 0) : 0;
  };
  const flowHtml = (steps) => steps.map((s, i) => `<span role="img" aria-label="${esc(kindName(s.type))}" title="${esc(kindName(s.type))}">${stepEmoji(s.type)}</span>`
    + (i < steps.length - 1 ? `<span class="tg-wf-gap" title="${esc(L("Pause danach", "Pause after"))}">${esc(fmtDur(s.pause_after))}</span>` : "")).join("");
  const accountOf = (id) => accountList.find((a) => a.id === id);
  const accountLine = (a) => `${a.label || a.phone} · ${(STATUS[a.status] || STATUS.offline)[K.lang === "de" ? 1 : 2]}${[...activeRuns.values()].some((r) => r.account_id === a.id) ? " ▶" : ""}`;

  // --- sidebar badge: a Telegram run is active ---

  function renderBadge() {
    const head = document.querySelector('.sb-group[data-module="telegram"] .sb-group-head');
    if (!head) return;
    let badge = head.querySelector("[data-run-badge]");
    if (!badge) {
      badge = document.createElement("span");
      badge.dataset.runBadge = "";
      badge.className = "sb-badge";
      head.insertBefore(badge, head.querySelector(".sb-chev"));
    }
    const runs = [...activeRuns.values()], running = runs.filter((r) => r.status !== "paused").length;
    badge.textContent = !runs.length ? "" : running ? `▶ ${runs.length > 1 ? runs.length : L("Läuft", "Running")}` : `⏸ ${runs.length > 1 ? runs.length : L("Pausiert", "Paused")}`;
    badge.classList.toggle("warn", !!runs.length && !running);
    badge.title = runs.length ? L("Ein Telegram-Durchlauf ist aktiv", "A Telegram run is active") : "";
  }

  function track(state) {   // remember a run (from an event or a REST answer) for the badge
    if (RUN_ACTIVE.includes(state.status)) activeRuns.set(state.id, state); else activeRuns.delete(state.id);
    renderBadge();
  }

  // Re-read what the page shows: runs that are active, and the run on screen (after a reload or a reconnect).
  async function syncRuns() {
    try {
      const list = await K.api(`${API}/runs?status=${RUN_ACTIVE.join(",")}&limit=50`);
      activeRuns.clear();
      list.items.forEach((r) => activeRuns.set(r.id, r));
      renderBadge();
      if (runsEl && rs.run) setRun(await K.api(`${API}/runs/${rs.run.id}`));
      else if (runsEl) {      // a run was started elsewhere meanwhile: show it instead of the form
        const r = list.items.find((x) => x.account_id === rs.account);
        if (r) setRun(r);
        paintAccountBar();
      }
      if (dashEl) loadDash().catch(() => {});
      if (histEl) (hs.detail === null ? loadList() : loadDetailChats()).catch(() => {});
    } catch { /* offline or signed out: the next reconnect tries again */ }
  }

  function onRun(m) {
    track(m);
    if (dashEl) dashRunEvent(m);
    if (histEl) histRunEvent(m);
    if (!runsEl) return;
    if (rs.run && rs.run.id === m.id) setRun(m);
    else if (!rs.run && RUN_ACTIVE.includes(m.status) && m.account_id === rs.account) setRun(m);   // started elsewhere
    paintAccountBar();
  }

  // --- the tab ---

  async function openRuns(el) {
    injectStyles();
    injectWorkflowStyles();
    injectRunStyles();
    runsEl = el;
    el.innerHTML = head(L("Versand", "Sending"), L("Ablauf und Chats wählen, dann starten", "Pick a workflow and chats, then start"));
    const [accounts, workflows, active] = await Promise.all([K.api(`${API}/accounts`), K.api(`${API}/workflows`),
      K.api(`${API}/runs?status=${RUN_ACTIVE.join(",")}&limit=50`)]);
    if (runsEl !== el) return;
    accountList = accounts;
    rs.workflows = workflows;
    rs.run = null;
    activeRuns.clear();
    active.items.forEach((r) => activeRuns.set(r.id, r));
    renderBadge();
    if (!accounts.length) {
      el.insertAdjacentHTML("beforeend", `<div class="empty">${icon("send")}<b>${esc(L("Noch kein Konto verbunden", "No account linked yet"))}</b>
        <span>${esc(L("Verbinde zuerst ein Telegram-Konto im Bereich Konten.", "Link a Telegram account in the Accounts section first."))}</span></div>`);
      return;
    }
    if (!accounts.some((a) => a.id === rs.account)) {
      const busy = active.items[0] && active.items[0].account_id;
      rs.account = busy || (accounts.find((a) => a.status === "online") || accounts[0]).id;
    }
    el.insertAdjacentHTML("beforeend", `<div class="acc-toolbar"><select data-run-account aria-label="${esc(L("Konto", "Account"))}"></select></div><div data-run-body></div>`);
    paintAccountBar();
    el.querySelector("[data-run-account]").onchange = act(async (e) => { rs.account = +e.target.value; await pickRun(); });
    el.onclick = act(onRunsClick);
    el.onchange = (e) => { if (e.target.matches("[data-form]")) formChanged(e.target); };
    el.oninput = (e) => { if (e.target.matches("[data-form]")) formChanged(e.target); };
    tickTimer = setInterval(tick, 500);
    await pickRun();
  }

  function closeRuns() {
    runsEl = null;
    clearInterval(tickTimer);
    clearTimeout(listTimer);
    tickTimer = listTimer = null;
    if (formCtl) { formCtl.destroy(); formCtl = null; }
    rs.run = null;
  }

  function paintAccountBar() {
    const sel = runsEl && runsEl.querySelector("[data-run-account]");
    if (!sel) return;
    sel.innerHTML = accountList.map((a) => `<option value="${a.id}" ${a.id === rs.account ? "selected" : ""}>${esc(accountLine(a))}</option>`).join("");
  }

  // show the live panel when the selected account has an active run, otherwise the start form
  async function pickRun() {
    const list = await K.api(`${API}/runs?account_id=${rs.account}&status=${RUN_ACTIVE.join(",")}&limit=1`);
    if (!runsEl) return;
    rs.run = null;
    if (list.items.length) setRun(list.items[0]); else renderForm();
  }

  // a new state of the run on screen (event, REST answer): the first one of a run draws the panel, later ones paint it
  function setRun(state) {
    track(state);
    const fresh = !rs.run || rs.run.id !== state.id;
    rs.run = state;
    rs.recvAt = performance.now();
    if (fresh) {
      rs.listOffset = null;
      rs.onlyErrors = false;
      renderLive();
    } else {
      paintRun();
      if (state.status !== "paused") refreshRunChats();
    }
  }

  async function onRunsClick(e) {
    const btn = e.target.closest("[data-run-act]");
    if (!btn || btn.disabled) return;
    const kind = btn.dataset.runAct;
    if (kind === "start") return startClicked();
    if (kind === "preset") return formCtl.selectStatus(btn.dataset.status, true);
    if (kind === "new") { rs.run = null; return renderForm(); }
    if (kind === "errors") {
      rs.onlyErrors = !rs.onlyErrors;
      rs.listOffset = null;
      btn.textContent = rs.onlyErrors ? L("Alle Chats zeigen", "Show all chats") : L("Nur Fehler zeigen", "Show errors only");
      return loadRunChats();
    }
    if (kind === "prev" || kind === "next") { rs.listOffset = +btn.dataset.offset; return loadRunChats(); }
    if (kind === "stop" && !confirm(L("Durchlauf wirklich stoppen? Chats, die noch nicht dran waren, werden übersprungen.",
                                      "Really stop the run? Chats that have not been reached are skipped."))) return;
    btn.disabled = true;
    try {
      setRun(await K.api(`${API}/runs/${rs.run.id}/${kind}`, { method: "POST" }));   // pause | resume | stop | restart
    } finally {
      btn.disabled = false;
    }
  }

  // --- start form ---

  function renderForm() {
    if (formCtl) { formCtl.destroy(); formCtl = null; }
    const body = runsEl && runsEl.querySelector("[data-run-body]");
    if (!body) return;
    const f = rs.form;
    if (!rs.workflows.some((w) => String(w.id) === f.workflow)) f.workflow = "";
    body.innerHTML = `
      <div data-offline></div>
      <div class="card tg-section"><h3>${esc(L("1 · Ablauf", "1 · Workflow"))}</h3>
        ${rs.workflows.length
          ? `<label><span>${esc(L("Welcher Ablauf soll gesendet werden?", "Which workflow should be sent?"))}</span>
              <select data-form="workflow"><option value="">${esc(L("– Ablauf wählen –", "– choose a workflow –"))}</option>
                ${rs.workflows.map((w) => `<option value="${w.id}" ${String(w.id) === f.workflow ? "selected" : ""}>${esc(w.name)}</option>`).join("")}</select></label>
            <div data-wf-info></div>`
          : `<p class="hint">${esc(L("Es gibt noch keinen Ablauf.", "There is no workflow yet."))} <a href="#telegram-workflows">${esc(L("Ablauf erstellen", "Create a workflow"))}</a></p>`}
        <label class="inline" style="margin-top:12px"><input type="checkbox" data-form="markRead" ${f.markRead ? "checked" : ""}>
          <span>${esc(L("Chat vor dem Ablauf öffnen (Nachrichten des Kontakts als gelesen markieren)", "Open the chat before the workflow (mark the contact's messages as read)"))}</span></label>
        <p class="hint" style="margin:6px 0 0">${esc(L("Der Kontakt sieht dann die zwei Haken (gelesen), bevor die erste Nachricht kommt – wie bei einer Person, die den Chat öffnet.",
          "The contact then sees the two ticks (read) before the first message arrives, like a person who opens the chat."))}</p>
      </div>
      <div class="card tg-section"><h3>${esc(L("2 · Chats auswählen", "2 · Select chats"))}</h3>
        <div class="tg-presets">
          <button type="button" class="btn small" data-run-act="preset" data-status="pending">🟢 ${esc(L("Alle unbearbeiteten", "All not processed"))}</button>
          <button type="button" class="btn small" data-run-act="preset" data-status="error">❌ ${esc(L("Alle mit Fehler", "All with errors"))}</button>
          <button type="button" class="btn small" data-run-act="preset" data-status="paused">⏸️ ${esc(L("Alle pausierten", "All paused"))}</button>
          <button type="button" class="btn small" data-run-act="preset" data-status="">${esc(L("Alle Chats", "All chats"))}</button>
        </div>
        <div data-table></div>
      </div>
      <div class="card tg-section"><h3>${esc(L("3 · Bei einem Fehler", "3 · When a chat fails"))}</h3>
        <div class="tg-row">
          <label><span>${esc(L("Was soll passieren?", "What should happen?"))}</span>
            <select data-form="onError">
              <option value="next" ${f.onError === "next" ? "selected" : ""}>${esc(L("Fehler merken und mit dem nächsten Chat weitermachen", "Note the error and go on with the next chat"))}</option>
              <option value="retry" ${f.onError === "retry" ? "selected" : ""}>${esc(L("Den Schritt erneut versuchen", "Try the step again"))}</option></select></label>
          <label data-retries class="${f.onError === "retry" ? "" : "hidden"}"><span>${esc(L("Wiederholungen", "Retries"))}</span>
            <input type="number" data-form="retries" min="1" max="5" value="${f.retries}" style="width:90px"></label>
        </div>
        <p class="hint" style="margin:10px 0 0">${esc(L("Ein Fehler stoppt nie den ganzen Durchlauf. Ist es auch nach den Wiederholungen nicht möglich, wird der Chat als Fehler markiert und der Durchlauf geht weiter.",
          "An error never stops the whole run. If it still fails after the retries, the chat is marked as an error and the run goes on."))}</p>
      </div>
      <div class="card tg-section"><h3>${esc(L("4 · Bei Verbindungsabbruch", "4 · When the connection drops"))}</h3>
        <label class="inline"><input type="checkbox" data-form="autoResume" ${f.autoResume ? "checked" : ""}>
          <span>${esc(L("Automatisch fortsetzen, sobald das Konto wieder online ist", "Resume automatically as soon as the account is online again"))}</span></label>
        <p class="hint" style="margin:10px 0 0">${esc(L("Reißt die Verbindung ab oder endet die Sitzung, pausiert der Durchlauf an genau dieser Stelle. Ohne diese Option setzt du ihn selbst mit „Fortsetzen“ fort. Eine von dir gesetzte Pause wird nie automatisch aufgehoben.",
          "If the connection drops or the session ends, the run pauses at exactly that point. Without this option you resume it yourself. A pause you set yourself is never lifted automatically."))}</p>
      </div>
      <div class="tg-risk" role="note"><b>${esc(L("Hinweis zu Telegram-Limits", "About Telegram limits"))}</b>
        <span>${esc(L("Automatisierte Erstnachrichten von privaten Konten können dazu führen, dass Telegram das Konto einschränkt (FloodWait / PeerFlood). Empfehlung: Pausen größer als 0 Sekunden verwenden und nicht zu viele neue Kontakte auf einmal anschreiben.",
          "Automated first-contact messages from personal accounts can get the account limited by Telegram (FloodWait / PeerFlood). Recommendation: keep pauses above 0 seconds and do not write to too many new contacts at once."))}</span>
        <span data-risk-zero></span></div>
      <div class="tg-start">
        <div class="tg-start-info"><b data-start-count></b><div class="muted" data-start-est></div><p class="error" data-start-error></p></div>
        <button type="button" class="btn primary lg tg-go" data-run-act="start">${icon("play")}<span>START</span></button>
      </div>`;
    K.hydrateIcons(body);
    formCtl = chatTable(body.querySelector("[data-table]"), { accounts: accountList, account: rs.account, editable: false, onChange: paintStart });
    formCtl.reload().catch(() => {});
    paintForm();
  }

  const refreshForm = K.throttle(() => { if (formCtl) formCtl.reload().catch(() => {}); }, 1500);
  const chosenWorkflow = () => rs.workflows.find((w) => String(w.id) === rs.form.workflow);

  function formChanged(input) {
    const f = rs.form, key = input.dataset.form;
    if (key === "retries") f.retries = Math.min(5, Math.max(1, parseInt(input.value, 10) || 1));
    else if (key === "autoResume" || key === "markRead") f[key] = input.checked;
    else f[key] = input.value;
    if (key === "onError") runsEl.querySelector("[data-retries]").classList.toggle("hidden", f.onError !== "retry");
    if (key === "workflow") paintForm();
    paintStart();
  }

  function paintForm() {   // workflow summary + offline warning
    const box = runsEl && runsEl.querySelector("[data-wf-info]");
    const w = chosenWorkflow();
    if (box) {
      box.innerHTML = w ? `<div class="tg-flow-box"><div class="tg-wf-flow">${flowHtml(w.steps)}</div>
        <div class="muted" style="margin-top:8px">${esc(L(`${w.steps.length} ${w.steps.length === 1 ? "Schritt" : "Schritte"}`, `${w.steps.length} ${w.steps.length === 1 ? "step" : "steps"}`))}
        · ${esc(L("Pausen pro Chat", "Pauses per chat"))}: ${esc(fmtDur(w.steps.reduce((sum, s) => sum + s.pause_after, 0)))}</div></div>` : "";
    }
    const zero = runsEl && runsEl.querySelector("[data-risk-zero]");
    if (zero) {
      zero.textContent = w && w.steps.slice(0, -1).some((x) => x.pause_after === 0)
        ? L("Dieser Ablauf hat Schritte ohne Pause (0 Sekunden): Die Nachrichten gehen dann sofort hintereinander raus.",
            "This workflow has steps without a pause (0 seconds): the messages are sent straight after each other.") : "";
    }
    const acc = accountOf(rs.account), off = runsEl && runsEl.querySelector("[data-offline]");
    if (off) {
      off.innerHTML = acc && acc.status !== "online"
        ? `<div class="tg-warn">${esc(L(`Das Konto ${acc.label || acc.phone} ist nicht online. Verbinde es im Bereich Konten, sonst kann kein Durchlauf starten.`,
            `The account ${acc.label || acc.phone} is not online. Connect it in the Accounts section, otherwise no run can start.`))}</div>` : "";
    }
    paintStart();
  }

  function paintStart() {   // the counter and the time estimate next to START
    const count = runsEl && runsEl.querySelector("[data-start-count]");
    if (!count || !formCtl) return;
    const n = formCtl.selectedIds().length, w = chosenWorkflow();
    count.textContent = countText(n);
    runsEl.querySelector("[data-start-est]").textContent = w && n
      ? L(`Geschätzte Dauer: ca. ${fmtDur(estimate(w.steps, n))} (nur Pausen, ohne Sendezeit)`, `Estimated duration: about ${fmtDur(estimate(w.steps, n))} (pauses only, not counting sending time)`)
      : L("Wähle einen Ablauf und Chats.", "Pick a workflow and chats.");
    runsEl.querySelector("[data-start-error]").textContent = "";
  }

  // validation, then the summary the operator confirms
  function startClicked() {
    const w = chosenWorkflow(), ids = formCtl.selectedIds(), acc = accountOf(rs.account);
    const problem = !acc || acc.status !== "online" ? L("Das Konto ist nicht online. Bitte zuerst im Bereich Konten verbinden.", "The account is not online. Connect it in the Accounts section first.")
      : !w ? L("Bitte einen Ablauf wählen.", "Please choose a workflow.")
      : !ids.length ? L("Bitte mindestens einen Chat auswählen.", "Please select at least one chat.") : "";
    runsEl.querySelector("[data-start-error]").textContent = problem;
    if (problem) return;
    const f = rs.form;
    K.openModal(L("Versand starten?", "Start sending?"), `
      <dl class="tg-sum">
        <dt>${esc(L("Konto", "Account"))}</dt><dd>${esc(acc.label || acc.phone)}</dd>
        <dt>${esc(L("Ablauf", "Workflow"))}</dt><dd><b>${esc(w.name)}</b><div class="tg-wf-flow" style="margin-top:6px">${flowHtml(w.steps)}</div></dd>
        <dt>${esc(L("Chats", "Chats"))}</dt><dd><b>${esc(countText(ids.length))}</b></dd>
        <dt>${esc(L("Dauer", "Duration"))}</dt><dd>${esc(L(`ca. ${fmtDur(estimate(w.steps, ids.length))} (nur Pausen)`, `about ${fmtDur(estimate(w.steps, ids.length))} (pauses only)`))}</dd>
        <dt>${esc(L("Bei Fehler", "On error"))}</dt><dd>${esc(f.onError === "retry"
          ? L(`Schritt bis zu ${f.retries}× erneut versuchen, dann nächster Chat`, `retry the step up to ${f.retries} times, then the next chat`)
          : L("mit dem nächsten Chat weitermachen", "go on with the next chat"))}</dd>
        <dt>${esc(L("Chat öffnen", "Open the chat"))}</dt><dd>${esc(f.markRead
          ? L("Nachrichten des Kontakts vorher als gelesen markieren", "mark the contact's messages as read first")
          : L("nein, direkt senden", "no, send straight away"))}</dd>
        <dt>${esc(L("Verbindungsabbruch", "Connection drop"))}</dt><dd>${esc(f.autoResume
          ? L("automatisch fortsetzen, sobald das Konto wieder online ist", "resume automatically when the account is back")
          : L("pausieren, du setzt selbst fort", "pause, you resume yourself"))}</dd></dl>
      ${w.steps.some((x) => x.type === "block") ? `<div class="tg-warn">${esc(L(`Am Ende ${ids.length === 1 ? "wird" : "werden"} ${fmtN(ids.length)} Nutzer in Telegram blockiert.`, `At the end ${fmtN(ids.length)} ${ids.length === 1 ? "user is" : "users are"} blocked on Telegram.`))}</div>` : ""}
      <p class="hint">${esc(L("Die Chats werden nacheinander bearbeitet. Du kannst den Durchlauf jederzeit pausieren oder stoppen.", "The chats are worked one after another. You can pause or stop the run at any time."))}</p>
      <p class="error" data-go-error></p>
      <div class="actions"><button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>
        <button class="btn primary lg" type="button" data-go>${esc(L("Jetzt starten", "Start now"))}</button></div>`);
    K.$("#modal [data-go]").onclick = act(startRun);
  }

  async function startRun() {
    const w = chosenWorkflow(), ids = formCtl.selectedIds(), f = rs.form;
    const go = K.$("#modal [data-go]"), err = K.$("#modal [data-go-error]");
    go.disabled = true;
    try {
      const state = await K.api(`${API}/runs`, { method: "POST",
        body: { account_id: rs.account, workflow_id: w.id, chat_ids: ids, on_error: f.onError, retries: f.retries, auto_resume: f.autoResume, mark_read: f.markRead } });
      K.closeModal();
      rs.run = null;
      setRun(state);
    } catch (e) {
      if (e.message !== "Not authenticated") { err.textContent = errText(e.message); go.disabled = false; }
    }
  }

  // --- live panel ---

  function renderLive() {
    if (formCtl) { formCtl.destroy(); formCtl = null; }
    const body = runsEl && runsEl.querySelector("[data-run-body]");
    if (!body) return;
    const tile = (label, key) => `<div class="tg-tile"><small>${esc(label)}</small><div data-${key}></div></div>`;
    body.innerHTML = `
      <div class="card tg-live" data-live>
        <div class="tg-live-top"><div><span class="badge" data-badge></span> <b data-wf></b> <span class="muted" data-acc></span></div>
          <div class="actions" data-buttons></div></div>
        <p class="tg-note hidden" data-note></p>
        <p class="tg-flood hidden" data-flood></p>
        <div class="tg-now">${tile(L("Aktueller Chat", "Current chat"), "chat")}${tile(L("Aktueller Schritt", "Current step"), "step")}
          ${tile(L("Nächster Schritt", "Next step"), "next")}${tile(L("Nächste Aktion", "Next action"), "count")}</div>
        <div class="tg-progress"><div class="tg-track" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i data-fill></i></div><b data-pct></b></div>
        <div class="tg-counts" data-counts></div>
        <div class="tg-meta-line" data-meta></div>
      </div>
      <div class="card table-card">
        <div class="tg-list-head"><h3>${esc(L("Ergebnis je Chat", "Result per chat"))}</h3>
          <button type="button" class="btn small" data-run-act="errors" data-errors-btn>${esc(L("Nur Fehler zeigen", "Show errors only"))}</button></div>
        <div class="tg-ls"><table class="table tg-table"><thead><tr><th>#</th><th>Chat</th><th>Status</th><th>${esc(L("Schritte", "Steps"))}</th><th>${esc(L("Zeit", "Time"))}</th></tr></thead>
          <tbody data-list></tbody></table></div>
        <div class="acc-foot"><span data-list-showing></span><div class="pages" data-list-pager></div></div>
      </div>`;
    paintRun();
    loadRunChats().catch(() => {});
  }

  function paintRun() {
    const r = rs.run, box = runsEl && runsEl.querySelector("[data-live]");
    if (!r || !box) return;
    const $r = (key) => box.querySelector(`[data-${key}]`);
    const active = RUN_ACTIVE.includes(r.status), acc = accountOf(r.account_id);
    const [cls, de, en] = RUN_STATUS[r.status] || RUN_STATUS.error;
    $r("badge").className = `badge ${cls}`;
    $r("badge").textContent = L(de, en);
    $r("wf").textContent = r.workflow_name;
    $r("acc").textContent = acc ? `· ${acc.label || acc.phone}` : "";
    const btn = (kind, label, ic, extra = "") => `<button type="button" class="btn ${extra}" data-run-act="${kind}">${icon(ic)}<span>${esc(label)}</span></button>`;
    $r("buttons").innerHTML = r.status === "paused"
      ? btn("resume", L("Fortsetzen", "Resume"), "play", "primary") + btn("stop", L("Stoppen", "Stop"), "x", "danger")
      : active ? btn("pause", L("Pause", "Pause"), "pause") + btn("stop", L("Stoppen", "Stop"), "x", "danger")
      : btn("restart", L("Neustart", "Restart"), "refresh", "primary") + btn("new", L("Neuer Durchlauf", "New run"), "plus");
    K.hydrateIcons($r("buttons"));

    // a note when the run waits for something other than its own pause
    const ended = /^(Telegram ended this session|This Telegram account was (banned|deactivated))/.test(r.status_msg);
    const note = r.status === "paused" && r.status_msg ? esc(L(`Pausiert: ${errText(r.status_msg)}.`, `Paused: ${r.status_msg}.`))
        + (ended ? ` <a href="#telegram-accounts">${esc(L("Im Bereich Konten neu anmelden", "Log in again in the Accounts section"))}</a>` : "")
        + (r.auto_resume ? ` ${esc(L("Der Durchlauf wird automatisch fortgesetzt, sobald das Konto wieder online ist.", "The run resumes automatically as soon as the account is online again."))}` : "")
      : active && r.wait_kind === "flood" ? esc(L("Telegram verlangt eine Wartezeit (FloodWait). Es geht danach automatisch weiter.", "Telegram asks to wait (FloodWait). The run continues automatically afterwards."))
      : active && r.wait_kind === "retry" ? esc(L("Das Senden ist fehlgeschlagen, ein neuer Versuch folgt.", "Sending failed, another attempt follows."))
      : r.status === "error" ? esc(errText(r.status_msg || "")) : "";
    $r("note").innerHTML = note;
    $r("note").classList.toggle("hidden", !note);
    $r("flood").textContent = floodNote(r);
    $r("flood").classList.toggle("hidden", !r.peer_floods);

    $r("chat").innerHTML = r.chat ? `<b>${esc(r.chat.name)}</b>${r.chat.username ? `<div class="muted">@${esc(r.chat.username)}</div>` : ""}` : "—";
    $r("step").innerHTML = r.step ? `<b>${stepEmoji(r.step.type)} ${esc(kindName(r.step.type))}</b>
      <div class="muted">${esc(L(`Schritt ${r.step.index + 1} von ${r.steps_total}`, `Step ${r.step.index + 1} of ${r.steps_total}`))}</div>` : "—";
    $r("next").innerHTML = r.next_step_type ? `<b>${stepEmoji(r.next_step_type)} ${esc(kindName(r.next_step_type))}</b>
      ${r.step && r.step.index + 1 >= r.steps_total ? `<div class="muted">${esc(L("im nächsten Chat", "in the next chat"))}</div>` : ""}` : "—";

    const pct = r.percent;
    $r("fill").style.width = pct + "%";
    box.querySelector("[role=progressbar]").setAttribute("aria-valuenow", pct);
    $r("pct").textContent = pct + " %";
    $r("counts").innerHTML = `<span>${esc(L("Bearbeitet", "Processed"))} <b>${fmtN(r.processed)} / ${fmtN(r.total)}</b></span>
      <span class="ok">${esc(L("Erfolgreich", "Successful"))} <b>${fmtN(r.success)}</b></span>
      <span class="bad">${esc(L("Fehler", "Errors"))} <b>${fmtN(r.errors)}</b></span>
      ${r.skipped ? `<span>${esc(L("Übersprungen", "Skipped"))} <b>${fmtN(r.skipped)}</b></span>` : ""}`;
    $r("meta").textContent = `${L("Gestartet", "Started")}: ${K.fmtDate(r.started_at)}${r.finished_at ? ` · ${L("Beendet", "Ended")}: ${K.fmtDate(r.finished_at)}` : ""}`;
    tick();
  }

  // PeerFlood: Telegram stopped this account from writing to new people; the chats that hit it are listed as errors
  const floodNote = (r) => (r.peer_floods ? L(
    `Telegram hat dieses Konto für Nachrichten an neue Kontakte eingeschränkt (PeerFlood, ${fmtN(r.peer_floods)} ${r.peer_floods === 1 ? "Chat" : "Chats"}). Weitere Sendungen schlagen wahrscheinlich ebenfalls fehl: Pausen erhöhen oder einige Stunden warten.`,
    `Telegram limited this account for writing to new people (PeerFlood, ${fmtN(r.peer_floods)} ${r.peer_floods === 1 ? "chat" : "chats"}). Further sends will probably fail too: raise the pauses or wait a few hours.`) : "");

  // The countdown is anchored at the moment the state arrived (seconds_remaining), so it does not depend on the clocks
  // of server and browser agreeing. While the run is paused the server reports the frozen rest and it is not counted down.
  function tick() {
    const r = rs.run, node = runsEl && runsEl.querySelector("[data-live] [data-count]");
    if (!r || !node) return;
    const active = RUN_ACTIVE.includes(r.status), has = active && r.seconds_remaining != null;
    const left = !has ? null : r.status === "paused" ? r.seconds_remaining : Math.max(0, r.seconds_remaining - (performance.now() - rs.recvAt) / 1000);
    const text = left === null ? (r.status === "running" || r.status === "queued" ? L("sendet gerade …", "sending …") : "—")
      : left > 59 ? `in ${fmtDur(Math.ceil(left))}`
      : L(`in ${Math.ceil(left)} ${Math.ceil(left) === 1 ? "Sekunde" : "Sekunden"}`, `in ${Math.ceil(left)} ${Math.ceil(left) === 1 ? "second" : "seconds"}`);
    const label = r.wait_kind === "flood" ? L("Wartezeit von Telegram", "Telegram wait") : r.wait_kind === "retry" ? L("neuer Versuch", "next attempt")
      : r.wait_kind === "pause" ? L("Pause bis zum nächsten Schritt", "pause before the next step") : "";
    const html = `<b class="tg-count">${esc(text)}</b>${r.status === "paused" && left !== null ? `<div class="muted">${esc(L("pausiert", "paused"))}</div>`
      : label ? `<div class="muted">${esc(label)}</div>` : ""}`;
    if (node.innerHTML !== html) node.innerHTML = html;
  }

  // --- per-chat result list ---

  function refreshRunChats() {
    if (!listTimer) listTimer = setTimeout(() => { listTimer = null; loadRunChats().catch(() => {}); }, 600);
  }

  async function loadRunChats() {
    const r = rs.run, tbody = runsEl && runsEl.querySelector("[data-list]");
    if (!r || !tbody) return;
    const my = ++rs.listSeq;
    const follow = RUN_ACTIVE.includes(r.status) && !rs.onlyErrors;    // keep the working chat in view
    const offset = rs.listOffset !== null ? rs.listOffset : follow ? Math.max(0, Math.min(r.processed - 10, r.total - RUN_LIST)) : 0;
    const p = new URLSearchParams({ limit: RUN_LIST, offset });
    if (rs.onlyErrors) p.set("status", "error");
    const res = await K.api(`${API}/runs/${r.id}/chats?${p}`);
    if (my !== rs.listSeq || !runsEl || !rs.run || rs.run.id !== r.id) return;
    tbody.innerHTML = res.items.length ? res.items.map((c) => {
      const [bcls, de, en] = RUN_CHAT_STATUS[c.status] || RUN_CHAT_STATUS.pending;
      return `<tr class="${c.status === "running" ? "tg-cur" : ""}"><td>${fmtN(c.position + 1)}</td>
        <td><b>${esc(c.display_name)}</b>${c.username ? `<div class="muted">@${esc(c.username)}</div>` : ""}</td>
        <td><span class="badge ${bcls}">${esc(L(de, en))}</span>${c.error_reason ? `<div class="muted">${esc(errText(c.error_reason))}</div>` : ""}</td>
        <td>${c.steps_done} / ${r.steps_total}</td><td class="nowrap">${esc(c.processed_at ? K.fmtDate(c.processed_at) : "—")}</td></tr>`;
    }).join("") : `<tr><td colspan="5"><div class="empty"><b>${esc(rs.onlyErrors ? L("Keine Fehler", "No errors") : L("Keine Chats", "No chats"))}</b></div></td></tr>`;
    const from = res.total ? offset + 1 : 0, to = Math.min(res.total, offset + RUN_LIST);
    runsEl.querySelector("[data-list-showing]").textContent = L(`${fmtN(from)}–${fmtN(to)} von ${fmtN(res.total)}`, `${fmtN(from)}–${fmtN(to)} of ${fmtN(res.total)}`);
    runsEl.querySelector("[data-list-pager]").innerHTML = res.total > RUN_LIST
      ? `<button class="pg" data-run-act="prev" data-offset="${Math.max(0, offset - RUN_LIST)}" ${offset <= 0 ? "disabled" : ""} aria-label="${esc(L("Zurück", "Previous"))}">${icon("chevronLeft")}</button>
         <button class="pg" data-run-act="next" data-offset="${offset + RUN_LIST}" ${to >= res.total ? "disabled" : ""} aria-label="${esc(L("Weiter", "Next"))}">${icon("chevronRight")}</button>` : "";
    K.hydrateIcons(runsEl.querySelector("[data-list-pager]"));
  }

  // --- Dashboard and Verlauf (history) ------------------------------------------------------------
  // The Dashboard shows GET /stats (one call, optionally for one account) and follows the module WebSocket:
  // a "run" event repaints the live card at once and re-reads the numbers (throttled). The Verlauf tab lists every run
  // with filters, opens one run as a per-chat result list, exports CSV and cleans up old runs.

  const fmtStamp = (iso) => (iso ? new Date(iso).toLocaleString(K.lang === "de" ? "de-DE" : "en-GB",
    { year: "2-digit", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—");
  const fmtSec = (sec) => (sec === null || sec === undefined ? "—" : fmtDur(sec));
  const localDay = (day, end) => new Date(`${day}T${end ? "23:59:59.999" : "00:00:00"}`).toISOString();   // the operator's local day
  const runBadge = (status) => {
    const [cls, de, en] = RUN_STATUS[status] || RUN_STATUS.error;
    return `<span class="badge ${cls}">${esc(L(de, en))}</span>`;
  };
  const runSummary = (r) => `${fmtN(r.success)} ${L("erfolgreich", "successful")} · ${fmtN(r.errors)} ${L("Fehler", "errors")}`
    + (r.skipped ? ` · ${fmtN(r.skipped)} ${L("abgebrochen", "aborted")}` : "");

  function injectDashStyles() {
    if (document.getElementById("tg-dash-style")) return;
    const style = document.createElement("style");
    style.id = "tg-dash-style";
    style.textContent = `
      .kpi-grid.tg-kpis { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
      .tg-kpis .kpi-value { font-size: 26px; overflow-wrap: anywhere; }
      .tg-kpis .kpi-value.long { font-size: 17px; line-height: 1.3; }
      .tg-kpis .kpi-foot { overflow-wrap: anywhere; }
      .tg-dash-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
      .tg-legend { display: flex; gap: 16px; font-size: 12.5px; color: var(--text-2); margin-bottom: 8px; }
      .tg-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }
      .tg-legend .ok i { background: var(--chart-bar); }
      .tg-legend .bad i { background: var(--danger); }
      .chart .bar-fail { fill: var(--danger); }
      a.btn { text-decoration: none; }
      .tg-hist tbody tr[data-run] { cursor: pointer; }
      .tg-hist tbody tr[data-run]:hover td { background: var(--surface-2); }
      .tg-hist td.tg-wf-cell { max-width: 280px; overflow-wrap: anywhere; }
      .tg-hist td.num, .tg-hist th.num { text-align: right; font-variant-numeric: tabular-nums; }
      .tg-hist-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
      .tg-hist-head .grow { flex: 1; }
      .tg-reason { max-width: 320px; overflow-wrap: anywhere; }
      .tg-form-grid { display: grid; gap: 12px; }
      @media (max-width: 1000px) { .tg-dash-grid { grid-template-columns: minmax(0, 1fr); } }`;
    document.head.appendChild(style);
  }

  // --- Dashboard ---

  const ds = { account: "", days: 14, data: null, seq: 0 };
  let dashEl = null;

  function dashKpis(s) {
    const a = s.active_run, last = s.last_run;
    const none = L("Keiner", "None");
    return [
      { label: L("Alle Chats", "All chats"), value: fmtN(s.chats.total), iconName: "message", tone: "info",
        foot: esc(L(`${fmtN(s.accounts)} ${s.accounts === 1 ? "Konto" : "Konten"}, ${fmtN(s.accounts_online)} online`,
          `${fmtN(s.accounts)} ${s.accounts === 1 ? "account" : "accounts"}, ${fmtN(s.accounts_online)} online`)) },
      { label: L("Noch nicht bearbeitet", "Not processed yet"), value: fmtN(s.chats.unprocessed), iconName: "clock", tone: "warn",
        foot: esc(L("Warten auf einen Durchlauf", "Waiting for a run")) },
      { label: L("Bereits bearbeitet", "Already processed"), value: fmtN(s.chats.processed), iconName: "checkCircle", tone: "ok",
        foot: esc(L("Ablauf vollständig gesendet", "Workflow fully sent")) },
      { label: L("Chats mit Fehlern", "Chats with errors"), value: fmtN(s.chats.errors), iconName: "alert", tone: "danger",
        foot: esc(L("Fehlergrund im Verlauf", "Reason in the history")) },
      { label: L("Laufender Ablauf", "Running workflow"), value: a ? esc(a.workflow_name) : esc(none), iconName: "play", tone: "accent", long: !!a,
        foot: a ? esc(`${L("Durchlauf", "Run")} #${a.id} · ${(RUN_STATUS[a.status] || RUN_STATUS.error)[K.lang === "de" ? 1 : 2]}`) : esc(L("Gerade läuft nichts", "Nothing running")) },
      { label: L("Erfolgreiche Sendungen", "Successful sends"), value: fmtN(s.sends.successful), iconName: "send", tone: "ok",
        foot: esc(L(`${fmtN(s.sends.messages)} Nachrichten insgesamt`, `${fmtN(s.sends.messages)} messages in total`)) },
      { label: L("Fehlgeschlagene Sendungen", "Failed sends"), value: fmtN(s.sends.failed), iconName: "ban", tone: "danger",
        foot: esc(L("Chats, die mit Fehler endeten", "Chats that ended in an error")) },
      { label: L("Antworten", "Replies"), value: fmtN(s.chats.replied), iconName: "message", tone: "info",
        foot: esc(L("Chats, die geantwortet haben", "Chats that answered")) },
      { label: L("Letzter Durchlauf", "Last run"), value: last ? esc(K.fmtDate(last.finished_at || last.started_at)) : "—", iconName: "clock", tone: "info", long: !!last,
        foot: last ? `${runBadge(last.status)} ${esc(runSummary(last))}` : esc(L("Noch kein Durchlauf beendet", "No run finished yet")) },
      { label: L("Aktueller Chat", "Active chat"), value: a && a.chat ? esc(a.chat.name) : "—", iconName: "user", tone: "accent", long: true,
        foot: a && a.step ? esc(`${stepEmoji(a.step.type)} ${kindName(a.step.type)} · ${L("Schritt", "step")} ${a.step.index + 1}/${a.steps_total}`) : esc(a ? L("Wartet", "Waiting") : L("Kein aktiver Chat", "No active chat")) },
      { label: L("Fortschritt", "Progress"), value: a ? `${a.percent} %` : "—", iconName: "percent", tone: "accent",
        foot: a ? esc(`${fmtN(a.processed)} / ${fmtN(a.total)} ${L("Chats", "chats")}`) : esc(L("Kein Durchlauf aktiv", "No run active")) },
    ];
  }

  const kpiHtml = (k) => K.kpiTile(k).replace('class="kpi-value"', `class="kpi-value${k.long ? " long" : ""}"`);

  function liveCard(a) {
    if (!a) return `<div class="card tg-section"><h3>${esc(L("Aktueller Durchlauf", "Current run"))}</h3>
      <div class="empty">${icon("play")}<b>${esc(L("Es läuft gerade kein Durchlauf", "No run is active right now"))}</b>
        <span><a href="#telegram-runs">${esc(L("Zum Versand", "Go to Sending"))}</a></span></div></div>`;
    const acc = accountOf(a.account_id);
    return `<div class="card tg-live" data-dash-live>
      <div class="tg-live-top"><div>${runBadge(a.status)} <b>${esc(a.workflow_name)}</b>
        <span class="muted">· ${esc(L("Durchlauf", "Run"))} #${a.id}${acc ? ` · ${esc(acc.label || acc.phone)}` : ""}</span></div>
        <a class="btn small" href="#telegram-runs">${esc(L("Zum Versand", "Go to Sending"))}</a></div>
      ${a.peer_floods ? `<p class="tg-flood">${esc(floodNote(a))}</p>` : ""}
      ${a.status === "paused" && a.status_msg ? `<p class="tg-note">${esc(L(`Pausiert: ${errText(a.status_msg)}`, `Paused: ${a.status_msg}`))}</p>` : ""}
      <div class="tg-now">
        <div class="tg-tile"><small>${esc(L("Aktueller Chat", "Current chat"))}</small>${a.chat ? `<b>${esc(a.chat.name)}</b>${a.chat.username ? `<div class="muted">@${esc(a.chat.username)}</div>` : ""}` : "—"}</div>
        <div class="tg-tile"><small>${esc(L("Aktueller Schritt", "Current step"))}</small>${a.step ? `<b>${stepEmoji(a.step.type)} ${esc(kindName(a.step.type))}</b>
          <div class="muted">${esc(L(`Schritt ${a.step.index + 1} von ${a.steps_total}`, `Step ${a.step.index + 1} of ${a.steps_total}`))}</div>` : "—"}</div>
        <div class="tg-tile"><small>${esc(L("Nächster Schritt", "Next step"))}</small>${a.next_step_type ? `<b>${stepEmoji(a.next_step_type)} ${esc(kindName(a.next_step_type))}</b>` : "—"}</div>
        <div class="tg-tile"><small>${esc(L("Dauer", "Duration"))}</small><b>${esc(fmtSec(a.duration_seconds))}</b></div>
      </div>
      <div class="tg-progress"><div class="tg-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${a.percent}"><i style="width:${a.percent}%"></i></div><b>${a.percent} %</b></div>
      <div class="tg-counts"><span>${esc(L("Bearbeitet", "Processed"))} <b>${fmtN(a.processed)} / ${fmtN(a.total)}</b></span>
        <span class="ok">${esc(L("Erfolgreich", "Successful"))} <b>${fmtN(a.success)}</b></span>
        <span class="bad">${esc(L("Fehler", "Errors"))} <b>${fmtN(a.errors)}</b></span></div></div>`;
  }

  function lastRunCard(r) {
    const row = (label, value) => `<dt>${esc(label)}</dt><dd>${value}</dd>`;
    return `<div class="card tg-section"><h3>${esc(L("Letzter Durchlauf", "Last run"))}</h3>
      ${r ? `<dl class="tg-sum">${row(L("Ablauf", "Workflow"), `<b>${esc(r.workflow_name)}</b>`)}
        ${row("Status", runBadge(r.status))}
        ${row(L("Start", "Started"), esc(fmtStamp(r.started_at)))}${row(L("Ende", "Ended"), esc(fmtStamp(r.finished_at)))}
        ${row(L("Dauer", "Duration"), esc(fmtSec(r.duration_seconds)))}
        ${row(L("Ergebnis", "Result"), esc(`${fmtN(r.total)} ${L("ausgewählt", "selected")} · ${runSummary(r)}`))}</dl>
        <button type="button" class="btn small" data-dash-act="detail" data-id="${r.id}">${esc(L("Details im Verlauf", "Details in the history"))}</button>`
        : `<div class="empty">${icon("clock")}<b>${esc(L("Noch kein Durchlauf beendet", "No run has finished yet"))}</b></div>`}</div>`;
  }

  function paintDash() {
    const s = ds.data, host = dashEl && dashEl.querySelector("[data-dash]");
    if (!s || !host) return;
    host.innerHTML = `<div class="kpi-grid tg-kpis">${dashKpis(s).map(kpiHtml).join("")}</div>
      <div data-dash-live-host>${liveCard(s.active_run)}</div>
      <div class="tg-dash-grid">
        <div class="card tg-section"><div class="card-head"><div><h3>${esc(L("Sendungen pro Tag", "Sends per day"))}</h3></div>
          <select data-dash-days aria-label="${esc(L("Zeitraum", "Period"))}">${[7, 14, 30].map((n) => `<option value="${n}" ${n === ds.days ? "selected" : ""}>${esc(L(`Letzte ${n} Tage`, `Last ${n} days`))}</option>`).join("")}</select></div>
          <div class="tg-legend"><span class="ok"><i></i>${esc(L("Erfolgreich", "Successful"))}</span><span class="bad"><i></i>${esc(L("Fehlgeschlagen", "Failed"))}</span></div>
          <div class="chart" data-dash-chart></div></div>
        ${lastRunCard(s.last_run)}
      </div>`;
    K.hydrateIcons(host);
    drawSendsChart();
  }

  // the live card alone, repainted from a WebSocket event
  function paintDashLive() {
    const host = dashEl && dashEl.querySelector("[data-dash-live-host]");
    if (!host || !ds.data) return;
    host.innerHTML = liveCard(ds.data.active_run);
    K.hydrateIcons(host);
  }

  const niceStep = (max) => {
    if (max <= 4) return 1;
    const raw = max / 4, mag = 10 ** Math.floor(Math.log10(raw)), norm = raw / mag;
    return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  };

  // Two stacked series (successful, failed) per UTC day, drawn as inline SVG like the Jaumo chart.
  function drawSendsChart() {
    const el = dashEl && dashEl.querySelector("[data-dash-chart]");
    if (!el || !ds.data) return;
    const data = ds.data.per_day, total = (d) => d.successful + d.failed;
    const day = (iso, opts) => new Date(iso + "T00:00:00").toLocaleDateString(K.lang === "de" ? "de-DE" : "en-GB", opts);
    const W = el.clientWidth || 600, H = el.clientHeight || 240, m = { t: 10, r: 4, b: 26, l: 40 };
    const iw = Math.max(10, W - m.l - m.r), ih = H - m.t - m.b;
    const maxV = Math.max(0, ...data.map(total)), step = niceStep(maxV), top = step * Math.max(1, Math.ceil(maxV / step));
    const y = (v) => m.t + ih - (v / top) * ih, base = m.t + ih;
    const band = iw / Math.max(1, data.length), bw = Math.max(4, Math.min(34, band * 0.62));
    const every = Math.max(1, Math.ceil(data.length / Math.max(1, Math.floor(iw / 54))));
    let grid = "", axis = "", cols = "";
    for (let v = 0; v <= top; v += step) {
      grid += `<line x1="${m.l}" x2="${m.l + iw}" y1="${y(v)}" y2="${y(v)}"/>`;
      axis += `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    data.forEach((d, i) => {
      const x0 = m.l + i * band, x = x0 + (band - bw) / 2;
      const okTop = y(d.successful), allTop = y(total(d));
      if ((data.length - 1 - i) % every === 0) axis += `<text x="${x0 + band / 2}" y="${H - 6}" text-anchor="middle">${esc(day(d.date, { day: "numeric", month: "short" }))}</text>`;
      cols += `<g class="col" data-i="${i}"><rect class="band" x="${x0 + 1}" y="${m.t}" width="${Math.max(1, band - 2)}" height="${ih}" rx="6"/>`
        + (d.successful ? `<rect class="bar" x="${x}" y="${okTop}" width="${bw}" height="${base - okTop}" rx="3"/>` : "")
        + (d.failed ? `<rect class="bar bar-fail" x="${x}" y="${allTop}" width="${bw}" height="${okTop - allTop}" rx="3"/>` : "") + `</g>`;
    });
    const sum = data.reduce((n, d) => n + total(d), 0);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L(`Sendungen pro Tag, letzte ${data.length} Tage`, `Sends per day, last ${data.length} days`))}">
        <g class="grid">${grid}</g><g>${cols}</g><g class="axis">${axis}</g></svg>
      ${sum ? "" : `<div class="chart-empty">${esc(L("In diesem Zeitraum wurde nichts gesendet", "Nothing was sent in this period"))}</div>`}`;
    const tip = K.$("#chart-tip");
    el.querySelectorAll(".col").forEach((g) => {
      g.addEventListener("mousemove", (e) => {
        const d = data[+g.dataset.i], row = (l, v) => `<div class="tip-row"><span>${esc(l)}</span><b>${fmtN(v)}</b></div>`;
        tip.innerHTML = `<div class="tip-title">${esc(day(d.date, { weekday: "short", day: "numeric", month: "short" }))}</div>
          ${row(L("Erfolgreich", "Successful"), d.successful)}${row(L("Fehlgeschlagen", "Failed"), d.failed)}`;
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

  async function loadDash() {
    const my = ++ds.seq;
    const p = new URLSearchParams({ days: ds.days });
    if (ds.account) p.set("account_id", ds.account);
    const s = await K.api(`${API}/stats?${p}`);
    if (my !== ds.seq || !dashEl) return;
    ds.data = s;
    paintDash();
  }
  const reloadDash = K.throttle(() => { loadDash().catch(() => {}); }, 1500);
  window.addEventListener("resize", K.debounce(() => { if (dashEl) drawSendsChart(); }, 200));

  // a run changed: show it in the live card at once, the other numbers follow
  function dashRunEvent(m) {
    if (!ds.data || (ds.account && +ds.account !== m.account_id)) return;
    const a = ds.data.active_run;
    if (RUN_ACTIVE.includes(m.status)) ds.data.active_run = m;
    else if (a && a.id === m.id) ds.data.active_run = null;
    paintDashLive();
    reloadDash();
  }

  async function openDashboard(el) {
    injectStyles();
    injectRunStyles();
    injectDashStyles();
    dashEl = el;
    accountList = await K.api(`${API}/accounts`);
    if (dashEl !== el) return;
    if (ds.account && !accountList.some((a) => String(a.id) === ds.account)) ds.account = "";
    el.innerHTML = head("Telegram", L("Übersicht über Chats, Sendungen und den laufenden Durchlauf", "Overview of chats, sends and the current run"))
      + `<div class="acc-toolbar"><select data-dash-account aria-label="${esc(L("Konto", "Account"))}"><option value="">${esc(L("Alle Konten", "All accounts"))}</option>
        ${accountList.map((a) => `<option value="${a.id}" ${String(a.id) === ds.account ? "selected" : ""}>${esc(a.label || a.phone)}</option>`).join("")}</select></div><div data-dash></div>`;
    el.onchange = act(async (e) => {
      if (e.target.matches("[data-dash-account]")) ds.account = e.target.value;
      else if (e.target.matches("[data-dash-days]")) ds.days = +e.target.value;
      else return;
      await loadDash();
    });
    el.onclick = (e) => {
      const btn = e.target.closest("[data-dash-act=detail]");
      if (btn) { hs.detail = +btn.dataset.id; location.hash = "#telegram-history"; }
    };
    await loadDash();
  }


  // --- Verlauf (history) ---

  const hs = { f: { workflow: "", account: "", status: "", from: "", to: "" }, page: 0, per: 25, workflows: [], seq: 0,
    detail: null, run: null, onlyErrors: false, dpage: 0, dseq: 0 };
  let histEl = null;
  const HIST_DETAIL = 100;       // rows of the per-chat list per page
  const HIST_STATUS = [["", "Alle Status", "All statuses"], ["done", "Fertig", "Finished"], ["stopped", "Gestoppt", "Stopped"],
    ["error", "Abgebrochen", "Aborted"], ["queued,running,paused", "Aktiv", "Active"]];

  const histFilters = () => {
    const p = new URLSearchParams(), f = hs.f;
    if (f.workflow) p.set("workflow_id", f.workflow);
    if (f.account) p.set("account_id", f.account);
    if (f.status) p.set("status", f.status);
    if (f.from) p.set("date_from", localDay(f.from));
    if (f.to) p.set("date_to", localDay(f.to, true));
    return p;
  };

  async function openHistory(el) {
    injectStyles();
    injectRunStyles();
    injectDashStyles();
    histEl = el;
    const [accounts, workflows] = await Promise.all([K.api(`${API}/accounts`), K.api(`${API}/workflows`)]);
    if (histEl !== el) return;
    accountList = accounts;
    hs.workflows = workflows;
    el.onclick = act(onHistClick);
    el.onchange = act(onHistChange);
    el.oninput = (e) => { if (e.target.matches("[data-hf]")) hs.f[e.target.dataset.hf] = e.target.value; };
    if (hs.detail) await showDetail(hs.detail); else await showList();
  }

  // the list of runs

  async function showList() {
    hs.detail = hs.run = null;
    if (!histEl) return;
    const f = hs.f, opt = (v, label, cur) => `<option value="${esc(v)}" ${String(v) === String(cur) ? "selected" : ""}>${esc(label)}</option>`;
    histEl.innerHTML = head(L("Verlauf", "History"), L("Alle bisherigen Durchläufe", "All previous runs"),
      `<a class="btn" data-hist-export download href="#">${icon("download")}<span>${esc(L("CSV exportieren", "Export CSV"))}</span></a>
       <button type="button" class="btn danger" data-hist-act="cleanup">${icon("trash")}<span>${esc(L("Alte Durchläufe löschen", "Clean up old runs"))}</span></button>`)
      + `<div class="acc-toolbar">
        <select data-hf="workflow" aria-label="${esc(L("Ablauf", "Workflow"))}">${opt("", L("Alle Abläufe", "All workflows"), f.workflow)}${hs.workflows.map((w) => opt(w.id, w.name, f.workflow)).join("")}</select>
        <select data-hf="account" aria-label="${esc(L("Konto", "Account"))}">${opt("", L("Alle Konten", "All accounts"), f.account)}${accountList.map((a) => opt(a.id, a.label || a.phone, f.account)).join("")}</select>
        <select data-hf="status" aria-label="Status">${HIST_STATUS.map(([v, de, en]) => opt(v, L(de, en), f.status)).join("")}</select>
        <label class="tg-date"><span>${esc(L("von", "from"))}</span><input type="date" data-hf="from" value="${esc(f.from)}"></label>
        <label class="tg-date"><span>${esc(L("bis", "to"))}</span><input type="date" data-hf="to" value="${esc(f.to)}"></label>
        <button class="btn ghost" type="button" data-hist-act="reset">${esc(L("Filter zurücksetzen", "Reset filters"))}</button></div>
      <div class="card table-card"><div style="overflow-x:auto"><table class="table tg-table tg-hist"><thead><tr>
        <th>${esc(L("Start", "Start"))}</th><th>${esc(L("Ende", "End"))}</th><th>${esc(L("Ablauf", "Workflow"))}</th>
        <th class="num">${esc(L("Gewählt", "Selected"))}</th><th class="num">${esc(L("Erfolgreich", "Successful"))}</th><th class="num">${esc(L("Fehler", "Errors"))}</th>
        <th class="num" title="${esc(L("Chats, die nicht mehr bearbeitet wurden", "Chats that were not worked on any more"))}">${esc(L("Abgebrochen", "Aborted"))}</th>
        <th>${esc(L("Dauer", "Duration"))}</th><th>Status</th><th></th></tr></thead><tbody data-hist-rows></tbody></table></div>
        <div class="acc-foot"><span data-hist-showing></span><div class="pages" data-hist-pager></div></div></div>`;
    K.hydrateIcons(histEl);
    await loadList();
  }

  async function loadList() {
    const my = ++hs.seq, p = histFilters();
    histEl.querySelector("[data-hist-export]").href = `${API}/runs/export.csv?${p}`;
    p.set("limit", hs.per);
    p.set("offset", hs.page * hs.per);
    const res = await K.api(`${API}/runs?${p}`);
    if (my !== hs.seq || !histEl || hs.detail) return;
    const pages = Math.max(1, Math.ceil(res.total / hs.per));
    if (hs.page >= pages) { hs.page = pages - 1; return loadList(); }
    const acc = (id) => { const a = accountOf(id); return a ? (a.label || a.phone) : "—"; };
    histEl.querySelector("[data-hist-rows]").innerHTML = res.items.length ? res.items.map((r) => `<tr data-run="${r.id}">
      <td class="nowrap">${esc(fmtStamp(r.started_at || r.created_at))}</td><td class="nowrap">${esc(fmtStamp(r.finished_at))}</td>
      <td class="tg-wf-cell"><b>${esc(r.workflow_name)}</b><div class="muted">#${r.id} · ${esc(acc(r.account_id))}</div></td>
      <td class="num">${fmtN(r.total)}</td><td class="num">${fmtN(r.success)}</td><td class="num">${fmtN(r.errors)}</td><td class="num">${fmtN(r.skipped)}</td>
      <td class="nowrap">${esc(fmtSec(r.duration_seconds))}</td><td>${runBadge(r.status)}</td>
      <td class="nowrap">${iconBtn("eye", `data-hist-act="open" data-id="${r.id}"`, L("Details", "Details"))}${RUN_ACTIVE.includes(r.status) ? ""
        : iconBtn("trash", `data-hist-act="delete" data-id="${r.id}"`, L("Durchlauf löschen", "Delete run"))}</td></tr>`).join("")
      : `<tr><td colspan="10"><div class="empty">${icon("clock")}<b>${esc(L("Keine Durchläufe", "No runs"))}</b></div></td></tr>`;
    const from = res.total ? hs.page * hs.per + 1 : 0, to = Math.min(res.total, (hs.page + 1) * hs.per);
    histEl.querySelector("[data-hist-showing]").textContent = L(`${fmtN(from)}–${fmtN(to)} von ${fmtN(res.total)}`, `${fmtN(from)}–${fmtN(to)} of ${fmtN(res.total)}`);
    histEl.querySelector("[data-hist-pager]").innerHTML = pages > 1
      ? `<button class="pg" data-hist-act="page" data-to="${hs.page - 1}" ${hs.page <= 0 ? "disabled" : ""} aria-label="${esc(L("Zurück", "Previous"))}">${icon("chevronLeft")}</button>
         <button class="pg" data-hist-act="page" data-to="${hs.page + 1}" ${hs.page >= pages - 1 ? "disabled" : ""} aria-label="${esc(L("Weiter", "Next"))}">${icon("chevronRight")}</button>` : "";
    K.hydrateIcons(histEl);
  }

  // one run: summary and the result of every chat

  async function showDetail(id) {
    hs.detail = id;
    hs.onlyErrors = false;
    hs.dpage = 0;
    try {
      hs.run = await K.api(`${API}/runs/${id}`);
    } catch (e) {
      hs.detail = null;
      if (e.message === "Not authenticated") throw e;
      K.toast(errText(e.message), true);
      return showList();
    }
    if (!histEl) return;
    histEl.innerHTML = `<div data-detail-head></div>
      <div class="card table-card"><div class="tg-list-head"><h3>${esc(L("Ergebnis je Chat", "Result per chat"))}</h3>
        <button type="button" class="btn small" data-hist-act="errors" data-errors-btn>${esc(L("Nur Fehler zeigen", "Show errors only"))}</button></div>
        <div class="tg-ls"><table class="table tg-table"><thead><tr><th>#</th><th>Chat</th><th>${esc(L("Zeit", "Time"))}</th><th>${esc(L("Ergebnis", "Result"))}</th>
          <th>${esc(L("Schritte", "Steps"))}</th><th>${esc(L("Fehlergrund", "Error reason"))}</th></tr></thead><tbody data-detail-rows></tbody></table></div>
        <div class="acc-foot"><span data-detail-showing></span><div class="pages" data-detail-pager></div></div></div>`;
    paintDetailHead();
    await loadDetailChats();
  }

  function paintDetailHead() {
    const r = hs.run, box = histEl && histEl.querySelector("[data-detail-head]");
    if (!r || !box) return;
    const acc = accountOf(r.account_id), active = RUN_ACTIVE.includes(r.status);
    const tile = (label, html) => `<div class="tg-tile"><small>${esc(label)}</small>${html}</div>`;
    box.innerHTML = `<div class="tg-hist-head"><button type="button" class="btn" data-hist-act="back">${icon("chevronLeft")}<span>${esc(L("Zurück zum Verlauf", "Back to history"))}</span></button>
        <div class="grow"></div>
        <a class="btn" download href="${API}/runs/${r.id}/export.csv">${icon("download")}<span>${esc(L("CSV exportieren", "Export CSV"))}</span></a>
        ${active ? `<a class="btn primary" href="#telegram-runs">${esc(L("Zum Versand", "Go to Sending"))}</a>`
          : `<button type="button" class="btn danger" data-hist-act="delete" data-id="${r.id}">${icon("trash")}<span>${esc(L("Durchlauf löschen", "Delete run"))}</span></button>`}</div>
      <div class="card tg-live"><div class="tg-live-top"><div><h2 style="display:inline;font-size:18px">${esc(r.workflow_name)}</h2>
        <span class="muted">· ${esc(L("Durchlauf", "Run"))} #${r.id}${acc ? ` · ${esc(acc.label || acc.phone)}` : ""}</span></div>${runBadge(r.status)}</div>
        ${r.status_msg && !active ? `<p class="tg-note">${esc(errText(r.status_msg))}</p>` : ""}
        <div class="tg-now">${tile(L("Start", "Started"), `<b>${esc(fmtStamp(r.started_at || r.created_at))}</b>`)}${tile(L("Ende", "Ended"), `<b>${esc(fmtStamp(r.finished_at))}</b>`)}
          ${tile(L("Dauer", "Duration"), `<b>${esc(fmtSec(r.duration_seconds))}</b>`)}${tile(L("Ausgewählt", "Selected"), `<b>${fmtN(r.total)}</b>`)}</div>
        <div class="tg-counts"><span class="ok">${esc(L("Erfolgreich", "Successful"))} <b>${fmtN(r.success)}</b></span>
          <span class="bad">${esc(L("Fehler", "Errors"))} <b>${fmtN(r.errors)}</b></span>
          <span>${esc(L("Abgebrochen", "Aborted"))} <b>${fmtN(r.skipped)}</b></span></div></div>`;
    K.hydrateIcons(box);
  }

  async function loadDetailChats() {
    const r = hs.run, tbody = histEl && histEl.querySelector("[data-detail-rows]");
    if (!r || !tbody) return;
    const my = ++hs.dseq, p = new URLSearchParams({ limit: HIST_DETAIL, offset: hs.dpage * HIST_DETAIL });
    if (hs.onlyErrors) p.set("status", "error");
    const res = await K.api(`${API}/runs/${r.id}/chats?${p}`);
    if (my !== hs.dseq || !histEl || hs.detail !== r.id) return;
    tbody.innerHTML = res.items.length ? res.items.map((c) => {
      const [bcls, de, en] = RUN_CHAT_STATUS[c.status] || RUN_CHAT_STATUS.pending;
      return `<tr class="${c.status === "running" ? "tg-cur" : ""}"><td>${fmtN(c.position + 1)}</td>
        <td><b>${esc(c.display_name)}</b>${c.username ? `<div class="muted">@${esc(c.username)}</div>` : ""}</td>
        <td class="nowrap">${esc(fmtStamp(c.processed_at || c.started_at))}</td><td><span class="badge ${bcls}">${esc(L(de, en))}</span></td>
        <td>${c.steps_done} / ${r.steps_total}</td><td class="tg-reason">${esc(c.error_reason ? errText(c.error_reason) : "")}</td></tr>`;
    }).join("") : `<tr><td colspan="6"><div class="empty"><b>${esc(hs.onlyErrors ? L("Keine Fehler", "No errors") : L("Keine Chats", "No chats"))}</b></div></td></tr>`;
    const from = res.total ? hs.dpage * HIST_DETAIL + 1 : 0, to = Math.min(res.total, (hs.dpage + 1) * HIST_DETAIL);
    histEl.querySelector("[data-detail-showing]").textContent = L(`${fmtN(from)}–${fmtN(to)} von ${fmtN(res.total)}`, `${fmtN(from)}–${fmtN(to)} of ${fmtN(res.total)}`);
    histEl.querySelector("[data-detail-pager]").innerHTML = res.total > HIST_DETAIL
      ? `<button class="pg" data-hist-act="dpage" data-to="${hs.dpage - 1}" ${hs.dpage <= 0 ? "disabled" : ""} aria-label="${esc(L("Zurück", "Previous"))}">${icon("chevronLeft")}</button>
         <button class="pg" data-hist-act="dpage" data-to="${hs.dpage + 1}" ${to >= res.total ? "disabled" : ""} aria-label="${esc(L("Weiter", "Next"))}">${icon("chevronRight")}</button>` : "";
    K.hydrateIcons(histEl.querySelector("[data-detail-pager]"));
  }

  // actions

  async function onHistChange(e) {
    if (!e.target.matches("[data-hf]")) return;
    hs.f[e.target.dataset.hf] = e.target.value;
    hs.page = 0;
    await loadList();
  }

  async function onHistClick(e) {
    const btn = e.target.closest("[data-hist-act]");
    if (!btn) {
      const row = e.target.closest("tr[data-run]");
      if (row && !hs.detail && !e.target.closest("a, button")) await showDetail(+row.dataset.run);
      return;
    }
    if (btn.disabled) return;
    const kind = btn.dataset.histAct;
    if (kind === "open") return showDetail(+btn.dataset.id);
    if (kind === "back") return showList();
    if (kind === "page") { hs.page = +btn.dataset.to; return loadList(); }
    if (kind === "dpage") { hs.dpage = +btn.dataset.to; return loadDetailChats(); }
    if (kind === "reset") { hs.f = { workflow: "", account: "", status: "", from: "", to: "" }; hs.page = 0; return showList(); }
    if (kind === "errors") {
      hs.onlyErrors = !hs.onlyErrors;
      hs.dpage = 0;
      btn.textContent = hs.onlyErrors ? L("Alle Chats zeigen", "Show all chats") : L("Nur Fehler zeigen", "Show errors only");
      return loadDetailChats();
    }
    if (kind === "cleanup") return cleanupDialog();
    if (kind === "delete") {
      if (!confirm(L("Diesen Durchlauf mit allen Ergebnissen je Chat löschen? Die Chats selbst bleiben unverändert.",
                     "Delete this run with all its per-chat results? The chats themselves stay unchanged."))) return;
      await K.api(`${API}/runs/${btn.dataset.id}`, { method: "DELETE" });
      K.toast(L("Durchlauf gelöscht", "Run deleted"));
      return showList();
    }
  }

  function cleanupDialog() {
    K.openModal(L("Alte Durchläufe löschen", "Clean up old runs"), `
      <form id="tg-cleanup" class="tg-form-grid">
        <p class="hint">${esc(L("Löscht beendete Durchläufe samt Ergebnis je Chat. Die Chats behalten ihren Status.",
                                 "Deletes finished runs together with their per-chat results. The chats keep their status."))}</p>
        <label><span>${esc(L("Durchläufe löschen, die älter sind als (Tage)", "Delete runs older than (days)"))}</span>
          <input name="days" type="number" min="1" max="36500" step="1" value="30" required></label>
        <div class="actions"><button class="btn" type="button" data-close-modal>${esc(L("Abbrechen", "Cancel"))}</button>
        <button class="btn danger" type="submit">${esc(L("Löschen", "Delete"))}</button></div></form>`);
    const form = K.$("#tg-cleanup");
    form.days.focus();
    form.onsubmit = act(async (e) => {
      e.preventDefault();
      const days = Number(form.days.value);
      if (!Number.isInteger(days) || days < 1) return K.toast(L("Bitte eine ganze Zahl ab 1 eingeben", "Enter a whole number from 1"), true);
      if (!confirm(L(`Alle beendeten Durchläufe, die älter als ${days} Tage sind, werden gelöscht. Fortfahren?`,
                     `All finished runs older than ${days} days will be deleted. Continue?`))) return;
      const res = await K.api(`${API}/runs/cleanup`, { method: "POST", body: { days } });
      K.closeModal();
      K.toast(L(`${res.deleted} Durchläufe gelöscht`, `${res.deleted} runs deleted`));
      hs.page = 0;
      if (histEl && !hs.detail) await loadList();
    });
  }

  // a run changed while the Verlauf tab is open
  function histRunEvent(m) {
    if (hs.detail === null) {
      if (!RUN_ACTIVE.includes(m.status) || hs.page === 0) reloadHistory();
    } else if (hs.run && hs.run.id === m.id) {
      hs.run = m;
      paintDetailHead();
      reloadDetail();
    }
  }
  const reloadHistory = K.throttle(() => { if (histEl && hs.detail === null) loadList().catch(() => {}); }, 1500);
  const reloadDetail = K.throttle(() => { if (histEl && hs.detail !== null) loadDetailChats().catch(() => {}); }, 1500);

  // --- tabs -----------------------------------------------------------------------------------

  const TAB_TITLES = { dashboard: ["Dashboard", "Dashboard"], accounts: ["Konten", "Accounts"], chats: ["Chats", "Chats"],
    workflows: ["Abläufe", "Workflows"], runs: ["Versand", "Sending"], history: ["Verlauf", "History"] };
  const loadingHtml = (tab) => head(L(...TAB_TITLES[tab]), "") + `<div class="tg-loading" role="status" style="padding:40px 0;text-align:center;color:var(--muted)"><span class="tg-wait">${icon("refresh")}</span>${esc(L("Wird geladen …", "Loading …"))}</div>`;

  const TABS = {
    async dashboard(el) {
      await openDashboard(el);
      watch();
    },
    async accounts(el) {
      accountsEl = el;
      await renderAccounts();
      watch();
    },
    async chats(el) {
      chatsEl = el;
      accountList = await K.api(`${API}/accounts`);
      for (const k of Object.keys(syncing)) delete syncing[k];
      accountList.filter((a) => a.sync).forEach((a) => (syncing[a.id] = { ...a.sync, account_id: a.id, state: "running" }));
      const sync = `<button class="btn primary" data-act="sync">${icon("refresh")}<span>${esc(L("Chats synchronisieren", "Sync chats"))}</span></button>`;
      el.innerHTML = head(L("Chats", "Chats"), L("Erfasste Chats durchsuchen, filtern und auswählen", "Search, filter and select captured chats"), sync);
      if (!accountList.length) {
        el.innerHTML += `<div class="empty">${icon("send")}<b>${esc(L("Noch kein Konto verbunden", "No account linked yet"))}</b>
          <span>${esc(L("Verbinde zuerst ein Telegram-Konto im Bereich Konten.", "Link a Telegram account in the Accounts section first."))}</span></div>`;
        return;
      }
      el.insertAdjacentHTML("beforeend", '<div data-sync></div><div data-table></div>');
      chatsCtl = chatTable(el.querySelector("[data-table]"), { accounts: accountList });
      el.querySelector('[data-act="sync"]').onclick = syncNow;
      renderSync();
      await chatsCtl.reload();
      watch();
    },
    async workflows(el) {
      wfEl = el;
      if (ed) renderEditor(); else await renderWorkflowList();
    },
    async runs(el) {
      await openRuns(el);
      watch();
    },
    async history(el) {
      await openHistory(el);
      watch();
    },
  };

  window.PanelModules.telegram = {
    async open(tab, el) {
      el.innerHTML = loadingHtml(tab);       // something to look at while the tab's requests are answered
      K.hydrateIcons(el);
      await TABS[tab](el);
      K.hydrateIcons(el);
    },
    close(tab) {
      if (tab === "accounts") accountsEl = null;
      if (tab === "workflows") wfEl = null;
      if (tab === "chats") {
        if (chatsCtl) chatsCtl.destroy();
        chatsCtl = chatsEl = null;
      }
      if (tab === "runs") closeRuns();
      if (tab === "dashboard") dashEl = null;
      if (tab === "history") histEl = null;
    },
    start() { watch(); },
    stop() { closeRuns(); if (sock) { sock.close(); sock = null; } activeRuns.clear(); renderBadge(); },
  };
})();
