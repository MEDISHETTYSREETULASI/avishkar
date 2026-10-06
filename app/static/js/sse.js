/**
 * sse.js — Real-Time Server-Sent Events (SSE) Engine
 *
 * Connects to /api/stream and handles instant push broadcasts:
 * - New flag raises (GPS mismatch, duplicate photo, headcount discrepancy)
 * - Missed random video calls
 * - Real-time KPI counter updates
 * - Live activity feed item insertion with animations
 * - Toast alert banners
 */

(function () {
  let eventSource = null;
  let reconnectAttempts = 0;
  const maxReconnectDelay = 15000;

  function initSSE() {
    if (eventSource) {
      eventSource.close();
    }

    eventSource = new EventSource("/api/stream");

    eventSource.addEventListener("heartbeat", (e) => {
      reconnectAttempts = 0;
      updateConnectionStatus(true);
    });

    // ── 1. Flag Raised Event ─────────────────────────────────────────────
    eventSource.addEventListener("flag_raised", (e) => {
      try {
        const data = JSON.parse(e.data);
        console.log("[SSE] Flag raised:", data);

        // Prepend to activity feed
        addFeedItem({
          severity: data.severity || "high",
          title: data.flag_type_label || "Anomaly Flag",
          subtitle: data.institute_name,
          time: data.time || new Date().toLocaleTimeString(),
          description: data.description,
        });

        // Bump open flags KPI
        bumpKPI("open_flags");

        // Show Toast Notification
        showToast(
          `⚠️ Anomaly Detected: ${data.flag_type_label}`,
          `${data.institute_name} — ${data.description || ""}`,
          data.severity === "high" ? "red" : "amber"
        );

        // If map is open, refresh map markers
        if (window.InstituteMap && typeof window.InstituteMap.reload === "function") {
          window.InstituteMap.reload();
        }
      } catch (err) {
        console.error("[SSE] Error parsing flag_raised:", err);
      }
    });

    // ── 2. VC Missed Event ───────────────────────────────────────────────
    eventSource.addEventListener("vc_missed", (e) => {
      try {
        const data = JSON.parse(e.data);
        console.log("[SSE] VC Missed:", data);

        addFeedItem({
          severity: "high",
          title: "Missed Video Call",
          subtitle: `${data.institute_name} (${data.staff_name || "Staff"})`,
          time: data.time || new Date().toLocaleTimeString(),
          description: "Staff did not respond within 60s deadline.",
        });

        bumpKPI("missed_calls");
        bumpKPI("open_flags");

        showToast(
          "📞 Missed Video Call Alert",
          `${data.institute_name}: Staff did not answer within 60 seconds.`,
          "red"
        );
      } catch (err) {
        console.error("[SSE] Error parsing vc_missed:", err);
      }
    });

    // ── 3. Headcount Discrepancy Event ───────────────────────────────────
    eventSource.addEventListener("headcount_mismatch", (e) => {
      try {
        const data = JSON.parse(e.data);
        console.log("[SSE] Headcount mismatch:", data);

        addFeedItem({
          severity: "high",
          title: "CCTV Headcount Mismatch",
          subtitle: data.institute_name,
          time: data.time || new Date().toLocaleTimeString(),
          description: `CCTV detected ${data.cctv_count} vs ${data.reported_count} reported (${data.diff_pct}% diff).`,
        });

        bumpKPI("open_flags");

        showToast(
          "📹 CCTV Headcount Discrepancy",
          `${data.institute_name}: CCTV found ${data.cctv_count} vs ${data.reported_count} reported.`,
          "red"
        );
      } catch (err) {
        console.error("[SSE] Error parsing headcount_mismatch:", err);
      }
    });

    // ── 4. Inspection Assigned Event ─────────────────────────────────────
    eventSource.addEventListener("inspection_assigned", (e) => {
      try {
        const data = JSON.parse(e.data);
        addFeedItem({
          severity: "low",
          title: "Inspection Assigned",
          subtitle: `${data.institute_name} → ${data.inspector_name}`,
          time: data.time || new Date().toLocaleTimeString(),
          description: "Risk-weighted inspection dispatched.",
        });

        bumpKPI("inspections_this_week");
      } catch (err) {
        console.error("[SSE] Error parsing inspection_assigned:", err);
      }
    });

    // ── Connection lifecycle ─────────────────────────────────────────────
    eventSource.onerror = () => {
      updateConnectionStatus(false);
      eventSource.close();
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay);
      reconnectAttempts++;
      console.warn(`[SSE] Disconnected. Reconnecting in ${delay / 1000}s...`);
      setTimeout(initSSE, delay);
    };
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  function updateConnectionStatus(isLive) {
    const indicator = document.getElementById("sse-live-indicator");
    if (indicator) {
      if (isLive) {
        indicator.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          <span class="text-green-600 font-medium text-xs">Live Stream Active</span>
        `;
      } else {
        indicator.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
          <span class="text-amber-600 font-medium text-xs">Connecting...</span>
        `;
      }
    }
  }

  function addFeedItem(item) {
    const feed = document.getElementById("activity-feed");
    if (!feed) return;

    const colors = {
      high: { bg: "bg-red-50", border: "border-red-100", icon: "alert-circle", iconColor: "text-red-500" },
      medium: { bg: "bg-amber-50", border: "border-amber-100", icon: "alert-triangle", iconColor: "text-amber-500" },
      low: { bg: "bg-teal-50", border: "border-teal-100", icon: "info", iconColor: "text-teal" },
    };

    const c = colors[item.severity] || colors.medium;

    const el = document.createElement("div");
    el.className = `flex items-start gap-3 p-3 rounded-xl border ${c.bg} ${c.border} transition-all duration-300 transform -translate-y-2 opacity-0 shadow-sm`;
    el.innerHTML = `
      <div class="w-7 h-7 rounded-lg bg-white/80 flex items-center justify-center flex-shrink-0 shadow-xs mt-0.5">
        <i data-lucide="${c.icon}" class="w-4 h-4 ${c.iconColor}"></i>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between gap-1">
          <p class="text-xs font-bold text-slate-800">${item.title}</p>
          <span class="text-[10px] text-slate-400 font-mono">${item.time}</span>
        </div>
        <p class="text-xs text-slate-600 truncate font-medium">${item.subtitle}</p>
        ${item.description ? `<p class="text-[11px] text-slate-500 mt-0.5">${item.description}</p>` : ""}
      </div>
    `;

    // Remove empty placeholder
    const emptyState = feed.querySelector("[data-empty-state]");
    if (emptyState) emptyState.remove();

    feed.prepend(el);
    if (window.lucide) lucide.createIcons();

    // Trigger animate-in
    requestAnimationFrame(() => {
      el.classList.remove("-translate-y-2", "opacity-0");
    });

    // Keep max 25 items in DOM
    while (feed.children.length > 25) {
      feed.removeChild(feed.lastChild);
    }
  }

  function bumpKPI(kpiKey) {
    const el = document.getElementById(`kpi-${kpiKey}`);
    if (!el) return;

    const current = parseInt(el.textContent.replace(/\D/g, ""), 10) || 0;
    el.textContent = current + 1;

    // Visual pulse animation
    el.classList.add("text-saffron", "scale-110");
    setTimeout(() => {
      el.classList.remove("text-saffron", "scale-110");
    }, 1000);
  }

  function showToast(title, message, color = "red") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-sm pointer-events-none";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const bg = color === "red" ? "bg-red-900/90 border-red-500" : "bg-amber-900/90 border-amber-500";

    toast.className = `pointer-events-auto p-4 rounded-xl text-white shadow-2xl border backdrop-blur-md transition-all duration-300 transform translate-x-10 opacity-0 ${bg}`;
    toast.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="w-2 h-2 rounded-full ${color === "red" ? "bg-red-400" : "bg-amber-400"} animate-ping mt-1.5 flex-shrink-0"></div>
        <div class="flex-1">
          <p class="text-xs font-bold">${title}</p>
          <p class="text-xs text-slate-200 mt-0.5">${message}</p>
        </div>
        <button onclick="this.parentElement.parentElement.remove()" class="text-slate-400 hover:text-white text-xs">✕</button>
      </div>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.remove("translate-x-10", "opacity-0");
    });

    setTimeout(() => {
      toast.classList.add("translate-x-10", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 6000);
  }

  // Auto-start SSE on page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSSE);
  } else {
    initSSE();
  }
})();
