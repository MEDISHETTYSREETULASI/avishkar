/**
 * i18n.js — English / Hindi language toggle for Smart Monitoring App (SIH26095)
 *
 * Usage:
 *   Add  data-i18n="key"  to any element.
 *   Call toggleLang() from a button.
 *   Language preference is stored in localStorage.
 */

const I18N = {
  en: {
    // App
    app_name:      "Smart Monitor",
    app_ministry:  "Ministry of Social Justice",
    app_subtitle:  "Grant-in-Aid Institute Monitoring",

    // Officer nav
    nav_overview:    "Overview",
    nav_map:         "Map",
    nav_cctv:        "CCTV Wall",
    nav_inspections: "Inspections",
    nav_flags:       "Flags",
    nav_assignments: "Assignments",
    nav_audit:       "Audit Log",

    // Inspector nav
    nav_tasks:   "Tasks",
    nav_capture: "Capture",
    nav_history: "History",
    nav_profile: "Profile",

    // Staff nav
    nav_attendance: "Attendance",
    nav_vc:         "Video Call",
    nav_results:    "Results",

    // Roles
    role_officer:   "Officer",
    role_inspector: "Inspector (PMU)",
    role_staff:     "Institute Staff",

    // Buttons
    btn_login:  "Sign In",
    btn_logout: "Sign Out",
    btn_assign: "Assign Inspection",
    btn_capture:"Capture Evidence",
    btn_submit: "Submit",
    btn_demo:   "Run Demo Scenario",

    // Statuses
    status_open:         "Open",
    status_genuine:      "Genuine",
    status_needs_action: "Needs Action",
    status_dismissed:    "Dismissed",
    status_completed:    "Completed",
    status_assigned:     "Assigned",
    status_in_progress:  "In Progress",

    // Risk
    rag_high:   "High Risk",
    rag_medium: "Medium Risk",
    rag_low:    "Low Risk",

    // Misc
    live_feed:   "Live Activity Feed",
    no_tasks:    "No tasks assigned",
    no_flags:    "No flags raised",
    loading:     "Loading…",
  },

  hi: {
    // App
    app_name:      "स्मार्ट मॉनिटर",
    app_ministry:  "सामाजिक न्याय मंत्रालय",
    app_subtitle:  "अनुदान संस्थान निगरानी",

    // Officer nav
    nav_overview:    "अवलोकन",
    nav_map:         "मानचित्र",
    nav_cctv:        "सीसीटीवी वॉल",
    nav_inspections: "निरीक्षण",
    nav_flags:       "चेतावनियाँ",
    nav_assignments: "असाइनमेंट",
    nav_audit:       "ऑडिट लॉग",

    // Inspector nav
    nav_tasks:   "कार्य",
    nav_capture: "कैप्चर",
    nav_history: "इतिहास",
    nav_profile: "प्रोफ़ाइल",

    // Staff nav
    nav_attendance: "उपस्थिति",
    nav_vc:         "वीडियो कॉल",
    nav_results:    "परिणाम",

    // Roles
    role_officer:   "अधिकारी",
    role_inspector: "निरीक्षक (पीएमयू)",
    role_staff:     "संस्था कर्मचारी",

    // Buttons
    btn_login:  "लॉगिन करें",
    btn_logout: "लॉगआउट",
    btn_assign: "निरीक्षण असाइन करें",
    btn_capture:"साक्ष्य कैप्चर करें",
    btn_submit: "सबमिट करें",
    btn_demo:   "डेमो परिदृश्य चलाएं",

    // Statuses
    status_open:         "खुला",
    status_genuine:      "वास्तविक",
    status_needs_action: "कार्रवाई आवश्यक",
    status_dismissed:    "खारिज",
    status_completed:    "पूर्ण",
    status_assigned:     "असाइन किया",
    status_in_progress:  "प्रगति में",

    // Risk
    rag_high:   "उच्च जोखिम",
    rag_medium: "मध्यम जोखिम",
    rag_low:    "निम्न जोखिम",

    // Misc
    live_feed:   "लाइव गतिविधि फ़ीड",
    no_tasks:    "कोई कार्य असाइन नहीं",
    no_flags:    "कोई चेतावनी नहीं",
    loading:     "लोड हो रहा है…",
  },
};

// ── State ────────────────────────────────────────────────────────────
let currentLang = localStorage.getItem("lang") || "en";

// ── Apply translations ────────────────────────────────────────────────
function applyLang(lang) {
  const strings = I18N[lang] || I18N.en;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (strings[key] !== undefined) {
      el.textContent = strings[key];
    }
  });
  // Update html lang attribute
  document.documentElement.setAttribute("lang", lang === "hi" ? "hi" : "en");
  // Update toggle button label
  const label = document.getElementById("lang-label");
  if (label) label.textContent = lang === "hi" ? "English" : "हिन्दी";
  currentLang = lang;
  localStorage.setItem("lang", lang);
}

function toggleLang() {
  applyLang(currentLang === "en" ? "hi" : "en");
}

// Apply on page load
document.addEventListener("DOMContentLoaded", () => applyLang(currentLang));
