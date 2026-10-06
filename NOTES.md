# Architectural Notes & Design Decisions
### SIH26095 — Smart Real-Time Monitoring & Inspection Mobile App

---

## 1. Transparent Disclosure of Simulated Components

In accordance with competition rules, all simulated layers are explicitly disclosed and tagged:

| Component | Implementation Detail | Disclosure Tag |
|---|---|---|
| **CCTV Surveillance Feeds** | Camera Gateway generates live MJPEG surveillance streams with dynamic HUD overlays (REC, timestamp, occupant bounding boxes) using Pillow. Plays directly in HTML5. Ready for RTSP/HLS drop-in. | `[SIMULATED]` |
| **Occupancy Count** | Deterministic occupancy model based on capacity & scripted anomalies. Can be replaced with YOLOv8/OpenCV without modifying business logic. | `[SIMULATED]` |
| **Subject Liveness Step** | Browser-side blink/movement verification with graceful offline fallback. Does **not** store sensitive biometric facial embeddings, complying with government privacy guidelines. | `[ANTI-SPOOFING]` |
| **Video Conference** | Uses free public Jitsi Meet infrastructure (`https://meet.jit.si/<room_name>`) embedded in secure iframes. Requires zero paid licenses or API keys. | `[ZERO-COST PROTOCOL]` |

---

## 2. Core Mathematical Formulations

### A. Institute Risk Score Calculation
Institutes are scored on a scale of $0.0$ (Low Risk) to $100.0$ (Critical Risk):
$$\text{Risk Score} = \text{Base Risk} + \sum \Delta \text{Flag Penalties} - (\text{Days Elapsed} \times \text{Decay Rate})$$
- High Severity Flag (e.g. GPS Mismatch, Duplicate Photo, Headcount Discrepancy): $+15.0$
- Medium Severity Flag (e.g. Missed Video Call, Statistical Flatline): $+8.0$
- Officer Dismissal (False Positive cleared): $-12.0$

### B. Risk-Weighted Inspection Priority Formula
$$\text{Priority Weight } W_i = (\text{Risk Score}_i \times 0.6) + (\min(100, \text{Days Since Last Audit}_i \times 2) \times 0.4)$$
- Ensures high-risk facilities and stale/uninspected institutes are scheduled autonomously.

### C. Inspection Compliance Trust Score
Computed upon audit completion starting at $100.0$:
$$\text{Trust Score} = 100.0 - \sum \text{Anomaly Signal Deductions}$$
- `duplicate_photo`: $-25$
- `gps_mismatch`: $-20$
- `cctv_headcount_mismatch`: $-15$
- `liveness_failed`: $-15$
- `missed_vc`: $-10$
- `unusual_attendance`: $-10$

### D. CCTV Headcount Reconciliation Discrepancy
$$\text{Discrepancy \%} = \frac{|\text{Reported Occupants} - \text{CCTV Detected Occupants}|}{\max(1, \text{Reported Occupants})} \times 100$$
- If $\text{Discrepancy \%} > 10.0\%$, a high-severity `cctv_headcount_mismatch` flag is raised immediately.

---

## 3. Cryptographic Tamper-Proofing Pipeline

1. **One-Time Token (OTP)**: A 6-digit random token is fetched by the mobile inspector prior to capture, valid for exactly $60\text{ seconds}$.
2. **In-Browser SHA-256**: The uncompressed JPEG blob is hashed inside the browser using `crypto.subtle.digest("SHA-256")`.
3. **Server HMAC-SHA256 Signature**:
   $$\text{HMAC Signature} = \text{HMAC}_{\text{SHA256}}(\text{SECRET\_KEY}, \text{SHA256} \mathbin{\Vert} \text{OTP} \mathbin{\Vert} \text{Timestamp}_{\text{ISO}})$$
4. **Perceptual Image Hashing (pHash)**: 64-bit DCT-based image hash. Bitwise Hamming distance $\le 6$ between two different inspections flags photo reuse automatically.

---

## 4. Key Architectural Decisions

1. **Server-Sent Events (SSE) vs WebSockets**:
   - SSE operates over standard HTTP, requiring zero special proxies or firewall configurations.
   - Built-in reconnection and native browser support via `EventSource`.
2. **In-Process APScheduler**:
   - Zero Redis / Celery dependencies, keeping the entire hackathon prototype self-contained and run-ready with a single command.
3. **Government-Grade Design Tokens**:
   - Navy (`#1E3A5F`), Teal (`#0D9488`), and Saffron (`#F59E0B`). High-contrast, compliant with standard accessible government UI specifications.
