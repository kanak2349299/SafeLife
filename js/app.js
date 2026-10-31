/* Bootstrap, routing and layout matching design picture. */
window.SLApp = (() => {
  const { api, ApiError, esc, toast, icon, logo } = window.SL;
  const $ = (id) => document.getElementById(id);
  let currentUser = null;
  let notificationsOpen = false;

  const ROUTES = {
    "/": () => window.SLMain.dashboard(),
    "/aapdasense": () => window.SLMain.aapdasense(),
    "/map": () => window.SLMain.map(),
    "/vault": () => window.SLVault.render(),
    "/documents": () => window.SLMain.documents(),
    "/assistant": () => window.SLVault.assistant(),
    "/planner": () => window.SLMain.planner(),
    "/family": () => window.SLMain.family(),
    "/emergency": () => window.SLMain.emergency(),
    "/settings": () => window.SLMain.settings(),
  };

  const NAV = [
    ["/", "Overview", "home"],
    ["/aapdasense", "AapdaSense", "alert"],
    ["/map", "Live Disaster Map", "map"],
    ["/vault", "My Memory Vault", "lock"],
    ["/documents", "Document Recommendations", "doc"],
    ["/planner", "Emergency Planner", "plan"],
    ["/family", "Family Safety", "family"],
    ["/settings", "Settings", "gear"],
  ];

  function renderChrome() {
    $("logo").innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;width:100%;padding:4px 8px">
        ${logo(36)}
        <div style="font-size:22px;font-weight:800;letter-spacing:-0.3px">
          <span style="color:#1b1f5e">Safe</span><span style="color:#ff8a2a">Life</span>
        </div>
      </div>`;

    $("nav").innerHTML = NAV.map(([href, label, ic]) =>
      `<a class="nav-item" href="#${href}" data-route="${href}">
        <span class="ni">${icon(ic)}</span>
        <span>${esc(label)}</span>
      </a>`).join("");

    const first = (currentUser?.full_name || currentUser?.email || "Himangi").trim();
    const displayName = first.split(" ")[0] || "Himangi";

    // Topbar User Chip with dropdown
    $("userChip").innerHTML = `
      <div class="user-dropdown" id="userMenuBtn">
        <div class="avatar" style="width:36px;height:36px;background:linear-gradient(135deg, #4b2fd6, #ff8a2a);font-size:14px;box-shadow:0 3px 10px rgba(75,47,214,0.3)">
          ${esc(displayName[0].toUpperCase())}
        </div>
        <div class="user-name">
          <span>${esc(displayName)}</span>
          <span style="font-size:10px;color:#8a8fae">⌵</span>
        </div>
        <div id="userMenuPopover" class="noti-popover" style="display:none;width:180px;right:0;top:44px">
          <a href="#/vault" class="nav-item" style="padding:8px 10px;font-size:13px">My Vault</a>
          <a href="#/settings" class="nav-item" style="padding:8px 10px;font-size:13px">Settings</a>
          <hr style="border:none;border-top:1px solid #f0f2fa;margin:4px 0" />
          <button id="logoutBtn" class="link small" style="color:#e53e5a;padding:8px 10px;width:100%;text-align:left">Sign Out</button>
        </div>
      </div>`;

    $("userMenuBtn").onclick = (e) => {
      e.stopPropagation();
      const m = $("userMenuPopover");
      m.style.display = m.style.display === "none" ? "block" : "none";
    };

    $("logoutBtn").onclick = (e) => {
      e.stopPropagation();
      logout();
    };

    // Notification bell handler
    $("bell").onclick = (e) => {
      e.stopPropagation();
      toggleNotifications();
    };

    // Close menus on outer click
    document.onclick = () => {
      if ($("userMenuPopover")) $("userMenuPopover").style.display = "none";
      const noti = document.getElementById("notiPopover");
      if (noti) noti.remove();
    };

    $("footer").innerHTML = `Emergency: <b>112</b> · Official alerts: <a href="https://sachet.ndma.gov.in" target="_blank" rel="noopener">NDMA Sachet</a>, <a href="https://mausam.imd.gov.in" target="_blank" rel="noopener">IMD</a> · SafeLife is an awareness tool, not an official warning service.`;
  }

  function toggleNotifications() {
    let pop = document.getElementById("notiPopover");
    if (pop) { pop.remove(); return; }
    pop = document.createElement("div");
    pop.id = "notiPopover";
    pop.className = "noti-popover";
    pop.innerHTML = `
      <div class="row between" style="margin-bottom:12px;border-bottom:1px solid #eef0f8;padding-bottom:8px">
        <b style="font-size:14px;color:#1b1f5e">Notifications</b>
        <span class="badge red">2 New</span>
      </div>
      <div class="noti-item">
        <span style="font-size:18px">🔥</span>
        <div style="font-size:12px">
          <b style="color:#e53e5a">Heat Wave Alert</b> in Delhi NCR
          <div class="muted">IMD advisory issued for high temperatures today.</div>
        </div>
      </div>
      <div class="noti-item">
        <span style="font-size:18px">🔒</span>
        <div style="font-size:12px">
          <b>Aadhaar Card Encrypted</b>
          <div class="muted">Document secured in your personal vault.</div>
        </div>
      </div>
      <div style="text-align:center;margin-top:10px">
        <a href="#/aapdasense" class="small link">View All Alerts →</a>
      </div>`;
    $("bell").appendChild(pop);
  }

  function markActive() {
    const hash = location.hash.replace(/^#/, "") || "/";
    document.querySelectorAll(".nav-item").forEach((a) => a.classList.toggle("active", a.dataset.route === hash));
  }

  async function route() {
    if (!currentUser) return;
    const path = (location.hash.replace(/^#/, "") || "/").split("?")[0];
    markActive();
    $("sidebar").classList.remove("open");
    const handler = ROUTES[path];
    if (!handler) { location.hash = "#/"; return; }
    try {
      await handler();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return showLogin();
      $("view").innerHTML = `<div class="card"><p class="error">${esc(err.message)}</p></div>`;
    }
  }

  function setBadge(n) {
    const b = $("bellCount");
    b.hidden = !n;
    b.textContent = n;
  }

  async function refreshUser() {
    const me = await api("auth/me");
    currentUser = me.user;
    renderChrome();
  }

  function enterApp() {
    $("auth").hidden = true;
    $("shell").hidden = false;
    renderChrome();
    if (!location.hash || location.hash.startsWith("#/login")) location.hash = "#/";
    route();
  }

  async function afterLogin(user) {
    currentUser = user;
    if (!user.onboarded) return window.SLAuth.showOnboarding(user);
    enterApp();
  }

  function showLogin() {
    currentUser = null;
    $("shell").hidden = true;
    window.SLAuth.showAuth("login");
  }

  async function logout() {
    try { await api("auth/logout", { method: "POST" }); } catch (_) {}
    window.SLVault?.lock();
    showLogin();
  }

  async function init() {
    $("menuBtn").onclick = () => $("sidebar").classList.toggle("open");
    window.onhashchange = route;

    // Search bar functionality
    $("searchBox").oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) return;
      if (e.key === "Enter" || q.length >= 3) {
        if (q.includes("map") || q.includes("danger") || q.includes("safe")) location.hash = "#/map";
        else if (q.includes("vault") || q.includes("doc") || q.includes("aadhaar")) location.hash = "#/vault";
        else if (q.includes("alert") || q.includes("heat") || q.includes("disaster")) location.hash = "#/aapdasense";
        else if (q.includes("ai") || q.includes("assist")) location.hash = "#/assistant";
      }
    };

    try {
      const me = await api("auth/me");
      currentUser = me.user;
      enterApp();
    } catch (err) {
      // Auto-demo login if no session so the browser immediately shows the populated dashboard
      try {
        const demo = await api("auth/demo", { method: "POST" });
        if (demo.user) {
          currentUser = demo.user;
          enterApp();
          return;
        }
      } catch (_) {}
      showLogin();
    }
  }

  document.addEventListener("DOMContentLoaded", init);

  return { init, enterApp, afterLogin, showLogin, logout, refreshUser, setBadge, getCurrentUser: () => currentUser };
})();
