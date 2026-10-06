# 3-Minute Live Demonstration Pitch Script
### Smart India Hackathon — Problem SIH26095 (Dept. of Social Justice & Empowerment)

---

## ⏱ Time Breakdown & Flow Overview

| Minute | Section | Key Focus |
|---|---|---|
| **0:00 – 0:30** | The Problem & Real-Time Overview | Why grant-in-aid monitoring fails & the Geo-Risk Map |
| **0:30 – 1:15** | CCTV Wall & AI Headcount Reconciliation | Automated mismatch detection & live camera gateway |
| **1:15 – 1:45** | Autonomous Conflict-Free Assignment | Risk-weighted algorithm, 4 anti-conflict rules, & random seed |
| **1:45 – 2:20** | Mobile Inspector Field Evidence Capture | Live camera only, 60s OTP, GPS 200m check, SHA-256 & HMAC |
| **2:20 – 2:45** | Random Video-Call Spot Check | 60-second SLA deadline & embedded Jitsi conference |
| **2:45 – 3:00** | Human-in-the-Loop Review & Audit Report | Officer adjudication, trust score, & printable PDF report |

---

## 🎤 Step-by-Step Demonstration Walkthrough

### 0:00 – 0:30 | Introduction & Officer Dashboard
1. **Action**: Open `http://localhost:5000`, click **"Officer"** (1-Click Instant Login).
2. **Talking Point**:
   > *"Respected Jury, the Department of Social Justice funds thousands of NGO-run shelter homes, hostels, and senior citizen centres. Traditional periodic monitoring suffers from ghost residents, photo reuse, and inspector collusion. We present a unified, real-time monitoring and inspection platform."*
3. **Action**: Point to the **KPI Cards**, **Risk Breakdown**, and **Interactive Geo-Risk Map**.
   > *"Here on the Officer Overview, all 15 NGO facilities are scored dynamically from 0 to 100. Red markers indicate high-risk facilities requiring urgent oversight."*

---

### 0:30 – 1:15 | CCTV Wall & AI Headcount Reconciliation
1. **Action**: In the left sidebar, click **CCTV Wall** (`/officer/cctv`).
2. **Talking Point**:
   > *"Our Camera Gateway integrates live surveillance feeds across all centres. On Tile #1—Naya Savera Shelter Home—the staff reported 48 occupants, but our automated camera scan detected only 29 residents—a 39.6% discrepancy."*
3. **Action**: Click **"Run Real-Time Headcount Scan"** on Tile #1.
   > *"When scanned, the system automatically detects this mismatch, escalates the institute's risk score, and issues a high-severity anomaly lead across the national event bus in real time."*

---

### 1:15 – 1:45 | Autonomous Conflict-Free Assignment Engine
1. **Action**: Click **Assignments** (`/officer/assignments`).
2. **Talking Point**:
   > *"Manual inspector scheduling often leads to bias and local collusion. Our Autonomous Assignment Engine calculates priority based on real-time risk scores and audit staleness."*
3. **Action**: Click **"Auto-Assign Next Priority"**.
4. **Talking Point**:
   > *"Notice what just happened: The system selected the highest-priority institute, filtered out all inspectors residing in that home district, banned repeat visits, balanced the weekly workload, and generated a cryptographically verifiable random seed logged to the immutable audit trail."*

---

### 1:45 – 2:20 | Mobile Field Evidence Capture (Inspector Portal)
1. **Action**: Open a new tab, go to `http://localhost:5000`, and click **"Inspector"** (`inspector1@demo.in`).
2. **Talking Point**:
   > *"Switching to the PMU Inspector's smartphone view: The mobile-first interface displays assigned tasks with one clear action per screen."*
3. **Action**: Tap **"Start Live Inspection"** on an assigned audit $\rightarrow$ Navigate to **Capture**.
4. **Talking Point**:
   > *"Field integrity is strictly enforced:*
   > *1. **Live Camera Only**: File uploads from the phone gallery are completely disabled.*
   > *2. **60-Second Server OTP**: A single-use token expires in 60 seconds.*
   > *3. **GPS Geo-Fence**: Computes real-time distance to registered coordinates (flags if $> 200\text{ m}$).*
   > *4. **Liveness Step**: Verifies subject presence.*
   > *5. **Tamperproofing**: The browser computes the SHA-256 hash, and the server signs it with an HMAC-SHA256 digital signature while checking perceptual hash to prevent duplicate photo reuse."*
5. **Action**: Tap **"Capture & Cryptographically Sign Evidence"**, then click **"Finalize & Compute Trust Score"**.

---

### 2:20 – 2:45 | Random Video-Call Spot Check (Staff Portal)
1. **Action**: Switch to the **Officer Tab** $\rightarrow$ Under **Live Simulation**, trigger **"Simulate Missed Random VC Check"** (or initiate a live call).
2. **Action**: Switch to the **Staff Tab** (`staff01@demo.in`) $\rightarrow$ Click **Video Call** (`/staff/vc`).
3. **Talking Point**:
   > *"Officers can dispatch unannounced spot checks at any moment. The staff portal immediately displays an incoming call banner with an active 60-second countdown. If accepted, an end-to-end encrypted Jitsi Meet room opens right in the browser with zero external software needed. If unanswered, a missed-call flag is raised automatically."*

---

### 2:45 – 3:00 | Human Review & Official Audit Report
1. **Action**: Back in the Officer portal, click **Inspections** (`/officer/inspections`) $\rightarrow$ Click **"Report"** on any completed audit.
2. **Talking Point**:
   > *"AI never takes final punitive action alone—it generates inspection leads. Officers review evidence context and record official determinations in the Audit Log.*
   > *Finally, officers can generate and print this official Government-Grade Inspection Report with complete cryptographic hash proofs, GPS coordinates, and inspector sign-off with a single click."*
3. **Closing**:
   > *"Built on 100% free, open-source technology with zero paid APIs. Thank you!"*
