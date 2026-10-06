/**
 * vc_staff.js — Incoming video-call handler for the staff portal.
 *
 * Phase 1: countdown timer for the VC banner if it's present.
 * Phase 6: full SSE-based push + Jitsi iframe integration.
 */

(function () {
  // Countdown for incoming VC banner
  const countdownEl = document.getElementById("vc-countdown");
  if (!countdownEl) return;

  let seconds = parseInt(countdownEl.textContent, 10) || 60;

  const interval = setInterval(() => {
    seconds -= 1;
    countdownEl.textContent = seconds;
    if (seconds <= 0) {
      clearInterval(interval);
      // Auto-mark as timed out in the UI
      const banner = document.getElementById("vc-banner");
      if (banner) {
        banner.classList.remove("border-red-400", "animate-pulse");
        banner.classList.add("border-slate-300", "opacity-60");
        banner.innerHTML = `
          <div class="text-center py-4 text-slate-500">
            <p class="font-semibold">Call missed — deadline passed</p>
            <p class="text-xs mt-1">This will be logged and flagged automatically.</p>
          </div>`;
      }
    }
  }, 1000);
})();
