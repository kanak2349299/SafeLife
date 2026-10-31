/* Memory Vault (client-side encryption) and the AI Assistant chat. */
window.SLVault = (() => {
  const { api, esc, toast, fmtDate, fmtDay, fmtSize, ago, icon } = window.SL;
  const C = window.VaultCrypto;
  const $ = (id) => document.getElementById(id);
  const view = () => $("view");
  const IDLE_MS = 10 * 60 * 1000;
  const MAX_BYTES = 5 * 1024 * 1024;

  // The vault key lives only in this closure. It is never stored or sent anywhere.
  let vaultKey = null;
  let idleTimer = null;
  let cached = [];           // decrypted item list: {id, name, doc_key, label, group, expiry, sha256, size, added}
  let docKeyMap = null;      // doc key -> {label, group}

  const DOC_OPTIONS = [
    ["aadhaar", "Identity", "Aadhaar Card"], ["pan", "Identity", "PAN Card"], ["passport", "Identity", "Passport"],
    ["voter_id", "Identity", "Voter ID"], ["driving_licence", "Identity", "Driving Licence"],
    ["birth_certificate", "Identity", "Children's Birth Certificate"],
    ["certificates", "Education", "Educational Certificate"], ["marksheets", "Education", "Mark Sheet"],
    ["degree", "Education", "Degree Certificate"],
    ["bank_info", "Financial", "Bank Account Information"], ["insurance", "Financial", "Insurance Policy"],
    ["property_papers", "Financial", "Property Document"], ["vehicle_rc", "Financial", "Vehicle Registration"],
    ["financial_records", "Financial", "Financial Record"],
    ["medical_history", "Medical", "Medical History"], ["prescriptions", "Medical", "Prescription"],
    ["blood_group", "Medical", "Blood Group Report"], ["health_insurance", "Medical", "Health Insurance"],
    ["emergency_contacts", "Emergency", "Emergency Contacts"], ["family_info", "Emergency", "Family Information"],
    ["legal_docs", "Emergency", "Legal Document"], ["ownership_records", "Emergency", "Ownership Record"],
    ["other", "Other", "Other document"],
  ];
  const GUESS = [
    [/aadhaar|aadhar/i, "aadhaar"], [/\bpan\b/i, "pan"], [/passport/i, "passport"], [/voter/i, "voter_id"],
    [/licen[cs]e|dl_/i, "driving_licence"], [/marks?\s?sheet|marksheet/i, "marksheets"], [/degree/i, "degree"],
    [/insur|policy/i, "insurance"], [/prescri|rx/i, "prescriptions"], [/medical|report|lab/i, "medical_history"],
    [/bank|cheque|check/i, "bank_info"], [/deed|property|registry|rent/i, "property_papers"],
    [/\brc\b|registration/i, "vehicle_rc"],
  ];
  const guessKey = (name) => (GUESS.find(([re]) => re.test(name)) || [null, "other"])[1];
  const docLabel = (k) => (DOC_OPTIONS.find((d) => d[0] === k) || [0, "Other", "Other document"])[2];

  function touch() {
    if (!vaultKey) return;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { lock(); toast("Vault locked after 10 minutes of inactivity."); render(); }, IDLE_MS);
  }
  function lock() { vaultKey = null; cached = []; clearTimeout(idleTimer); }

  function expiryBadge(expiry) {
    if (!expiry) return `<span class="badge gray">No expiry set</span>`;
    const days = Math.ceil((new Date(expiry) - new Date()) / 86400000);
    if (days < 0) return `<span class="badge red">Expired ${fmtDay(expiry)}</span>`;
    if (days <= 60) return `<span class="badge orange">Renew in ${days} days</span>`;
    return `<span class="badge green">Valid until ${fmtDay(expiry)}</span>`;
  }

  async function render() {
    if (!docKeyMap) {
      docKeyMap = {};
      DOC_OPTIONS.forEach(([k, g, l]) => (docKeyMap[k] = { label: l, group: g }));
    }
    view().innerHTML = `<div class="stack"><div class="skeleton"></div></div>`;
    let setup;
    try { setup = await api("vault/setup"); } catch (err) {
      view().innerHTML = `<div class="card"><p class="error">${esc(err.message)}</p></div>`;
      return;
    }
    if (!setup.initialized) return renderSetup(setup);
    if (!vaultKey) return renderUnlock(setup);
    return renderMain(setup);
  }

  /* ----------------------------------------------------- setup / unlock */
  function renderSetup(setup) {
    view().innerHTML = `
      <div class="card" style="max-width:560px;margin:20px auto">
        <div class="card-title"><span class="ico purple">${icon("lock")}</span>Create your vault passphrase</div>
        <p class="muted" style="margin-bottom:14px">This passphrase encrypts your documents on this device. We cannot see it and cannot reset it. If you forget it, your documents cannot be recovered.</p>
        <form id="setupForm">
          <label class="field"><span>Passphrase (at least 10 characters)</span><input id="p1" type="password" minlength="10" autocomplete="new-password" required /></label>
          <label class="field"><span>Repeat passphrase</span><input id="p2" type="password" minlength="10" autocomplete="new-password" required /></label>
          <div class="error" id="err"></div>
          <button class="btn primary" id="go" type="submit">Create vault</button>
        </form>
      </div>`;
    $("setupForm").onsubmit = async (e) => {
      e.preventDefault();
      const p1 = $("p1").value, p2 = $("p2").value;
      if (p1 !== p2) { $("err").textContent = "The two passphrases do not match."; return; }
      if (p1.length < 10) { $("err").textContent = "Use at least 10 characters."; return; }
      $("go").disabled = true; $("go").innerHTML = `<span class="spin"></span> Securing…`;
      try {
        const key = await C.deriveKey(p1, setup.salt);
        await api("vault/check", { method: "PUT", body: { check: await C.makeCheck(key) } });
        vaultKey = key; touch(); toast("Vault created"); render();
      } catch (err) {
        $("err").textContent = err.message; $("go").disabled = false; $("go").textContent = "Create vault";
      }
    };
  }

  function renderUnlock(setup) {
    view().innerHTML = `
      <div class="card" style="max-width:520px;margin:20px auto">
        <div class="card-title"><span class="ico purple">${icon("lock")}</span>Unlock your vault</div>
        <form id="unlockForm">
          <label class="field"><span>Vault passphrase</span><input id="pp" type="password" autocomplete="off" required autofocus /></label>
          <div class="error" id="err"></div>
          <button class="btn primary" id="go" type="submit">Unlock</button>
        </form>
        <p class="small muted" style="margin-top:12px">Your passphrase is checked on this device. It is never sent to the server.</p>
      </div>`;
    $("unlockForm").onsubmit = async (e) => {
      e.preventDefault();
      $("go").disabled = true; $("go").innerHTML = `<span class="spin"></span> Checking…`;
      try {
        const key = await C.deriveKey($("pp").value, setup.salt);
        if (!(await C.verifyCheck(key, setup.check))) {
          $("err").textContent = "Wrong passphrase. Please try again.";
          $("go").disabled = false; $("go").textContent = "Unlock";
          return;
        }
        vaultKey = key; touch(); render();
      } catch (err) {
        $("err").textContent = err.message; $("go").disabled = false; $("go").textContent = "Unlock";
      }
    };
  }

  /* ------------------------------------------------------------ main */
  async function loadDocs() {
    const { items } = await api("vault/items");
    const out = [];
    for (const it of items) {
      try {
        const meta = await C.openJSON(vaultKey, it.meta);
        out.push({ id: it.id, size: it.size, created: it.created, ...meta });
      } catch (_) {
        out.push({ id: it.id, size: it.size, created: it.created, name: "(could not decrypt)", broken: true });
      }
    }
    cached = out;
    return out;
  }

  async function renderMain() {
    view().innerHTML = `<div class="stack"><div class="skeleton"></div><div class="skeleton"></div></div>`;
    const docs = await loadDocs();
    const expiring = docs.filter((d) => d.expiry && Math.ceil((new Date(d.expiry) - new Date()) / 86400000) <= 60);
    const hist = await api("vault/history").catch(() => ({ events: [] }));

    view().innerHTML = `
      <div class="row between wrap" style="margin-bottom:18px">
        <div><h1 class="page-title">My Memory Vault</h1><p class="page-sub" style="margin:0">${docs.length} document${docs.length === 1 ? "" : "s"} · encrypted on this device</p></div>
        <div class="row"><input id="filter" class="input" placeholder="Filter by name…" style="width:220px" /><button class="btn soft" id="lockBtn">🔒 Lock vault</button></div>
      </div>

      ${expiring.length ? `<div class="card" style="margin-bottom:18px;background:var(--amber-bg);box-shadow:none">
        <b>Renewal reminders:</b> ${expiring.map((d) => `${esc(d.name)} (${d.expiry < new Date().toISOString().slice(0, 10) ? "expired" : "renew soon"})`).join(" · ")}</div>` : ""}

      <div class="grid g-2">
        <div class="card">
          <div class="card-title"><span class="ico purple">⬆️</span>Upload a document</div>
          <div class="drop" id="drop">
            <div style="font-size:28px">📄</div>
            <div style="font-weight:700;margin-top:6px">Drop a file here, or click to choose</div>
            <div class="small muted">PDF, JPG, PNG, DOC, DOCX or TXT · max 5 MB</div>
            <input id="file" type="file" hidden accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.txt" />
          </div>
          <form id="upForm" class="section-gap" hidden>
            <div id="chosen" class="small muted" style="margin-bottom:10px"></div>
            <label class="field"><span>What is this document?</span>
              <select id="docKey">${DOC_OPTIONS.map(([k, g, l]) => `<option value="${k}">${esc(g)} · ${esc(l)}</option>`).join("")}</select></label>
            <label class="field"><span>Expiry date (if the document has one)</span><input id="expiry" type="date" /></label>
            <div class="small muted" style="margin-bottom:10px">Note: automatic text reading (OCR) is not built yet, so please choose the type yourself.</div>
            <div class="error" id="upErr"></div>
            <button class="btn primary" id="upBtn" type="submit">Encrypt &amp; save</button>
          </form>
        </div>

        <div class="card">
          <div class="card-title"><span class="ico green">🛡️</span>How your vault is protected</div>
          <ul class="small muted" style="padding-left:18px;line-height:1.8">
            <li>Files and their names are encrypted in your browser (AES-256-GCM).</li>
            <li>The key comes from your passphrase, which never leaves this device.</li>
            <li>Duplicate check runs on your device too, so the server never compares files.</li>
            <li>Downloads and deletions are recorded in your history below.</li>
          </ul>
        </div>
      </div>

      <div class="card section-gap">
        <div class="card-title">Your documents</div>
        <div class="doc-grid" id="docGrid">
          ${docs.map(docCard).join("") || `<p class="muted">No documents yet. Upload your first one above.</p>`}
        </div>
      </div>

      <div class="card section-gap">
        <div class="card-title">Access history</div>
        ${hist.events.slice(0, 12).map((e) => `<div class="list-item"><span class="ico purple">•</span><div class="grow">${esc(e.kind.replace(/_/g, " "))} <span class="small muted">${esc(e.detail)}</span></div><span class="small muted">${ago(e.created)}</span></div>`).join("") || `<p class="muted">No activity yet.</p>`}
      </div>`;

    wireMain();
    touch();
  }

  function docCard(d) {
    if (d.broken) return `<div class="doc" style="opacity:.6"><div class="name">(could not decrypt)</div><div class="small muted">This item was encrypted with a different passphrase.</div>
      <div class="actions"><button class="btn sm danger" data-del="${d.id}">Delete</button></div></div>`;
    return `
      <div class="doc" data-name="${esc(d.name.toLowerCase())}">
        <div class="row between"><span class="badge purple">${esc(d.group || "Other")}</span><span class="small muted">${fmtSize(d.size)}</span></div>
        <div class="name">${esc(d.name)}</div>
        <div class="small muted">${esc(d.label || docLabel(d.doc_key))}</div>
        <div>${expiryBadge(d.expiry)}</div>
        <div class="small muted">Added ${fmtDate(d.added || (d.created * 1000))}</div>
        <div class="actions">
          <button class="btn sm soft" data-open="${d.id}">Open</button>
          <button class="btn sm" data-dl="${d.id}">Download</button>
          <button class="btn sm danger" data-del="${d.id}">Delete</button>
        </div>
      </div>`;
  }

  function wireMain() {
    $("lockBtn").onclick = () => { lock(); render(); };
    $("filter").oninput = (e) => {
      const q = e.target.value.trim().toLowerCase();
      document.querySelectorAll("#docGrid .doc").forEach((el) => { el.hidden = q && !el.dataset.name.includes(q); });
    };

    const drop = $("drop"), file = $("file");
    drop.onclick = () => file.click();
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) choose(e.dataTransfer.files[0]); });
    file.onchange = () => file.files[0] && choose(file.files[0]);

    let chosenFile = null;
    function choose(f) {
      touch();
      if (f.size > MAX_BYTES) { toast("That file is larger than 5 MB.", "err"); return; }
      chosenFile = f;
      $("upForm").hidden = false;
      $("chosen").textContent = `${f.name} · ${fmtSize(f.size)}`;
      $("docKey").value = guessKey(f.name);
      $("expiry").value = "";
    }

    $("upForm").onsubmit = async (e) => {
      e.preventDefault();
      if (!chosenFile) return;
      touch();
      $("upBtn").disabled = true; $("upBtn").innerHTML = `<span class="spin"></span> Encrypting…`;
      try {
        const bytes = new Uint8Array(await chosenFile.arrayBuffer());
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
          .map((b) => b.toString(16).padStart(2, "0")).join("");
        const dup = cached.find((d) => d.sha256 === digest);
        if (dup && !confirm(`This looks like a copy of "${dup.name}" already in your vault. Save it anyway?`)) {
          throw new Error("Upload cancelled: duplicate.");
        }
        const docKey = $("docKey").value;
        const data = await C.sealBytes(vaultKey, bytes);
        const meta = await C.sealJSON(vaultKey, {
          name: chosenFile.name.slice(0, 200), type: chosenFile.type || "application/octet-stream",
          size: chosenFile.size, doc_key: docKey, label: docLabel(docKey),
          group: docKeyMap[docKey]?.group || "Other", expiry: $("expiry").value || null,
          sha256: digest, added: new Date().toISOString(),
        });
        await api("vault/items", { method: "POST", body: { meta, data, size: chosenFile.size } });
        // Marks the checklist item as uploaded (status only, not the document).
        if (docKey !== "other") await api(`checklist/${docKey}`, { method: "PUT", body: { status: "uploaded" } }).catch(() => {});
        toast("Saved to your vault, encrypted.");
        chosenFile = null;
        render();
      } catch (err) {
        $("upErr").textContent = err.message;
        $("upBtn").disabled = false; $("upBtn").textContent = "Encrypt & save";
      }
    };

    view().querySelectorAll("[data-dl],[data-open]").forEach((b) => b.onclick = () => openDoc(b.dataset.dl || b.dataset.open, !!b.dataset.dl));
    view().querySelectorAll("[data-del]").forEach((b) => b.onclick = () => removeDoc(b.dataset.del));
  }

  async function openDoc(id, download) {
    touch();
    try {
      const item = await api(`vault/items/${id}`);
      const meta = await C.openJSON(vaultKey, item.meta);
      const bytes = await C.openBytes(vaultKey, item.data);
      const url = URL.createObjectURL(new Blob([bytes], { type: meta.type }));
      if (download) {
        const a = document.createElement("a");
        a.href = url; a.download = meta.name; document.body.appendChild(a); a.click(); a.remove();
      } else {
        window.open(url, "_blank", "noopener");
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      toast("Could not open this document: " + err.message, "err");
    }
  }

  async function removeDoc(id) {
    if (!confirm("Delete this document permanently? This cannot be undone.")) return;
    touch();
    try {
      const doc = cached.find((d) => String(d.id) === String(id));
      await api(`vault/items/${id}`, { method: "DELETE" });
      // If no other document of this type remains, the checklist goes back to pending.
      if (doc && doc.doc_key && doc.doc_key !== "other" && !cached.some((d) => d.id !== doc.id && d.doc_key === doc.doc_key)) {
        await api(`checklist/${doc.doc_key}`, { method: "PUT", body: { status: "pending" } }).catch(() => {});
      }
      toast("Deleted");
      render();
    } catch (err) { toast(err.message, "err"); }
  }

  /* ============================================================ ASSISTANT */
  const PROMPTS = [
    "What should I prepare if there is a flood warning in my district?",
    "Which documents should I keep ready before a cyclone?",
    "Is my location currently under any disaster warning?",
  ];

  function assistant() {
    view().innerHTML = `
      <h1 class="page-title">AI Preparedness Assistant</h1>
      <p class="page-sub">It uses your saved city and official alerts. Official instructions always come first. In danger, call 112.</p>
      <div class="grid" style="grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:start">
        <div class="card">
          <div class="chat" id="chat">
            <div class="msg bot">Hi! Ask me about floods, cyclones, heatwaves, earthquakes or which documents to keep ready. I will check official alerts for your saved city first.</div>
          </div>
          <form id="askForm" class="row" style="margin-top:14px">
            <input id="q" class="input" placeholder="Ask about preparedness or alerts…" maxlength="1000" required />
            <button class="btn primary" type="submit" id="askBtn">Send</button>
          </form>
        </div>
        <div class="card">
          <div class="card-title">Try asking</div>
          <div class="stack">${PROMPTS.map((p) => `<button class="btn soft" data-p="${esc(p)}" style="text-align:left;justify-content:flex-start;white-space:normal">${esc(p)}</button>`).join("")}</div>
          <p class="small muted" style="margin-top:14px">Your documents are never sent to the assistant. Only your city, the alert status and the names of missing essential documents are used.</p>
        </div>
      </div>`;
    const chat = $("chat");
    const add = (cls, text, src) => {
      const el = document.createElement("div");
      el.className = "msg " + cls;
      el.textContent = text;
      if (src) { const s = document.createElement("span"); s.className = "src"; s.textContent = src; el.appendChild(s); }
      chat.appendChild(el); chat.scrollTop = chat.scrollHeight;
    };
    async function ask(q) {
      add("user", q);
      const pending = document.createElement("div");
      pending.className = "msg bot"; pending.textContent = "Checking official sources…";
      chat.appendChild(pending);
      try {
        const r = await api("assistant", { method: "POST", body: { question: q } });
        pending.remove();
        add("bot", r.answer + (r.note ? `\n\n(${r.note})` : ""),
          r.source === "gemini" ? "AI answer · official alerts take priority · verify with NDMA Sachet / IMD" : "Rule-based guidance · verify with official sources");
      } catch (err) {
        pending.textContent = err.message;
      }
    }
    $("askForm").onsubmit = (e) => { e.preventDefault(); const q = $("q").value.trim(); if (q) { $("q").value = ""; ask(q); } };
    view().querySelectorAll("[data-p]").forEach((b) => b.onclick = () => ask(b.dataset.p));
  }

  return { render, assistant, lock, isUnlocked: () => !!vaultKey };
})();
