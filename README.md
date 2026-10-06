# Smart Real-Time Monitoring & Inspection Mobile App
### Problem SIH26095 — Department of Social Justice & Empowerment, Government of India

A full-stack, real-time monitoring and field inspection system for NGO-run institutes (shelter homes, hostels, de-addiction centres, and senior citizen homes) funded under Central grant-in-aid schemes.

---

## 🌟 Key Features Built & Integrated

1. **Geographic Risk-Intelligence Map**: Real-time Leaflet map of all facilities color-coded by dynamic RAG risk levels (Red $\ge 70$, Amber $40-69$, Green $< 40$) with category filters and interactive quick-view modals.
2. **Autonomous Conflict-Free Assignment Engine**: Risk-weighted random inspection scheduling ($W_i = \text{Risk} \times 0.6 + \text{Days} \times 0.4$) enforcing 4 strict anti-conflict rules (home district segregation, repeat visit bans, workload caps) with reproducible cryptographic seeds.
3. **Mobile-First Live Camera Evidence Capture**: Live hardware capture viewfinder (`getUserMedia`), 60-second single-use OTP countdowns, GPS geo-fence distance calculation ($200\text{ m}$ threshold), and anti-spoofing liveness verification.
4. **Cryptographic Integrity & Tamperproofing**: In-browser SHA-256 hash generation, server-side HMAC-SHA256 digital signatures, and 64-bit Perceptual Hash (pHash) comparison to block photo reuse.
5. **Multi-Signal Anomaly Engine & Trust Scores**: Statistical attendance flatline detector, geo-fence breach detector, duplicate image detector, and automated trust score calculation ($0-100$).
6. **Live CCTV Wall & Headcount AI Reconciliation**: Camera Gateway streaming live MJPEG surveillance feeds with AI occupant bounding box overlays and automated cross-checking against daily staff attendance ($10\%$ tolerance).
7. **Random Video-Call Spot Checks**: Risk-weighted unannounced video checks with 60-second SLA timers, embedded Jitsi Meet conference rooms, and automated missed-call anomaly escalation.
8. **Human-in-the-Loop Review & Audit Trail**: Officer adjudication workflow (Genuine, Needs Action, Dismissed) with institute staff response submission and append-only cryptographic audit logging.
9. **Printable Inspection Audit Reports**: Government-grade certificate view with 1-click printable PDF generation.
10. **Dynamic Bilingual UI**: Instant in-place English $\leftrightarrow$ हिन्दी language toggle.

---

## 🛠 Tech Stack

- **Backend**: Python 3.10+, Flask 3.x, Flask-SQLAlchemy 3.x, Flask-Login, APScheduler, Pillow, ImageHash, PyOpenSSL.
- **Frontend**: Jinja2 Templates, Tailwind CSS (via CDN), Vanilla JavaScript (ES6+), Lucide Icons.
- **Real-Time Data**: Server-Sent Events (SSE) streaming (`/api/stream`) with auto-reconnecting event bus.
- **Maps & Charts**: Leaflet.js (OpenStreetMap), Chart.js.
- **Video & Surveillance**: In-browser camera (`getUserMedia`), Web Crypto API, Jitsi Meet secure room integration, MJPEG camera gateway.
- **Zero Paid Dependencies**: 100% free, open-source stack with zero API keys required.

---

## 🚀 Quickstart & How to Run

### 1. Installation
```powershell
# Navigate to project directory
cd avishkar

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch the Application

**Standard Run (Localhost)**:
```powershell
python run.py
```

**Mobile Testing Run with HTTPS (Enables Camera & Geolocation on Mobile Phones)**:
```powershell
python run.py --ssl
```
*When running with `--ssl`, open `https://<YOUR-LOCAL-IP>:5000` on your smartphone connected to the same Wi-Fi.*

---

## 🔑 Demo Login Accounts

All accounts share the password: `demo123`

| Role | Email | Name | Default Portal |
|---|---|---|---|
| **Zonal Officer** | `officer@demo.in` | Aditya Kapoor | `/officer/overview` |
| **PMU Inspector** | `inspector1@demo.in` | Rajan Mehta | `/inspector/tasks` |
| **PMU Inspector #2** | `inspector2@demo.in` | Priya Sharma | `/inspector/tasks` |
| **Institute Staff** | `staff01@demo.in` | Kavita Patel | `/staff/attendance` |

*(On the login screen at `http://localhost:5000`, you can also use the **1-Click Instant Demo Login** cards for immediate access).*

---

## 📁 Project Architecture & Folder Structure

```
avishkar/
├── run.py                       # Application entry point (supports --ssl and --port)
├── requirements.txt             # Python dependencies
├── app/
│   ├── __init__.py              # Flask factory & APScheduler setup
│   ├── config.py                # Configurable anomaly weights & thresholds
│   ├── extensions.py            # SQLAlchemy, Flask-Login, SSE event queues
│   ├── models.py                # 8 core data models (User, Institute, Inspection, etc.)
│   ├── seed.py                  # Demo dataset (15 institutes, 5 inspectors, 20 staff, anomalies)
│   ├── services/
│   │   ├── anomaly.py           # Anomaly detectors, pHash, GPS, attendance analysis
│   │   ├── assignment.py        # Risk-weighted conflict-free assignment engine
│   │   ├── cctv.py              # CCTV camera gateway & headcount reconciliation
│   │   ├── event_bus.py         # Real-time SSE event dispatcher
│   │   ├── report.py            # Inspection PDF report compiler
│   │   ├── trust_score.py       # Inspection compliance trust score calculator
│   │   └── vc.py                # Random video call SLA & Jitsi manager
│   ├── blueprints/
│   │   ├── api/routes.py        # REST API & SSE streaming endpoints
│   │   ├── auth/routes.py       # Authentication & 1-click quick login
│   │   ├── inspector/routes.py  # Mobile inspector tasks, capture, & history
│   │   ├── officer/routes.py    # Desktop dashboard, map, CCTV, flags, audit log
│   │   └── staff/routes.py      # Staff attendance, incoming VC, & flag clarifications
│   ├── static/
│   │   ├── css/custom.css       # Design tokens & print stylesheet
│   │   ├── js/                  # i18n.js, map.js, sse.js, capture.js, vc_staff.js
│   │   └── uploads/             # Field evidence photo storage
│   └── templates/
│       ├── base_officer.html    # Desktop sidebar shell
│       ├── base_inspector.html  # Mobile bottom-nav shell
│       ├── base_staff.html      # Staff portal navigation shell
│       ├── auth/login.html      # 1-Click login portal
│       ├── officer/             # overview, map, cctv_wall, inspections, flags, assignments, audit_log, report
│       ├── inspector/           # tasks, capture, history, profile
│       └── staff/               # attendance, vc_incoming, flags, results
├── README.md                    # System documentation & run guide
├── NOTES.md                     # Architectural decisions & simulation disclosures
└── DEMO_SCRIPT.md               # 3-Minute pitch & live demonstration script
```
