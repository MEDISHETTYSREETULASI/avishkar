/**
 * map.js — Interactive Leaflet map with RAG status markers, filter controls,
 * real-time updates, and Quick View detail modal.
 */

window.InstituteMap = (function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return {};

  let map;
  let markers = [];
  let allInstitutes = [];
  let activeRagFilter = "all";
  let activeTypeFilter = "all";
  let searchQuery = "";

  // RAG Colors & Labels
  const RAG_CONFIG = {
    red: {
      color: "#DC2626",
      fillColor: "#EF4444",
      label: "High Risk",
      badgeClass: "bg-red-100 text-red-700 border border-red-200",
    },
    amber: {
      color: "#D97706",
      fillColor: "#F59E0B",
      label: "Medium Risk",
      badgeClass: "bg-amber-100 text-amber-700 border border-amber-200",
    },
    green: {
      color: "#16A34A",
      fillColor: "#22C55E",
      label: "Low Risk",
      badgeClass: "bg-green-100 text-green-700 border border-green-200",
    },
  };

  // Initialize Map
  function initMap() {
    map = L.map("map", {
      center: [22.5937, 78.9629], // Geographic centre of India
      zoom: 5,
      zoomControl: true,
      scrollWheelZoom: true,
    });

    // Clean OpenStreetMap CartoDB Positron style / standard OSM
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map);

    loadInstitutes();
    setupFilterListeners();
  }

  // Fetch Institutes from API
  async function loadInstitutes() {
    try {
      const response = await fetch("/api/institutes");
      if (!response.ok) throw new Error("Failed to load institutes");
      allInstitutes = await response.json();
      renderMarkers();
    } catch (err) {
      console.error("[Map] Load error:", err);
      mapEl.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-slate-400 p-6">
          <i data-lucide="alert-circle" class="w-8 h-8 text-amber-500 mb-2"></i>
          <p class="text-sm font-medium text-slate-700">Unable to load map data</p>
          <p class="text-xs text-slate-400 mt-1">Please check your connection and refresh.</p>
        </div>
      `;
      if (window.lucide) lucide.createIcons();
    }
  }

  // Render / Filter Markers
  function renderMarkers() {
    // Clear existing markers
    markers.forEach((m) => map.removeLayer(m));
    markers = [];

    const filtered = allInstitutes.filter((inst) => {
      const matchesRag =
        activeRagFilter === "all" || inst.rag === activeRagFilter;
      const matchesType =
        activeTypeFilter === "all" || inst.type === activeTypeFilter;
      const query = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !query ||
        inst.name.toLowerCase().includes(query) ||
        inst.district.toLowerCase().includes(query) ||
        inst.state.toLowerCase().includes(query);

      return matchesRag && matchesType && matchesSearch;
    });

    filtered.forEach((inst) => {
      const cfg = RAG_CONFIG[inst.rag] || RAG_CONFIG.amber;

      // Custom marker design
      const isHighRisk = inst.rag === "red";
      const marker = L.circleMarker([inst.lat, inst.lng], {
        radius: isHighRisk ? 11 : 9,
        color: cfg.color,
        fillColor: cfg.fillColor,
        fillOpacity: 0.85,
        weight: 2.5,
        className: isHighRisk ? "leaflet-marker-pulse" : "",
      }).addTo(map);

      // Interactive Popup content
      const popupHtml = `
        <div class="p-1 max-w-xs font-sans">
          <div class="flex items-center justify-between gap-2 mb-1.5">
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${cfg.badgeClass}">
              ${cfg.label} (${Math.round(inst.risk_score)})
            </span>
            <span class="text-[10px] text-slate-400 font-medium">Cap: ${inst.reported_capacity}</span>
          </div>
          <h4 class="font-bold text-slate-900 text-sm leading-snug mb-1">${inst.name}</h4>
          <p class="text-xs text-slate-500 mb-2">
            <i data-lucide="map-pin" class="w-3 h-3 inline mr-0.5 text-slate-400"></i>
            ${inst.district}, ${inst.state}
          </p>

          <div class="grid grid-cols-2 gap-1.5 text-[11px] bg-slate-50 rounded-lg p-2 mb-2.5 border border-slate-100">
            <div>
              <span class="text-slate-400 block text-[10px]">Type</span>
              <span class="font-semibold text-slate-700">${inst.type_label}</span>
            </div>
            <div>
              <span class="text-slate-400 block text-[10px]">Open Flags</span>
              <span class="font-bold ${inst.open_flags > 0 ? "text-red-600" : "text-green-600"}">${inst.open_flags}</span>
            </div>
          </div>

          <button onclick="window.InstituteMap.openQuickView(${inst.id})"
                  class="w-full bg-navy hover:bg-navy-700 text-white text-xs font-semibold py-1.5 px-3 rounded-md transition-colors flex items-center justify-center gap-1.5 shadow-sm">
            <i data-lucide="info" class="w-3.5 h-3.5"></i>
            Quick View Details
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml, { maxWidth: 260, minWidth: 220 });
      marker.on("popupopen", () => {
        if (window.lucide) lucide.createIcons();
      });

      markers.push(marker);
    });

    // Auto fit bounds to visible markers
    if (markers.length > 0) {
      const group = L.featureGroup(markers);
      map.fitBounds(group.getBounds(), { padding: [40, 40], maxZoom: 12 });
    }

    // Update count in UI if element exists
    const countEl = document.getElementById("map-institutes-count");
    if (countEl) {
      countEl.textContent = `${filtered.length} of ${allInstitutes.length} institutes visible`;
    }
  }

  // Setup Event Listeners for Filters
  function setupFilterListeners() {
    // RAG filter buttons
    document.querySelectorAll("[data-map-rag-filter]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        document
          .querySelectorAll("[data-map-rag-filter]")
          .forEach((b) => b.classList.remove("ring-2", "ring-navy", "font-bold"));
        btn.classList.add("ring-2", "ring-navy", "font-bold");
        activeRagFilter = btn.getAttribute("data-map-rag-filter");
        renderMarkers();
      });
    });

    // Type filter select
    const typeSelect = document.getElementById("map-type-filter");
    if (typeSelect) {
      typeSelect.addEventListener("change", (e) => {
        activeTypeFilter = e.target.value;
        renderMarkers();
      });
    }

    // Search input
    const searchInput = document.getElementById("map-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value;
        renderMarkers();
      });
    }
  }

  // Quick View Modal
  async function openQuickView(instituteId) {
    const modal = document.getElementById("institute-quickview-modal");
    if (!modal) return;

    const content = document.getElementById("quickview-content");
    content.innerHTML = `
      <div class="flex items-center justify-center py-12">
        <i data-lucide="loader" class="w-8 h-8 text-teal animate-spin"></i>
      </div>
    `;
    modal.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();

    try {
      const res = await fetch(`/api/institutes/${instituteId}`);
      if (!res.ok) throw new Error("Institute not found");
      const data = await res.json();
      const cfg = RAG_CONFIG[data.rag] || RAG_CONFIG.amber;

      content.innerHTML = `
        <div class="space-y-4">
          <!-- Header -->
          <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-bold px-2.5 py-0.5 rounded-full ${cfg.badgeClass}">
                  ${cfg.label} · Score ${data.risk_score}
                </span>
                <span class="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">
                  ${data.type_label}
                </span>
              </div>
              <h3 class="text-lg font-bold text-slate-900">${data.name}</h3>
              <p class="text-xs text-slate-500">${data.address}</p>
            </div>
          </div>

          <!-- Quick Stats Grid -->
          <div class="grid grid-cols-3 gap-3 text-center">
            <div class="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <p class="text-[11px] text-slate-500">Capacity</p>
              <p class="text-sm font-bold text-slate-800">${data.reported_capacity} Residents</p>
            </div>
            <div class="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <p class="text-[11px] text-slate-500">Annual Grant</p>
              <p class="text-sm font-bold text-teal">₹${data.grant_amount_lakhs} L</p>
            </div>
            <div class="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <p class="text-[11px] text-slate-500">Open Flags</p>
              <p class="text-sm font-bold ${data.open_flags_count > 0 ? "text-red-600" : "text-green-600"}">${data.open_flags_count}</p>
            </div>
          </div>

          <!-- Latest Attendance & CCTV Status -->
          <div class="bg-navy/5 border border-navy/10 rounded-xl p-3">
            <div class="flex items-center justify-between text-xs mb-1.5">
              <span class="font-semibold text-navy">Latest Attendance &amp; Headcount</span>
              <span class="text-slate-500">${data.latest_attendance?.date || "No recent record"}</span>
            </div>
            <div class="flex items-center justify-between text-xs">
              <span>Reported: <strong>${data.latest_attendance?.reported_count ?? "—"}</strong></span>
              <span>CCTV Detected: <strong>${data.latest_attendance?.cctv_count ?? "—"}</strong></span>
              <span>Status: ${
                data.latest_attendance?.mismatch
                  ? '<span class="text-red-600 font-bold">⚠️ Mismatch</span>'
                  : '<span class="text-green-600 font-bold">✓ Reconciled</span>'
              }</span>
            </div>
          </div>

          <!-- Contact & Registration -->
          <div class="text-xs space-y-1.5 bg-slate-50 p-3 rounded-xl border border-slate-100">
            <div class="flex justify-between">
              <span class="text-slate-500">Contact Person:</span>
              <span class="font-medium text-slate-800">${data.contact_name} (${data.contact_phone})</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">NGO Registration:</span>
              <span class="font-mono text-slate-700">${data.ngo_reg}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Last Field Inspection:</span>
              <span class="text-slate-700">${data.last_inspection}</span>
            </div>
          </div>

          <!-- Recent Flags -->
          <div>
            <p class="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Recent Flags</p>
            ${
              data.recent_flags.length === 0
                ? '<p class="text-xs text-green-600 bg-green-50 p-2 rounded-lg">No recent flags on record.</p>'
                : `<div class="space-y-1.5">
                    ${data.recent_flags
                      .map(
                        (f) => `
                      <div class="p-2 rounded-lg bg-red-50 border border-red-100 text-xs flex justify-between items-center">
                        <div>
                          <span class="font-semibold text-red-800">${f.type_label}</span>
                          <p class="text-[11px] text-red-600 truncate max-w-xs">${f.description}</p>
                        </div>
                        <span class="text-[10px] font-bold uppercase text-red-700">${f.status}</span>
                      </div>
                    `
                      )
                      .join("")}
                  </div>`
            }
          </div>

          <!-- Action Buttons -->
          <div class="flex gap-2 pt-2 border-t border-slate-100">
            <a href="/officer/assignments"
               class="flex-1 bg-teal hover:bg-teal/90 text-white text-xs font-semibold py-2.5 rounded-lg text-center transition-colors">
              Schedule Inspection
            </a>
            <button onclick="document.getElementById('institute-quickview-modal').classList.add('hidden')"
                    class="px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold py-2.5 rounded-lg transition-colors">
              Close
            </button>
          </div>
        </div>
      `;
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      content.innerHTML = `
        <div class="text-center py-6 text-red-600 text-xs">
          Failed to load institute details.
        </div>
      `;
    }
  }

  // Initialize
  initMap();

  return {
    reload: loadInstitutes,
    openQuickView: openQuickView,
  };
})();
