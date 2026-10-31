/* Shared helpers. Session is an HttpOnly cookie; JS never sees the token. */
window.SL = (() => {
  const CSRF = { "X-SafeLife": "1" };

  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  async function api(path, { method = "GET", body } = {}) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET") Object.assign(headers, CSRF);
    const res = await fetch("api/" + path, {
      method, headers, credentials: "same-origin", cache: "no-store",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* non-JSON */ }
    if (!res.ok) throw new ApiError(data.error || `Request failed (${res.status})`, res.status);
    return data;
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function toast(message, kind = "ok") {
    const host = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = "toast" + (kind === "err" ? " err" : "");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  const fmtDate = (t) => (t ? new Date(t).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");
  const fmtDay = (t) => (t ? new Date(t).toLocaleDateString("en-IN", { dateStyle: "medium" }) : "—");
  const fmtSize = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);
  const ago = (t) => {
    if (!t) return "";
    const s = (Date.now() / 1000) - t;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    return `${Math.round(s / 86400)} d ago`;
  };

  // Severity: green / yellow / orange / red. Labels follow the brief exactly.
  const SEV = {
    green: { label: "Normal", text: "Normal conditions", icon: "✓" },
    yellow: { label: "Be Aware", text: "Be aware", icon: "!" },
    orange: { label: "High Risk", text: "High risk", icon: "⚠" },
    red: { label: "Emergency", text: "Emergency / official severe warning", icon: "⛔" },
  };
  const sevBadge = (level) => `<span class="badge ${level}">${SEV[level]?.label || level}</span>`;
  const sevIcon = (level) => `<div class="sev-dot sev-${level}">${SEV[level]?.icon || "•"}</div>`;

  function greeting() {
    const h = new Date().getHours();
    return h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
  }

  function icon(name) {
    const paths = {
      shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
      home: '<path d="M3 11l9-7 9 7v9H3z"/><path d="M9 20v-6h6v6"/>',
      alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
      map: '<path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
      lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
      doc: '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
      chat: '<path d="M4 5h16v11H9l-5 4z"/>',
      plan: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/>',
      family: '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M14 20c0-2.5 1.6-4.5 4-4.5s3 1 3 1"/>',
      gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>',
      sos: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16h.01"/>',
      out: '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 4h5v16h-5"/>',
    };
    return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] || ""}</svg>`;
  }

  function logo(size = 56) {
    return `
      <svg width="${size}" height="${size}" viewBox="0 0 64 64" aria-hidden="true">
        <defs><linearGradient id="lg${size}" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#6d4cff"/><stop offset=".55" stop-color="#4b2fd6"/><stop offset="1" stop-color="#ff8a2a"/></linearGradient></defs>
        <path d="M32 4l22 8v16c0 14-9 24-22 30C19 52 10 42 10 28V12z" fill="url(#lg${size})"/>
        <path d="M32 18l12 10v13H38V34h-12v7H20V28z" fill="#fff"/>
        <path d="M14 46c6 4 12 5 18 5s12-1 18-5" stroke="#ff8a2a" stroke-width="3" fill="none" stroke-linecap="round"/>
      </svg>`;
  }

  return { api, ApiError, esc, toast, fmtDate, fmtDay, fmtSize, ago, SEV, sevBadge, sevIcon, greeting, icon, logo };
})();
