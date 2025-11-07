# 🧮 FinSight: Intelligent Financial Risk Detection and Review Platform

## 🚀 Overview
**FinSight** is a Django-based intelligent financial risk management platform that automates **ledger ingestion, risk scoring, and anomaly detection** using machine learning.  
It provides **role-based dashboards** and workflows for **Admins**, **Auditors**, **Finance Officers**, and **Reviewers** to collaboratively monitor financial ledgers, detect suspicious transactions, and maintain transparency across all reviews.

---

## 🧭 System Workflow

### 1️⃣ Ledger Upload
- Authorized users (**Admin**, **Auditor**, **Finance Officer**) upload `.csv` or `.xlsx` files.
- Each ledger includes:
  - `Date`
  - `Description`
  - `Amount`
- Uploaded ledgers are stored as `LedgerUpload` records and processed automatically.

### 2️⃣ Risk Processing Pipeline
**Core function:** `core.risk_engine.processor.process_ledger_file`

#### Workflow:
1. Validates and parses ledger data.
2. Initializes or retrieves an existing **RiskProfile**.
3. Uses the **RiskAnalysisEngine** to analyze transactions.
4. Extracts features:
   - Amount, log(amount)
   - Hour/day dummies
   - Rolling frequency counts (1h, 3h, 6h, 12h, 24h)
   - Category encodings (if any)
5. Applies **StandardScaler** normalization.
6. Detects anomalies using **IsolationForest** (default contamination = 10%).
7. Combines anomaly score with rule-based metrics to create a unified **risk score**.
8. Creates **Alert** entries for transactions where `risk_score > 70`.

---

## ⚠️ Alerts & Review

### 🔁 Alert Assignment
- Alerts are auto-assigned evenly to **active reviewers**.
- Managed by `assign_alerts_to_reviewers()`.

### 🧾 Review Workflow
- Reviewers access the **Reviewer Dashboard**:
  - Review high-risk transactions.
  - Add comments and notes.
  - Update status (Pending → In Review → Resolved).
  - Print or export reports.
- Metrics include:
  - Current risk level
  - Reviewed vs. pending alerts
  - Average resolution time

---

## 🔐 Role-Based Access Control (RBAC)

### Roles and Permissions

| **Role / Group** | **Primary Capabilities** | **Purpose** |
|------------------|--------------------------|--------------|
| **Admin** | Full dashboards, user management, ledger uploads, Django admin access | System oversight |
| **Auditor** | Upload ledgers, analyze risk, view high-risk transactions | Investigate anomalies |
| **FinanceOfficer** | Upload ledgers, view summaries, KPIs | Monitor financial performance |
| **Reviewer** | Review alerts, update status, add notes | Resolve flagged transactions |
| **Guest** | Read-only demo dashboard | Limited demo access |
| **Superuser** | All privileges (includes Admin + Django admin) | Developer / Ops |

RBAC enforcement:
- Uses Django **Group membership**.
- Default roles created automatically by:
  ```python
  core.signals.create_roles (post_migrate)
