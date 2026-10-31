/* Sign in / sign up, MFA step, and onboarding with visual fidelity to design. */
window.SLAuth = (() => {
  const { api, esc, toast, logo } = window.SL;
  let mode = "login";
  let pendingEmail = null;
  let pendingPassword = null;
  let showPassword = false;

  function authArt() {
    return `
      <div style="position:relative;width:280px;height:240px;margin:15px auto;">
        <!-- Glowing background rings -->
        <svg viewBox="0 0 280 240" style="position:absolute;inset:0;width:100%;height:100%" aria-hidden="true">
          <defs>
            <radialGradient id="orbitGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#7c4dff" stop-opacity="0.25"/>
              <stop offset="60%" stop-color="#4b2fd6" stop-opacity="0.08"/>
              <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
            </radialGradient>
            <linearGradient id="shieldGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#6979f8"/>
              <stop offset="50%" stop-color="#4054ea"/>
              <stop offset="100%" stop-color="#2a38b7"/>
            </linearGradient>
            <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ffe066"/>
              <stop offset="100%" stop-color="#f59f00"/>
            </linearGradient>
          </defs>

          <!-- Halo circle -->
          <circle cx="140" cy="115" r="70" fill="url(#orbitGlow)"/>

          <!-- Orbit line 1 -->
          <ellipse cx="140" cy="115" rx="100" ry="42" fill="none" stroke="#cfd4fc" stroke-width="2" stroke-dasharray="6 4" transform="rotate(-15 140 115)"/>
          <!-- Orbit line 2 -->
          <ellipse cx="140" cy="115" rx="85" ry="32" fill="none" stroke="#ffd8a8" stroke-width="2" transform="rotate(22 140 115)"/>

          <!-- 3D Glowing Shield -->
          <g filter="drop-shadow(0 12px 20px rgba(64,84,234,0.35))">
            <path d="M140 50 L185 68 C185 106 168 140 140 160 C112 140 95 106 95 68 Z" fill="url(#shieldGrad)"/>
            <path d="M140 55 L178 71 C178 103 163 133 140 151 C117 133 102 103 102 71 Z" fill="#4d62f0"/>
          </g>

          <!-- Padlock on Shield -->
          <g transform="translate(126, 92)" filter="drop-shadow(0 4px 8px rgba(0,0,0,0.2))">
            <path d="M7 11 V7 A7 7 0 0 1 21 7 V11" fill="none" stroke="url(#goldGrad)" stroke-width="3.5" stroke-linecap="round"/>
            <rect x="3" y="11" width="22" height="18" rx="4" fill="url(#goldGrad)"/>
            <circle cx="14" cy="19" r="2.5" fill="#5c3b00"/>
            <path d="M14 21 V24" stroke="#5c3b00" stroke-width="2" stroke-linecap="round"/>
          </g>

          <!-- Floating Document 1 (Identity card - Left) -->
          <g transform="translate(42, 65) rotate(-10)" filter="drop-shadow(0 6px 12px rgba(30,30,90,0.12))">
            <rect width="40" height="52" rx="6" fill="#ffffff" stroke="#e0e3f5"/>
            <circle cx="14" cy="18" r="6" fill="#4b2fd6" opacity="0.8"/>
            <rect x="23" y="14" width="12" height="3" rx="1.5" fill="#4b2fd6"/>
            <rect x="23" y="19" width="8" height="3" rx="1.5" fill="#9da4c8"/>
            <rect x="8" y="30" width="24" height="2.5" rx="1" fill="#c3c8e2"/>
            <rect x="8" y="36" width="18" height="2.5" rx="1" fill="#c3c8e2"/>
            <rect x="8" y="42" width="20" height="2.5" rx="1" fill="#c3c8e2"/>
          </g>

          <!-- Floating Document 2 (Medical + - Right) -->
          <g transform="translate(200, 72) rotate(12)" filter="drop-shadow(0 6px 12px rgba(30,30,90,0.12))">
            <rect width="38" height="48" rx="6" fill="#ffffff" stroke="#e0e3f5"/>
            <rect x="15" y="14" width="8" height="8" rx="2" fill="#e8f8f0"/>
            <path d="M19 15 V21 M16 18 H22" stroke="#1faa6b" stroke-width="2.5" stroke-linecap="round"/>
            <rect x="8" y="27" width="22" height="2.5" rx="1" fill="#c3c8e2"/>
            <rect x="8" y="33" width="16" height="2.5" rx="1" fill="#c3c8e2"/>
            <rect x="8" y="39" width="19" height="2.5" rx="1" fill="#c3c8e2"/>
          </g>

          <!-- Floating Badge 3 (Orange Shield Checkmark) -->
          <g transform="translate(182, 135)" filter="drop-shadow(0 4px 10px rgba(255,138,42,0.3))">
            <circle cx="16" cy="16" r="14" fill="#ff8a2a"/>
            <path d="M11 16 L15 20 L22 13" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </g>

          <!-- Floating Blue Checkmark Badge Left -->
          <g transform="translate(80, 138)" filter="drop-shadow(0 4px 10px rgba(75,47,214,0.25))">
            <circle cx="12" cy="12" r="11" fill="#4b2fd6"/>
            <path d="M8 12 L11 15 L16 10" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </g>

          <!-- Indian Monument Silhouettes at bottom -->
          <g opacity="0.35" fill="#8f96bd" transform="translate(0, 185)">
            <!-- India Gate & Domes & Taj silhouette line -->
            <path d="M0 45 L15 45 L15 32 L20 30 L25 45 L40 45 L45 25 L50 20 L55 25 L60 45 L80 45 L85 15 L95 10 L105 15 L110 45 L130 45 L130 18 L140 18 L140 28 L145 28 L145 45 L150 45 L155 12 L165 8 L175 12 L180 45 L200 45 L205 28 L210 24 L215 28 L220 45 L240 45 L245 15 L255 10 L265 15 L280 45 V55 H0 Z"/>
          </g>
        </svg>
      </div>`;
  }

  function authShell() {
    return `
      <section class="auth-left">
        <div class="blob" style="width:360px;height:360px;background:#c9b8ff;top:-100px;left:-100px"></div>
        <div class="blob" style="width:300px;height:300px;background:#ffd2a6;bottom:-100px;right:-80px"></div>
        
        <div style="position:relative;display:flex;align-items:center;gap:10px;margin-bottom:6px">
          ${logo(48)}
          <div style="font-size:38px;font-weight:800;letter-spacing:-0.5px">
            <span style="color:#1b1f5e">Safe</span><span style="color:#ff8a2a">Life</span>
          </div>
        </div>
        
        <div class="tag" style="position:relative">Your Life. Your Memories. Your Safety.</div>
        <div class="pills" style="position:relative">Secure Documents <span>•</span> Disaster Alerts <span>•</span> Peace of Mind</div>

        <!-- Central illustration with glowing shield, documents & monuments -->
        ${authArt()}

        <!-- Bottom botanical waves -->
        <svg viewBox="0 0 500 120" style="position:absolute;bottom:0;left:0;width:100%;pointer-events:none" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 60 C150 110 320 20 500 70 L500 120 L0 120 Z" fill="#ebedff" opacity="0.6"/>
          <path d="M0 80 C180 30 350 110 500 75 L500 120 L0 120 Z" fill="#ffeade" opacity="0.5"/>
          <path d="M10 110 Q25 70 50 85 Q75 100 90 60 Q105 110 120 120 Z" fill="#6d4cff" opacity="0.18"/>
        </svg>
      </section>

      <section class="auth-right">
        <div class="auth-box" id="authBox"></div>
      </section>`;
  }

  function renderForm(message = "") {
    const box = document.getElementById("authBox");
    if (pendingEmail) {
      box.innerHTML = `
        <h2 style="font-size:24px;font-weight:800;color:#1b1f5e;margin-bottom:6px">Two-step verification</h2>
        <p class="muted" style="margin-bottom:20px">Enter the 6-digit code from your authenticator app.</p>
        <form id="mfaForm">
          <div class="field">
            <span>Authenticator code</span>
            <input class="input" id="mfaCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required placeholder="000000" style="font-size:18px;letter-spacing:4px;text-align:center" />
          </div>
          <div class="error" id="authErr">${esc(message)}</div>
          <button class="btn-signin" id="authSubmit" type="submit">Verify and sign in →</button>
          <p class="small muted" style="margin-top:16px;text-align:center">
            <button class="link" type="button" id="mfaBack">← Back to Login</button>
          </p>
        </form>`;
      document.getElementById("mfaCode").focus();
      document.getElementById("mfaForm").onsubmit = submitMfa;
      document.getElementById("mfaBack").onclick = () => { pendingEmail = null; pendingPassword = null; renderForm(); };
      return;
    }

    const isSignup = mode === "signup";
    box.innerHTML = `
      <div class="seg" role="tablist">
        <button type="button" data-mode="login" class="${!isSignup ? "on" : ""}">Login</button>
        <button type="button" data-mode="signup" class="${isSignup ? "on" : ""}">Sign Up</button>
      </div>

      <form id="authForm">
        ${isSignup ? `
          <div class="field">
            <div class="input-icon-group">
              <span class="icon-pre">👤</span>
              <input id="fullName" placeholder="Full Name" autocomplete="name" maxlength="100" />
            </div>
          </div>` : ""}

        <div class="field">
          <div class="input-icon-group">
            <span class="icon-pre">✉</span>
            <input id="email" type="email" placeholder="Email Address" autocomplete="email" required value="${!isSignup && !pendingEmail ? "himangi123@gmail.com" : ""}" />
          </div>
        </div>

        <div class="field" style="margin-bottom:6px">
          <div class="input-icon-group">
            <span class="icon-pre">🔒</span>
            <input id="password" type="${showPassword ? "text" : "password"}" placeholder="Password" minlength="6"
              autocomplete="${isSignup ? "new-password" : "current-password"}" required value="${!isSignup ? "Password@123" : ""}" />
            <button type="button" class="icon-eye" id="togglePw" aria-label="Toggle password visibility">
              ${showPassword ? "👁️‍🗨️" : "👁️"}
            </button>
          </div>
        </div>

        <div class="auth-options">
          <label><input type="checkbox" id="rememberMe" checked /> <span>Remember me</span></label>
          <a href="javascript:void(0)" id="forgotPwLink">Forgot password?</a>
        </div>

        <div class="error" id="authErr">${esc(message)}</div>

        <button class="btn-signin" id="authSubmit" type="submit">
          <span>${isSignup ? "Create Account" : "Sign In"}</span> <span>→</span>
        </button>

        <div class="auth-divider"><span>or continue with</span></div>

        <button type="button" class="btn-google" id="googleBtn">
          <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.7 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.6c-.3 1.5-1.1 2.8-2.4 3.7v3.1h3.9c2.3-2.1 3.6-5.2 3.6-9z"/><path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-3l-3.9-3.1c-1.1.7-2.5 1.2-4.1 1.2-3.1 0-5.8-2.1-6.7-5H1.2v3.2C3.3 21.4 7.4 24 12 24z"/><path fill="#FBBC05" d="M5.3 14.1c-.2-.7-.4-1.5-.4-2.3 0-.8.1-1.6.4-2.3V6.3H1.2C.4 7.9 0 9.9 0 12c0 2.1.4 4.1 1.2 5.7l4.1-3.6z"/><path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4C18 1.2 15.2 0 12 0 7.4 0 3.3 2.6 1.2 6.3l4.1 3.2c.9-2.9 3.6-4.7 6.7-4.7z"/></svg>
          <span>Continue with Google</span>
        </button>

        <button type="button" class="btn-demo-quick" id="demoQuickBtn">
          <span>⚡</span> <span>One-Click Demo (Himangi)</span>
        </button>

        <p class="small muted" style="margin-top:20px;text-align:center">
          ${isSignup ? `Already have an account? <a href="javascript:void(0)" class="link" id="switchLogin">Sign In</a>` : `Don't have an account? <a href="javascript:void(0)" class="link" id="switchSignup">Create Account</a>`}
        </p>
      </form>`;

    box.querySelectorAll("[data-mode]").forEach((b) => b.onclick = () => { mode = b.dataset.mode; renderForm(); });
    
    document.getElementById("togglePw").onclick = () => {
      showPassword = !showPassword;
      renderForm();
    };

    if (document.getElementById("switchSignup")) {
      document.getElementById("switchSignup").onclick = () => { mode = "signup"; renderForm(); };
    }
    if (document.getElementById("switchLogin")) {
      document.getElementById("switchLogin").onclick = () => { mode = "login"; renderForm(); };
    }

    document.getElementById("forgotPwLink").onclick = () => {
      toast("To reset password, please verify your email or use the Demo login.", "err");
    };

    document.getElementById("demoQuickBtn").onclick = handleDemoLogin;
    document.getElementById("googleBtn").onclick = handleDemoLogin;

    document.getElementById("authForm").onsubmit = submitAuth;
  }

  async function handleDemoLogin() {
    const btn = document.getElementById("demoQuickBtn");
    if (btn) { btn.disabled = true; btn.innerHTML = `<span>⏳ Signing in...</span>`; }
    try {
      const res = await api("auth/demo", { method: "POST" });
      if (res.user) {
        toast("Welcome, " + (res.user.full_name || "Himangi") + "!");
        window.SLApp.afterLogin(res.user);
      }
    } catch (err) {
      // Fallback normal login
      try {
        const res = await api("auth/login", { method: "POST", body: { email: "himangi123@gmail.com", password: "Password@123" } });
        window.SLApp.afterLogin(res.user);
      } catch (e) {
        renderForm(err.message || e.message);
      }
    }
  }

  async function submitAuth(e) {
    e.preventDefault();
    const btn = document.getElementById("authSubmit");
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const fullName = document.getElementById("fullName")?.value.trim() || "";
    btn.disabled = true; btn.innerHTML = `<span class="spin"></span> Signing In...`;
    try {
      const path = mode === "signup" ? "auth/register" : "auth/login";
      const body = mode === "signup" ? { email, password, full_name: fullName } : { email, password };
      const res = await api(path, { method: "POST", body });
      if (res.mfa_required) {
        pendingEmail = email; pendingPassword = password;
        renderForm();
        return;
      }
      window.SLApp.afterLogin(res.user);
    } catch (err) {
      renderForm(err.message);
    }
  }

  async function submitMfa(e) {
    e.preventDefault();
    const code = document.getElementById("mfaCode").value.trim();
    const btn = document.getElementById("authSubmit");
    btn.disabled = true;
    try {
      const res = await api("auth/login", { method: "POST", body: { email: pendingEmail, password: pendingPassword, code } });
      pendingEmail = null; pendingPassword = null;
      window.SLApp.afterLogin(res.user);
    } catch (err) {
      renderForm(err.message);
    }
  }

  function showAuth(initialMode = "login") {
    mode = initialMode;
    const root = document.getElementById("auth");
    root.innerHTML = authShell();
    root.hidden = false;
    document.getElementById("shell").hidden = true;
    renderForm();
  }

  function showOnboarding(user) {
    const root = document.getElementById("auth");
    root.innerHTML = `
      <div class="onb card" style="margin-top:40px;box-shadow:var(--shadow)">
        <h2 style="font-size:24px;font-weight:800;color:#1b1f5e;margin-bottom:6px">Complete your safety profile</h2>
        <p class="muted" style="margin-bottom:20px">SafeLife personalises your document checklist and emergency readiness.</p>
        <form id="onbForm">
          <div class="field">
            <span>Your Current City</span>
            <input class="input" id="onbCity" value="${esc(user.city || "New Delhi")}" required />
          </div>
          <div class="field">
            <span>Blood Group</span>
            <select class="input" id="onbBlood">
              ${["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Unknown"].map(b => `<option ${b === (user.blood_group || "B+") ? "selected" : ""}>${b}</option>`).join("")}
            </select>
          </div>
          <button class="btn-signin" style="margin-top:16px" type="submit">Save and Enter SafeLife →</button>
        </form>
      </div>`;
    document.getElementById("onbForm").onsubmit = async (e) => {
      e.preventDefault();
      const city = document.getElementById("onbCity").value.trim();
      const blood = document.getElementById("onbBlood").value;
      await api("settings/profile", { method: "PUT", body: { city, blood_group: blood, has_property: true, has_children: true, has_vehicle: true } });
      window.SLApp.enterApp();
    };
  }

  return { showAuth, showOnboarding };
})();
