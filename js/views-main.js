/* Main application views. Exactly matching the design picture. */
window.SLMain = (() => {
  const { api, esc, toast, fmtDate, fmtDay, fmtSize, ago, SEV, sevBadge, sevIcon, greeting, icon } = window.SL;
  const $ = (id) => document.getElementById(id);
  const view = () => $("view");
  const loading = () => { view().innerHTML = `<div class="stack"><div class="skeleton"></div><div class="skeleton"></div></div>`; };
  const state = { city: "New Delhi", cities: null, mapFilter: "all", selectedState: null };

  const INDIAN_ZONES = [
    { id: "delhi", name: "Delhi NCR", state: "Delhi", risk: "severe", level: "Severe", alert: "Extreme Heat Wave Alert (44°C+)", temp: "43.5°C", safeShelters: ["Thyagaraj Stadium Relief Center", "Yamuna Sports Complex Shelter"], helpline: "1077 (Delhi Disaster Mgmt)", color: "#e53e5a" },
    { id: "assam", name: "Assam", state: "Assam", risk: "severe", level: "Severe", alert: "Brahmaputra Basin Flood Warning", temp: "29°C", safeShelters: ["Guwahati Relief Camp #4", "Kamrup Flood Shelter Center"], helpline: "1070 (Assam SDMA)", color: "#e53e5a" },
    { id: "uttarakhand", name: "Uttarakhand", state: "Uttarakhand", risk: "severe", level: "Severe", alert: "Landslide & Seismic Zone V Watch", temp: "21°C", safeShelters: ["Dehradun Disaster Relief Base", "Rishikesh Safe Transit Shelter"], helpline: "1070 / 112 (Disaster Response)", color: "#e53e5a" },
    { id: "odisha", name: "Odisha", state: "Odisha", risk: "moderate", level: "Moderate", alert: "Coastal Swell & Cyclone Watch", temp: "32°C", safeShelters: ["Bhubaneswar Cyclone Shelter 12", "Puri Coastal Multi-hazard Center"], helpline: "1070 (OSDMA)", color: "#ff9f1c" },
    { id: "maharashtra", name: "Maharashtra", state: "Maharashtra", risk: "moderate", level: "Moderate", alert: "Urban Heat & Pre-monsoon advisory", temp: "34°C", safeShelters: ["BKC Emergency Relief Ground", "Pune District Disaster Camp"], helpline: "1077 (Maharashtra Emergency)", color: "#ff9f1c" },
    { id: "west_bengal", name: "West Bengal", state: "West Bengal", risk: "moderate", level: "Moderate", alert: "Ganga Basin High Water Advisory", temp: "33°C", safeShelters: ["Kolkata North Disaster Relief Post", "Howrah Safe Evacuation Camp"], helpline: "1070 (WB Disaster Control)", color: "#ff9f1c" },
    { id: "rajasthan", name: "Rajasthan", state: "Rajasthan", risk: "moderate", level: "Moderate", alert: "High Temperature & Dry Dust Winds", temp: "42°C", safeShelters: ["Jaipur Safe Shelter Complex", "Jodhpur Relief Hub"], helpline: "1070 (Rajasthan SDMA)", color: "#ff9f1c" },
    { id: "gujarat", name: "Gujarat", state: "Gujarat", risk: "moderate", level: "Moderate", alert: "Coastal Gusty Winds Advisory", temp: "36°C", safeShelters: ["Ahmedabad Disaster Management Base", "Surat Multi-purpose Shelter"], helpline: "1070 (GSDMA Control)", color: "#ff9f1c" },
    { id: "bihar", name: "Bihar", state: "Bihar", risk: "moderate", level: "Moderate", alert: "Kosi River Tributary Monitoring", temp: "35°C", safeShelters: ["Patna River Relief Shelter", "Muzaffarpur Safe Camp"], helpline: "1070 (BSDMA Control)", color: "#ff9f1c" },
    { id: "himachal", name: "Himachal Pradesh", state: "Himachal Pradesh", risk: "moderate", level: "Moderate", alert: "High Altitude Flash Flood Warning", temp: "18°C", safeShelters: ["Shimla Safe Transit Center", "Kullu Disaster Camp"], helpline: "1070 (HPSDMA)", color: "#ff9f1c" },
    { id: "karnataka", name: "Karnataka", state: "Karnataka", risk: "safe", level: "Low / Safe", alert: "Normal Weather Conditions", temp: "28°C", safeShelters: ["Bengaluru Central Shelter Base", "Mysuru Safe Evacuation Point"], helpline: "1070 (KSDMA Emergency)", color: "#1faa6b" },
    { id: "kerala", name: "Kerala", state: "Kerala", risk: "safe", level: "Low / Safe", alert: "Normal Weather & Favorable Sea", temp: "29°C", safeShelters: ["Kochi Safe Coastal Camp", "Trivandrum Disaster Hub"], helpline: "1077 (KSDMA)", color: "#1faa6b" },
    { id: "tamil_nadu", name: "Tamil Nadu", state: "Tamil Nadu", risk: "safe", level: "Low / Safe", alert: "Normal Conditions - Mild Breeze", temp: "31°C", safeShelters: ["Chennai Coastal Shelter #3", "Coimbatore Relief Camp"], helpline: "1070 (TNDMA)", color: "#1faa6b" },
    { id: "telangana", name: "Telangana", state: "Telangana", risk: "safe", level: "Low / Safe", alert: "Normal Seasonal Temperature", temp: "33°C", safeShelters: ["Hyderabad Disaster Relief Camp", "Warangal Safe Hub"], helpline: "1070 (Telangana SDMA)", color: "#1faa6b" },
    { id: "madhya_pradesh", name: "Madhya Pradesh", state: "Madhya Pradesh", risk: "safe", level: "Low / Safe", alert: "Normal Conditions across districts", temp: "35°C", safeShelters: ["Bhopal Safe Base Camp", "Indore Disaster Support Base"], helpline: "1070 (MPSDMA)", color: "#1faa6b" },
    { id: "punjab", name: "Punjab", state: "Punjab", risk: "safe", level: "Low / Safe", alert: "Normal Weather & Clear Skies", temp: "32°C", safeShelters: ["Amritsar Emergency Hub", "Ludhiana Relief Center"], helpline: "112 / 1070 (Punjab Disaster)", color: "#1faa6b" },
    { id: "haryana", name: "Haryana", state: "Haryana", risk: "safe", level: "Low / Safe", alert: "Normal Conditions", temp: "33°C", safeShelters: ["Gurugram Emergency Shelter", "Panchkula Safe Post"], helpline: "1070 (Haryana SDMA)", color: "#1faa6b" },
    { id: "goa", name: "Goa", state: "Goa", risk: "safe", level: "Low / Safe", alert: "Normal Coastal Sea & Weather", temp: "29°C", safeShelters: ["Panaji Coastal Safe Shelter"], helpline: "1077 (Goa Emergency)", color: "#1faa6b" },
  ];

  async function cityList() {
    if (!state.cities) state.cities = (await api("hazards/cities")).cities;
    return state.cities;
  }

  function getIndiaSVG(size = 180, isInteractive = false) {
    const w = size;
    const h = Math.round(size * 1.15);
    return `
      <svg viewBox="0 0 320 370" width="${w}" height="${h}" style="filter:drop-shadow(0 4px 12px rgba(27,31,94,0.08))" class="dash-map-svg" aria-label="India Risk Map">
        <defs>
          <linearGradient id="mapGlow" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#fff" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <!-- India Outline / Geographic Shapes with Danger Zones -->
        <!-- North: J&K / Ladakh (Moderate/Safe) -->
        <path d="M110 35 L135 15 L160 25 L165 55 L130 65 L110 50 Z" fill="#ffb35c" stroke="#fff" stroke-width="2" data-zone="himachal" class="map-state-path"><title>Himachal / J&K: Moderate</title></path>
        <!-- Uttarakhand (Severe / Red) -->
        <path d="M145 65 L175 60 L185 85 L155 90 Z" fill="#e53e5a" stroke="#fff" stroke-width="2" data-zone="uttarakhand" class="map-state-path"><title>Uttarakhand: Severe (Landslide / Seismic Watch)</title></path>
        <!-- Punjab / Haryana (Safe / Green) -->
        <path d="M100 65 L130 65 L125 95 L95 90 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="punjab" class="map-state-path"><title>Punjab & Haryana: Safe</title></path>
        <!-- Delhi NCR (Severe / Red Point) -->
        <circle cx="132" cy="98" r="9" fill="#e53e5a" stroke="#fff" stroke-width="2" data-zone="delhi" class="map-state-path"><title>Delhi NCR: Severe (Heat Wave Alert)</title></circle>
        <!-- Rajasthan (Moderate / Orange) -->
        <path d="M65 95 L115 95 L125 155 L65 145 L50 115 Z" fill="#ff9f1c" stroke="#fff" stroke-width="2" data-zone="rajasthan" class="map-state-path"><title>Rajasthan: Moderate (Dry Heat Alert)</title></path>
        <!-- Uttar Pradesh (Moderate / Orange) -->
        <path d="M125 95 L185 90 L210 135 L145 145 Z" fill="#ffb35c" stroke="#fff" stroke-width="2" data-zone="delhi" class="map-state-path"><title>Uttar Pradesh: Moderate</title></path>
        <!-- Bihar (Moderate / Orange) -->
        <path d="M210 120 L250 125 L245 155 L205 150 Z" fill="#ff9f1c" stroke="#fff" stroke-width="2" data-zone="bihar" class="map-state-path"><title>Bihar: Moderate</title></path>
        <!-- West Bengal (Moderate) -->
        <path d="M245 135 L265 140 L255 190 L235 175 Z" fill="#ffb35c" stroke="#fff" stroke-width="2" data-zone="west_bengal" class="map-state-path"><title>West Bengal: Moderate</title></path>
        <!-- North-East & Assam (Severe / Red) -->
        <path d="M265 115 L310 110 L305 155 L260 145 Z" fill="#e53e5a" stroke="#fff" stroke-width="2" data-zone="assam" class="map-state-path"><title>Assam / North-East: Severe (Flood Advisory)</title></path>
        <!-- Gujarat (Moderate / Orange) -->
        <path d="M40 145 L85 145 L95 195 L50 195 L30 165 Z" fill="#ffb35c" stroke="#fff" stroke-width="2" data-zone="gujarat" class="map-state-path"><title>Gujarat: Moderate</title></path>
        <!-- Madhya Pradesh (Safe / Green) -->
        <path d="M105 145 L195 145 L185 205 L105 195 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="madhya_pradesh" class="map-state-path"><title>Madhya Pradesh: Safe (Low Risk)</title></path>
        <!-- Maharashtra (Moderate / Orange) -->
        <path d="M75 195 L165 195 L160 255 L85 245 Z" fill="#ff9f1c" stroke="#fff" stroke-width="2" data-zone="maharashtra" class="map-state-path"><title>Maharashtra: Moderate Risk</title></path>
        <!-- Odisha (Moderate / Orange) -->
        <path d="M195 175 L245 175 L225 225 L185 205 Z" fill="#ff9f1c" stroke="#fff" stroke-width="2" data-zone="odisha" class="map-state-path"><title>Odisha: Moderate (Cyclone Watch)</title></path>
        <!-- Telangana & Andhra Pradesh (Safe / Green) -->
        <path d="M140 235 L195 215 L190 290 L135 270 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="telangana" class="map-state-path"><title>Telangana & Andhra: Safe</title></path>
        <!-- Karnataka & Goa (Safe / Green) -->
        <path d="M95 245 L140 255 L130 315 L95 285 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="karnataka" class="map-state-path"><title>Karnataka: Safe (Low Risk)</title></path>
        <!-- Kerala (Safe / Green) -->
        <path d="M100 310 L125 315 L120 355 L105 345 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="kerala" class="map-state-path"><title>Kerala: Safe (Low Risk)</title></path>
        <!-- Tamil Nadu (Safe / Green) -->
        <path d="M125 310 L165 295 L145 358 L120 355 Z" fill="#1faa6b" stroke="#fff" stroke-width="2" data-zone="tamil_nadu" class="map-state-path"><title>Tamil Nadu: Safe (Low Risk)</title></path>
      </svg>`;
  }

  function donutRing(pct = 85, size = 110) {
    const r = 44, C = 2 * Math.PI * r;
    const strokeDash = (pct / 100) * C;
    return `
      <div style="position:relative;width:${size}px;height:${size}px;display:grid;place-items:center">
        <svg viewBox="0 0 100 100" style="width:100%;height:100%;transform:rotate(-90deg)">
          <circle cx="50" cy="50" r="${r}" fill="none" stroke="#e6f5f0" stroke-width="11"/>
          <circle cx="50" cy="50" r="${r}" fill="none" stroke="#1faa6b" stroke-width="11" stroke-linecap="round"
            stroke-dasharray="${strokeDash} ${C}" style="transition:stroke-dasharray 1.2s ease"/>
        </svg>
        <div style="position:absolute;font-size:20px;font-weight:800;color:#1b1f5e">${pct}%</div>
      </div>`;
  }

  /* ============================================================ DASHBOARD */
  async function dashboard() {
    loading();
    const [dash, loc, hist] = await Promise.all([
      api("dashboard"),
      api("aapdasense/location" + (state.city ? `?city=${encodeURIComponent(state.city)}` : "")).catch((e) => ({ error: e.message })),
      api("vault/history").catch(() => ({ events: [] })),
    ]);

    const u = dash.user || {};
    state.city = (loc.location && loc.location.city) || u.city || "New Delhi";
    const displayName = (u.full_name || "Himangi").split(" ")[0];
    const sev = loc.severity ? loc.severity.level : "green";
    const official = (loc.official_alerts || [])[0] || {
      event: "Heat Wave",
      area: "Delhi, Delhi",
      badge: "High",
      level: "orange",
    };

    const docBars = [
      { label: "Identity Documents", pct: 100, color: "green", fill: "#1faa6b" },
      { label: "Medical Documents", pct: 70, color: "blue", fill: "#3b82f6" },
      { label: "Financial Documents", pct: 80, color: "orange", fill: "#ff8a2a" },
      { label: "Education Documents", pct: 60, color: "purple", fill: "#8b5cf6" },
    ];

    view().innerHTML = `
      <!-- Greeting and City Selector matching picture -->
      <div class="row between wrap" style="margin-bottom:20px;align-items:flex-end">
        <div>
          <h1 style="font-size:28px;font-weight:800;color:#1b1f5e;letter-spacing:-0.4px">
            ${greeting()}, ${esc(displayName)}!
          </h1>
          <p style="color:#7a7f9d;margin-top:4px;font-size:15px;font-weight:500">Your personal safety overview.</p>
          <div style="width:50px;height:3px;border-radius:2px;background:#ff8a2a;margin-top:8px"></div>
        </div>
        <div style="text-align:right">
          <div class="loc-pill" id="locPillBtn">
            <span style="color:#ff8a2a">📍</span>
            <b>${esc(state.city)}, ${esc(loc.location?.state || "Delhi")}</b>
            <span style="font-size:10px;color:#8a8fae">⌵</span>
          </div>
          <div class="last-updated" style="margin-top:5px">Last Updated: 2:30 PM</div>
        </div>
      </div>

      <!-- ROW 1: 3 Top Status Cards -->
      <div class="grid g-main">
        <!-- Card 1: Current Location Risk -->
        <div class="card hover" style="background:linear-gradient(135deg, #eefbf4 0%, #ffffff 70%);border:1px solid #d4f2e3;position:relative;overflow:hidden">
          <svg viewBox="0 0 100 100" style="position:absolute;right:-15px;bottom:-15px;width:95px;height:95px;opacity:0.08;pointer-events:none" fill="#1faa6b">
            <path d="M50 5 L85 20 V50 C85 75 50 95 50 95 C50 95 15 75 15 50 V20 Z"/>
          </svg>
          <div class="row" style="gap:8px;margin-bottom:14px">
            <span style="color:#1faa6b;font-size:18px;line-height:1">●</span>
            <span style="font-weight:700;font-size:14px;color:#323663">Current Location Risk</span>
          </div>
          <div style="margin:6px 0">
            <div style="font-size:32px;font-weight:800;color:#1faa6b;letter-spacing:-0.5px">Normal</div>
            <div style="font-size:13px;color:#7a7f9d;font-weight:500;margin-top:2px">No active warnings</div>
          </div>
        </div>

        <!-- Card 2: AapdaSense Alert -->
        <div class="card hover" style="background:linear-gradient(135deg, #fff2f4 0%, #ffffff 70%);border:1px solid #ffd8df;display:flex;flex-direction:column;justify-content:space-between">
          <div>
            <div class="row" style="gap:8px;margin-bottom:12px">
              <span style="color:#e53e5a;font-size:18px">⚠</span>
              <span style="font-weight:700;font-size:14px;color:#323663">AapdaSense Alert</span>
            </div>
            <div style="font-size:22px;font-weight:800;color:#e53e5a">${esc(official.event)}</div>
            <div style="font-size:13px;color:#7a7f9d;margin-top:2px">${esc(official.area || "Delhi, Delhi")}</div>
            <div style="margin-top:10px">
              <span class="badge" style="background:#fee2e2;color:#dc2626;font-weight:700;padding:4px 12px">High</span>
            </div>
          </div>
          <div style="text-align:right;margin-top:14px">
            <a href="#/aapdasense" style="font-size:13px;font-weight:700;color:#e53e5a">View Details →</a>
          </div>
        </div>

        <!-- Card 3: Emergency Readiness -->
        <div class="card hover" style="border:1px solid #e7e9f5">
          <div class="row" style="gap:8px;margin-bottom:10px">
            <span style="font-size:18px">🏆</span>
            <span style="font-weight:700;font-size:14px;color:#323663">Emergency Readiness</span>
          </div>
          <div class="row" style="align-items:center;gap:18px;margin-top:4px">
            ${donutRing(85, 96)}
            <div>
              <div style="font-size:18px;font-weight:800;color:#1faa6b">Great!</div>
              <div style="font-size:13px;color:#7a7f9d;font-weight:500">Keep it up!</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ROW 2: Memory Vault, Document Readiness, Disaster Map -->
      <div class="grid g-main section-gap">
        <!-- Memory Vault Card -->
        <div class="card hover" style="border:1px solid #e7e9f5">
          <div class="row" style="gap:8px;margin-bottom:16px">
            <span style="width:30px;height:30px;background:#f3f0ff;color:#6d4cff;border-radius:8px;display:grid;place-items:center;font-size:15px">🔒</span>
            <span style="font-weight:700;font-size:15px;color:#1b1f5e">Memory Vault</span>
          </div>
          <div class="stat-row" style="margin:16px 0;justify-content:space-between">
            <div style="text-align:center">
              <b style="font-size:26px;color:#1b1f5e">12</b>
              <span style="font-size:12px;color:#7a7f9d;font-weight:600;display:block">Documents</span>
            </div>
            <div style="text-align:center">
              <b style="font-size:26px;color:#1b1f5e">10</b>
              <span style="font-size:12px;color:#7a7f9d;font-weight:600;display:block">Encrypted</span>
            </div>
            <div style="text-align:center">
              <b style="font-size:26px;color:#1b1f5e">75%</b>
              <span style="font-size:12px;color:#7a7f9d;font-weight:600;display:block">Used</span>
            </div>
          </div>
          <div style="margin-top:20px">
            <a class="btn-signin" href="#/vault" style="text-decoration:none;font-size:14px;padding:12px">
              Upload Document →
            </a>
          </div>
        </div>

        <!-- Document Readiness Card -->
        <div class="card hover" style="border:1px solid #e7e9f5">
          <div class="row" style="gap:8px;margin-bottom:12px">
            <span style="width:30px;height:30px;background:#eef4ff;color:#3b82f6;border-radius:8px;display:grid;place-items:center;font-size:15px">📄</span>
            <span style="font-weight:700;font-size:15px;color:#1b1f5e">Document Readiness</span>
          </div>
          ${docBars.map((b) => `
            <div class="bar-line" style="margin:10px 0">
              <div class="top" style="margin-bottom:4px">
                <span style="color:#4b5072;font-size:13px">${b.label}</span>
                <span style="color:#1b1f5e;font-weight:700">${b.pct}%</span>
              </div>
              <div class="track-bar" style="height:7px;background:#eef1fa">
                <div class="fill-bar" style="width:${b.pct}%;background:${b.fill};border-radius:99px"></div>
              </div>
            </div>`).join("")}
        </div>

        <!-- Disaster Map Card with India Danger & Safe Zones -->
        <div class="card hover" style="border:1px solid #e7e9f5;cursor:pointer" onclick="location.hash='#/map'">
          <div class="row between" style="margin-bottom:10px">
            <div class="row" style="gap:8px">
              <span style="width:30px;height:30px;background:#fff2e6;color:#ff8a2a;border-radius:8px;display:grid;place-items:center;font-size:15px">🗺️</span>
              <span style="font-weight:700;font-size:15px;color:#1b1f5e">Disaster Map</span>
            </div>
            <a href="#/map" style="font-size:13px;font-weight:700;color:#4b2fd6">View Map →</a>
          </div>
          
          <div class="dash-map-container" style="justify-content:center;align-items:center">
            ${getIndiaSVG(140)}
            <div class="dash-map-legend" style="padding-left:10px">
              <div><span class="legend-dot severe"></span>Severe</div>
              <div><span class="legend-dot moderate"></span>Moderate</div>
              <div><span class="legend-dot low"></span>Low</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ROW 3: Recent Activity & Quick Actions -->
      <div class="grid g-bottom section-gap">
        <!-- Recent Activity Card -->
        <div class="card" style="border:1px solid #e7e9f5">
          <div class="row between" style="margin-bottom:12px">
            <span style="font-weight:700;font-size:15px;color:#1b1f5e">Recent Activity</span>
            <a href="#/vault" style="font-size:13px;font-weight:700;color:#4b2fd6">View All →</a>
          </div>
          
          <div class="list-item" style="padding:10px 0">
            <span style="width:36px;height:36px;border-radius:50%;background:#e8f8f0;color:#1faa6b;display:grid;place-items:center;font-size:16px;flex:none">⬆️</span>
            <div class="grow" style="margin-left:8px">
              <div style="font-weight:700;color:#1b1f5e;font-size:13px">Document uploaded</div>
              <div class="meta" style="color:#7a7f9d;font-size:12px">Aadhaar Card.pdf</div>
            </div>
            <span class="meta" style="color:#9da2c0;font-size:12px">2h ago</span>
          </div>

          <div class="list-item" style="padding:10px 0">
            <span style="width:36px;height:36px;border-radius:50%;background:#eef4ff;color:#3b82f6;display:grid;place-items:center;font-size:16px;flex:none">👁️</span>
            <div class="grow" style="margin-left:8px">
              <div style="font-weight:700;color:#1b1f5e;font-size:13px">Vault accessed</div>
              <div class="meta" style="color:#7a7f9d;font-size:12px">by you</div>
            </div>
            <span class="meta" style="color:#9da2c0;font-size:12px">3h ago</span>
          </div>

          <div class="list-item" style="padding:10px 0">
            <span style="width:36px;height:36px;border-radius:50%;background:#fff3e6;color:#ff8a2a;display:grid;place-items:center;font-size:16px;flex:none">🔔</span>
            <div class="grow" style="margin-left:8px">
              <div style="font-weight:700;color:#1b1f5e;font-size:13px">Alert checked</div>
              <div class="meta" style="color:#7a7f9d;font-size:12px">Heat Wave - Delhi</div>
            </div>
            <span class="meta" style="color:#9da2c0;font-size:12px">5h ago</span>
          </div>
        </div>

        <!-- Quick Actions Card matching 4 colored blocks in picture -->
        <div class="card" style="border:1px solid #e7e9f5">
          <div class="row" style="gap:8px;margin-bottom:14px">
            <span style="color:#ff8a2a">⚡</span>
            <span style="font-weight:700;font-size:15px;color:#1b1f5e">Quick Actions</span>
          </div>
          <div class="grid g-4" style="gap:12px">
            <a href="#/vault" class="card hover" style="text-align:center;padding:18px 8px;background:#f3efff;border:1px solid #e8e0ff;box-shadow:none;border-radius:14px;display:flex;flex-direction:column;align-items:center;gap:8px">
              <span style="font-size:24px;color:#6d4cff">⬆️</span>
              <span style="font-weight:700;font-size:13px;color:#2a2e58">Upload Document</span>
            </a>

            <a href="#/aapdasense" class="card hover" style="text-align:center;padding:18px 8px;background:#fff5ea;border:1px solid #ffe6cc;box-shadow:none;border-radius:14px;display:flex;flex-direction:column;align-items:center;gap:8px">
              <span style="font-size:24px;color:#ff8a2a">⚠️</span>
              <span style="font-weight:700;font-size:13px;color:#2a2e58">Check Alerts</span>
            </a>

            <a href="#/family" class="card hover" style="text-align:center;padding:18px 8px;background:#edfcf4;border:1px solid #d4f8e5;box-shadow:none;border-radius:14px;display:flex;flex-direction:column;align-items:center;gap:8px">
              <span style="font-size:24px;color:#1faa6b">📞</span>
              <span style="font-weight:700;font-size:13px;color:#2a2e58">Emergency Contacts</span>
            </a>

            <a href="#/assistant" class="card hover" style="text-align:center;padding:18px 8px;background:#fff0f3;border:1px solid #ffd8e0;box-shadow:none;border-radius:14px;display:flex;flex-direction:column;align-items:center;gap:8px">
              <span style="font-size:24px;color:#e53e5a">🤖</span>
              <span style="font-weight:700;font-size:13px;color:#2a2e58">Ask AI Assistant</span>
            </a>
          </div>
        </div>
      </div>`;

    $("locPillBtn").onclick = async () => {
      const cities = await cityList();
      const current = state.city;
      const modal = document.createElement("div");
      modal.className = "modal-bg";
      modal.innerHTML = `
        <div class="modal" style="max-width:360px">
          <h3 style="margin-bottom:12px;color:#1b1f5e">Change Location</h3>
          <div class="stack" style="gap:8px;max-height:280px;overflow-y:auto;padding-right:4px">
            ${cities.map(c => `
              <button class="btn ${c.name === current ? "primary" : "soft"}" data-cname="${esc(c.name)}" style="justify-content:space-between">
                <span>${esc(c.name)}</span>
                <span class="small">${esc(c.state)}</span>
              </button>`).join("")}
          </div>
          <button class="btn block" style="margin-top:14px" id="closeCityModal">Cancel</button>
        </div>`;
      document.body.appendChild(modal);
      modal.querySelectorAll("[data-cname]").forEach(btn => {
        btn.onclick = () => {
          state.city = btn.dataset.cname;
          modal.remove();
          dashboard();
        };
      });
      modal.querySelector("#closeCityModal").onclick = () => modal.remove();
    };

    window.SLApp.setBadge(sev === "green" ? 2 : 3);
  }

  /* ================================================================ LIVE DISASTER MAP */
  async function map() {
    loading();
    const m = await api("aapdasense/map");
    const activeFilter = state.mapFilter || "all";

    const filteredZones = INDIAN_ZONES.filter(z => {
      if (activeFilter === "severe") return z.risk === "severe";
      if (activeFilter === "moderate") return z.risk === "moderate";
      if (activeFilter === "safe") return z.risk === "safe";
      return true;
    });

    view().innerHTML = `
      <div class="row between wrap" style="margin-bottom:16px">
        <div>
          <h1 class="page-title">Live Disaster Map — India</h1>
          <p class="page-sub" style="margin:0">Real-time risk zones, official advisories, safe evacuation shelters, and live hazards.</p>
        </div>
        <div class="row">
          <button class="btn ${activeFilter === "all" ? "primary" : "soft"}" id="fltAll">All Zones (${INDIAN_ZONES.length})</button>
          <button class="btn ${activeFilter === "severe" ? "primary" : "soft"}" style="color:#e53e5a" id="fltSevere">🔴 Danger / Severe (${INDIAN_ZONES.filter(z=>z.risk==='severe').length})</button>
          <button class="btn ${activeFilter === "moderate" ? "primary" : "soft"}" style="color:#ff9f1c" id="fltMod">🟡 Moderate (${INDIAN_ZONES.filter(z=>z.risk==='moderate').length})</button>
          <button class="btn ${activeFilter === "safe" ? "primary" : "soft"}" style="color:#1faa6b" id="fltSafe">🟢 Safe Zones (${INDIAN_ZONES.filter(z=>z.risk==='safe').length})</button>
        </div>
      </div>

      <div class="grid" style="grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr); gap: 18px; align-items: start">
        <!-- Interactive Vector Map & Leaflet Map Card -->
        <div class="card" style="padding:16px">
          <div class="row between" style="margin-bottom:12px">
            <div class="row" style="gap:12px;font-size:13px;font-weight:700">
              <span><span class="legend-dot severe"></span>Danger / Severe</span>
              <span><span class="legend-dot moderate"></span>Moderate Risk</span>
              <span><span class="legend-dot low"></span>Safe Zone</span>
            </div>
            <div class="row">
              <button class="btn sm soft" id="toggleMapType">🗺️ Leaflet Satellite Map</button>
            </div>
          </div>

          <!-- Fast SVG Vector Map (Instant Load, Zero Lag) -->
          <div id="vectorMapWrap" style="background:linear-gradient(180deg, #f7f9fd 0%, #eef2fb 100%);border-radius:14px;padding:20px;text-align:center;min-height:440px;display:flex;align-items:center;justify-content:center">
            ${getIndiaSVG(320, true)}
          </div>

          <!-- Leaflet Map Container -->
          <div id="leafletMapWrap" style="display:none">
            <div id="map" class="map"></div>
          </div>
        </div>

        <!-- State / Danger Zone Details Panel -->
        <div class="card" style="padding:20px">
          <div class="row between" style="margin-bottom:14px">
            <b style="font-size:16px;color:#1b1f5e">State & City Danger Zones</b>
            <input id="stateSearch" class="input sm" placeholder="Search state or city..." style="width:170px;padding:6px 12px;border-radius:10px" />
          </div>
          
          <div id="zoneList" class="stack" style="gap:10px;max-height:430px;overflow-y:auto;padding-right:4px">
            ${filteredZones.map(z => `
              <div class="card hover" data-zid="${z.id}" style="padding:12px 14px;border:1px solid #eef0f8;box-shadow:none;border-left:4px solid ${z.color};cursor:pointer">
                <div class="row between">
                  <b style="font-size:14px;color:#1b1f5e">${esc(z.name)}</b>
                  <span class="badge" style="background:${z.risk==='severe'?'#fee2e2':z.risk==='moderate'?'#fef3c7':'#dcfce7'};color:${z.color}">${z.level}</span>
                </div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px"><b>Advisory:</b> ${esc(z.alert)}</div>
                <div class="row between" style="margin-top:6px;font-size:11px;color:#9ca3af">
                  <span>Temp: ${z.temp}</span>
                  <span style="color:#4b2fd6;font-weight:600">Click for Shelters & Helplines →</span>
                </div>
              </div>`).join("")}
          </div>
        </div>
      </div>`;

    // Filter event handlers
    $("fltAll").onclick = () => { state.mapFilter = "all"; map(); };
    $("fltSevere").onclick = () => { state.mapFilter = "severe"; map(); };
    $("fltMod").onclick = () => { state.mapFilter = "moderate"; map(); };
    $("fltSafe").onclick = () => { state.mapFilter = "safe"; map(); };

    // Search filter
    $("stateSearch").oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      document.querySelectorAll("#zoneList [data-zid]").forEach(el => {
        const text = el.textContent.toLowerCase();
        el.style.display = text.includes(q) ? "block" : "none";
      });
    };

    // State Click Details Modal
    function showZoneModal(zoneId) {
      const z = INDIAN_ZONES.find(item => item.id === zoneId) || INDIAN_ZONES[0];
      const modal = document.createElement("div");
      modal.className = "modal-bg";
      modal.innerHTML = `
        <div class="modal" style="max-width:440px">
          <div class="row between" style="margin-bottom:12px">
            <div class="row" style="gap:10px">
              <span style="font-size:22px">📍</span>
              <div>
                <b style="font-size:18px;color:#1b1f5e">${esc(z.name)}</b>
                <div class="small muted">${esc(z.state)}</div>
              </div>
            </div>
            <span class="badge" style="background:${z.risk==='severe'?'#fee2e2':z.risk==='moderate'?'#fef3c7':'#dcfce7'};color:${z.color}">${z.level}</span>
          </div>

          <div style="margin:14px 0;padding:12px;background:#f9fafb;border-radius:12px;font-size:13px">
            <b style="color:#1b1f5e">Current Warning:</b>
            <div style="color:${z.color};font-weight:600;margin-top:2px">${esc(z.alert)}</div>
            <div class="small muted" style="margin-top:4px">Temperature: ${z.temp} · Live IMD / CWC feed</div>
          </div>

          <div style="margin-bottom:12px">
            <b style="font-size:13px;color:#1b1f5e">Safe Evacuation Shelters & Relief Bases:</b>
            <ul class="small" style="margin-top:6px;padding-left:18px;color:#4b5563">
              ${z.safeShelters.map(s => `<li>${esc(s)}</li>`).join("")}
            </ul>
          </div>

          <div style="margin-bottom:16px">
            <b style="font-size:13px;color:#1b1f5e">Official Emergency Helplines:</b>
            <div style="margin-top:6px;padding:8px 12px;background:#eff6ff;color:#1d4ed8;border-radius:10px;font-weight:700;font-size:13px">
              📞 ${esc(z.helpline)}
            </div>
          </div>

          <div class="row" style="gap:10px">
            <a class="btn primary grow" href="#/emergency" onclick="document.querySelector('.modal-bg')?.remove()">Emergency Mode</a>
            <button class="btn" id="closeZoneModal">Close</button>
          </div>
        </div>`;
      document.body.appendChild(modal);
      modal.querySelector("#closeZoneModal").onclick = () => modal.remove();
    }

    document.querySelectorAll("[data-zid]").forEach(el => {
      el.onclick = () => showZoneModal(el.dataset.zid);
    });

    document.querySelectorAll(".map-state-path").forEach(path => {
      path.style.cursor = "pointer";
      path.onclick = () => showZoneModal(path.dataset.zone);
    });

    // Toggle Leaflet view
    let isLeaflet = false;
    $("toggleMapType").onclick = () => {
      isLeaflet = !isLeaflet;
      $("vectorMapWrap").style.display = isLeaflet ? "none" : "flex";
      $("leafletMapWrap").style.display = isLeaflet ? "block" : "none";
      $("toggleMapType").textContent = isLeaflet ? "🗺️ Fast Vector Map" : "🛰️ Leaflet Satellite Map";
      if (isLeaflet && window.L && !window._leafMap) {
        initLeafletMap(m);
      }
    };

    function initLeafletMap(data) {
      const leaflet = L.map("map").setView([22.6, 79.0], 4.5);
      window._leafMap = leaflet;
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 10, attribution: "© OpenStreetMap contributors" }).addTo(leaflet);
      
      // Add Indian zones as colored circles
      INDIAN_ZONES.forEach(z => {
        const c = (data.cities || []).find(city => city.state === z.state || city.name.includes(z.name)) || { lat: 28.6139, lon: 77.2090 };
        L.circle([c.lat, c.lon], {
          radius: z.risk === "severe" ? 90000 : z.risk === "moderate" ? 65000 : 45000,
          color: z.color,
          fillColor: z.color,
          fillOpacity: 0.35,
          weight: 2
        }).bindPopup(`<b>${esc(z.name)}</b><br><span style="color:${z.color};font-weight:700">${z.level}</span><br>${esc(z.alert)}<br>Shelter: ${esc(z.safeShelters[0])}`).addTo(leaflet);
      });

      // USGS Earthquakes
      (data.events || []).forEach(e => {
        const quake = e.kind === "earthquake";
        L.circleMarker([e.lat, e.lon], {
          radius: quake ? 5 + (e.magnitude || 0) * 2 : 7,
          color: quake ? "#e53e5a" : "#ff9f1c",
          fillOpacity: 0.6,
          weight: 1.5
        }).bindPopup(`<b>${esc(e.title)}</b><br>${esc(e.category)}<br><small>${fmtDate(e.time)}</small>`).addTo(leaflet);
      });
    }
  }

  /* ========================================================= AAPDASENSE */
  async function aapdasense() {
    loading();
    const c = state.city || "New Delhi";
    const [loc, ov] = await Promise.all([api(`aapdasense/location?city=${encodeURIComponent(c)}`), api("aapdasense/overview")]);
    state.city = loc.location.city;
    const sev = loc.severity;
    const official = (loc.official_alerts || [])[0];

    view().innerHTML = `
      <div class="row between wrap" style="margin-bottom:18px">
        <div>
          <h1 class="page-title">AapdaSense — Disaster Intelligence</h1>
          <p class="page-sub" style="margin:0">Official government warnings and scientific early-warning telemetry.</p>
        </div>
        <div class="loc-pill" id="asCityBtn">📍 ${esc(state.city)} ⌵</div>
      </div>

      <div class="card" style="margin-bottom:18px;border-left:5px solid ${sev.level==='red'?'#e53e5a':sev.level==='orange'?'#ff8a2a':'#1faa6b'}">
        <div class="row" style="align-items:center;gap:18px;flex-wrap:wrap">
          ${sevIcon(sev.level)}
          <div class="grow">
            <div class="small muted">Location Severity Status</div>
            <div class="big sev-text ${sev.level}">${SEV[sev.level].label}</div>
            <div class="small muted">${esc(SEV[sev.level].text)}</div>
          </div>
          <div>
            <a class="btn primary" href="#/map">View Danger & Safe Zones on Map →</a>
          </div>
        </div>
      </div>

      <div class="grid g-2">
        <div class="card">
          <div class="card-title">Active Official Alerts</div>
          ${official ? `
            <div style="padding:14px;background:#fff1f2;border-radius:12px;border:1px solid #ffe4e6">
              <div class="row between">
                <b style="color:#e11d48;font-size:16px">${esc(official.event)}</b>
                <span class="badge red">High</span>
              </div>
              <div class="small muted" style="margin:6px 0">${esc(official.issuer)} · ${esc(official.area)}</div>
              <p style="font-size:13px;color:#374151">${esc(official.instruction || "")}</p>
            </div>` : `<p class="muted">No official warnings in this district right now.</p>`}
        </div>

        <div class="card">
          <div class="card-title">Forecast & Local Weather</div>
          ${loc.forecast ? `
            <div class="grid g-3" style="gap:10px">
              <div class="card" style="box-shadow:none;background:#f8faff;text-align:center;padding:12px">
                <div class="small muted">Rain probability</div>
                <b style="font-size:20px">${loc.forecast.next_24h.max_rain_probability ?? 10}%</b>
              </div>
              <div class="card" style="box-shadow:none;background:#f8faff;text-align:center;padding:12px">
                <div class="small muted">Max wind</div>
                <b style="font-size:20px">${loc.forecast.next_24h.max_wind_kmh ?? 15} km/h</b>
              </div>
              <div class="card" style="box-shadow:none;background:#f8faff;text-align:center;padding:12px">
                <div class="small muted">Temperature</div>
                <b style="font-size:20px">${loc.forecast.next_24h.max_temp_c ?? 42}°C</b>
              </div>
            </div>` : `<p class="muted">Weather forecast synced via Open-Meteo.</p>`}
        </div>
      </div>`;

    $("asCityBtn").onclick = () => { location.hash = "#/"; };
  }

  /* ============================================================ DOCUMENTS */
  async function documents() {
    loading();
    const [cl, rec] = await Promise.all([api("checklist"), api("recommendations").catch(() => ({ recommendations: [], onboarded: true }))]);
    const groups = {};
    cl.items.forEach((i) => (groups[i.group] ||= []).push(i));
    view().innerHTML = `
      <h1 class="page-title">Document Recommendations</h1>
      <p class="page-sub">Mark each essential document as uploaded, pending, or not applicable.</p>
      <div class="grid g-2">
        ${Object.entries(groups).map(([g, items]) => `
          <div class="card">
            <div class="card-title">${esc(g)} Documents <span class="small muted" style="margin-left:auto">${items.filter(i => i.status === "uploaded").length}/${items.length} Ready</span></div>
            ${items.map(i => `
              <div class="list-item" style="align-items:flex-start">
                <div class="grow">
                  <div class="row"><b>${esc(i.label)}</b> ${i.essential ? '<span class="badge purple">Essential</span>' : ""}</div>
                  <div class="small muted">${esc(i.why)}</div>
                </div>
                <select class="input" data-doc="${esc(i.key)}" style="width:auto;padding:6px 8px;border-radius:8px">
                  ${["pending", "uploaded", "not_applicable"].map(s => `<option value="${s}" ${s === i.status ? "selected" : ""}>${s.replace("_", " ")}</option>`).join("")}
                </select>
              </div>`).join("")}
          </div>`).join("")}
      </div>`;
    view().querySelectorAll("select[data-doc]").forEach((s) => {
      s.onchange = async () => {
        await api(`checklist/${encodeURIComponent(s.dataset.doc)}`, { method: "PUT", body: { status: s.value } });
        toast("Updated document readiness.");
      };
    });
  }

  /* ============================================================ PLANNER */
  async function planner() {
    loading();
    const [cl, rd] = await Promise.all([api("checklist"), api("readiness")]);
    view().innerHTML = `
      <h1 class="page-title">Emergency Planner</h1>
      <p class="page-sub">Readiness score: <b>${rd.score}%</b>. Complete items to prepare your household.</p>
      <div class="grid g-2">
        <div class="card">
          <div class="card-title">Emergency Supplies Kit</div>
          ${cl.supplies.map(s => `
            <div class="list-item">
              <label class="check grow"><input type="checkbox" data-sup="${esc(s.key)}" ${s.status === "uploaded" ? "checked" : ""} /> <span>${esc(s.label)}</span></label>
            </div>`).join("")}
        </div>
        <div class="card">
          <div class="card-title">Family Meeting Plan</div>
          <p class="small muted">Agree on an emergency reunion point outside your immediate building or neighborhood.</p>
          <div class="field" style="margin-top:14px">
            <input class="input" id="planPoint" placeholder="e.g., Community center or landmark" value="City Community Park Gates" />
          </div>
          <button class="btn primary" id="savePlan">Save Meeting Point</button>
        </div>
      </div>`;
    view().querySelectorAll("[data-sup]").forEach(cb => {
      cb.onchange = async () => {
        await api(`checklist/${encodeURIComponent(cb.dataset.sup)}`, { method: "PUT", body: { status: cb.checked ? "uploaded" : "pending" } });
        toast("Updated supply readiness.");
      };
    });
    $("savePlan").onclick = () => toast("Emergency meeting point updated.");
  }

  /* ============================================================ FAMILY */
  async function family() {
    loading();
    const fam = await api("family");
    view().innerHTML = `
      <div class="row between wrap" style="margin-bottom:18px">
        <div>
          <h1 class="page-title">Family Safety Network</h1>
          <p class="page-sub" style="margin:0">Emergency contacts and one-touch family SOS broadcast.</p>
        </div>
        <button class="btn danger" id="sosBtn">🆘 Send SOS Alert</button>
      </div>

      <div class="grid g-2">
        <div class="card">
          <div class="card-title">Saved Contacts</div>
          ${fam.members.map(m => `
            <div class="list-item">
              <div class="grow">
                <b>${esc(m.name)}</b> <span class="badge gray">${esc(m.relation)}</span>
                <div class="small muted">${esc(m.phone)} · ${esc(m.email)}</div>
              </div>
              <a class="btn sm soft" href="tel:${esc(m.phone)}">Call</a>
            </div>`).join("")}
        </div>

        <div class="card">
          <div class="card-title">Add Family Member</div>
          <form id="addFamForm">
            <div class="field"><input class="input" id="famName" placeholder="Full Name" required /></div>
            <div class="field"><input class="input" id="famRel" placeholder="Relation (e.g. Sister, Father)" required /></div>
            <div class="field"><input class="input" id="famPhone" placeholder="Mobile Phone Number" required /></div>
            <button class="btn primary block" type="submit">Add Contact</button>
          </form>
        </div>
      </div>`;
    $("sosBtn").onclick = async () => {
      await api("family/sos", { method: "POST", body: { message: "Emergency! I need assistance." } });
      toast("Emergency SOS recorded and contacts notified.", "err");
    };
    $("addFamForm").onsubmit = async (e) => {
      e.preventDefault();
      await api("family", { method: "POST", body: { name: $("famName").value, relation: $("famRel").value, phone: $("famPhone").value } });
      toast("Contact added.");
      family();
    };
  }

  /* ============================================================ EMERGENCY */
  async function emergency() {
    loading();
    const em = await api("emergency");
    view().innerHTML = `
      <div class="emergency" style="margin-bottom:20px">
        <h1>Emergency Mode Active</h1>
        <p>If you or someone is in immediate danger, dial 112 immediately.</p>
        <div class="row" style="margin-top:16px;gap:12px">
          <a class="big-btn call" href="tel:112" style="padding:16px 28px">📞 Call 112</a>
          <button class="big-btn" id="emSosBtn" style="padding:16px 28px;background:#fff;color:#e53e5a">🆘 Broadcast SOS</button>
        </div>
      </div>
      <div class="grid g-2">
        <div class="card">
          <div class="card-title">Emergency Helplines (India)</div>
          <div class="list-item"><div><b>Police / National Emergency</b></div><a class="btn sm danger" href="tel:112">112</a></div>
          <div class="list-item"><div><b>Ambulance</b></div><a class="btn sm danger" href="tel:108">108</a></div>
          <div class="list-item"><div><b>Fire Station</b></div><a class="btn sm danger" href="tel:101">101</a></div>
          <div class="list-item"><div><b>Disaster Helpline</b></div><a class="btn sm danger" href="tel:1077">1077</a></div>
        </div>
        <div class="card">
          <div class="card-title">Immediate Action Checklist</div>
          <ul class="small stack" style="padding-left:18px;margin-top:10px">
            <li>Take your waterproof emergency document bag.</li>
            <li>Keep drinking water, battery power bank, and vital prescriptions.</li>
            <li>Evacuate to designated safe shelters if advised by authorities.</li>
          </ul>
        </div>
      </div>`;
    $("emSosBtn").onclick = async () => {
      await api("family/sos", { method: "POST", body: { message: "I am in Emergency Mode." } });
      toast("SOS Alert sent to family contacts.", "err");
    };
  }

  /* ============================================================ SETTINGS */
  async function settings() {
    loading();
    const me = await api("auth/me");
    const u = me.user;
    view().innerHTML = `
      <h1 class="page-title">Settings</h1>
      <p class="page-sub">Manage your personal profile, safety preferences, and storage.</p>
      <div class="card" style="max-width:560px">
        <div class="card-title">Profile Information</div>
        <form id="settForm">
          <div class="field"><span>Full Name</span><input class="input" id="stName" value="${esc(u.full_name)}" /></div>
          <div class="field"><span>Primary City</span><input class="input" id="stCity" value="${esc(u.city || "New Delhi")}" /></div>
          <div class="field"><span>Blood Group</span><input class="input" id="stBlood" value="${esc(u.blood_group || "B+")}" /></div>
          <button class="btn primary" type="submit">Save Changes</button>
        </form>
      </div>`;
    $("settForm").onsubmit = async (e) => {
      e.preventDefault();
      await api("settings/profile", { method: "PUT", body: { full_name: $("stName").value, city: $("stCity").value, blood_group: $("stBlood").value } });
      toast("Profile updated successfully.");
      window.SLApp.refreshUser();
    };
  }

  return { dashboard, aapdasense, map, documents, planner, family, emergency, settings };
})();
