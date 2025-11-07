# FinSight Repository Overview

## Technology Stack
- **Framework**: Django (Python)
- **Frontend**: Bootstrap 5, Chart.js, DataTables
- **Background Tasks**: Celery (configured in `finsight/celery.py`)
- **Database**: SQLite (default `db.sqlite3` provided)

## App Structure
- **finsight/**: Project settings, URLs, WSGI, Celery configuration.
- **core/**: Main Django app containing views, models, forms, tasks, alerts, and ML/risk processing code.
  - **templatetags/**: Custom template filters, e.g., `group_filters.py` for RBAC checks.
  - **risk_engine/**: Ledger processing logic and risk analysis utilities.
  - **tests/**: Unit tests covering RBAC, alerts, and risk analysis.
- **templates/core/**: HTML templates for dashboards, auth, and misc pages.
- **static/core/**: Source JS/CSS assets used by templates.
- **staticfiles/**: Collected static assets (e.g., via `collectstatic`).
- **media/**: Uploaded ledger samples (`media/ledgers/`).

## Key URLs & Views
- **Root (`/`)**: Currently mapped to `core.views.guest_dashboard` (demo dashboard for guests).
- **Dashboards**: Admin, auditor, finance, and reviewer dashboards require specific groups.
- **Upload**: `upload_ledger` view with group-based restrictions.
- **Authentication**: Django auth views (login/logout, password reset/change).

## Development Notes
- Uses custom group-based filters (`user|has_group`) widely in templates.
- Risk processing leverages `core/risk_engine/processor.py` and related modules.
- Celery tasks defined in `core/tasks.py` for async processing (requires broker configuration outside repo).