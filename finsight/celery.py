import os
from celery import Celery
from django.conf import settings

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finsight.settings')

# Create Celery instance
app = Celery('finsight')

# Load settings from Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure periodic tasks
app.conf.beat_schedule = {
    'process-pending-ledgers': {
        'task': 'core.tasks.process_ledger_upload',
        'schedule': 300.0,  # every 5 minutes
    },
    'update-risk-profiles': {
        'task': 'core.tasks.update_all_risk_profiles',
        'schedule': 3600.0,  # every hour
    },
    'cleanup-old-alerts': {
        'task': 'core.tasks.cleanup_old_alerts',
        'schedule': 86400.0,  # daily
        'kwargs': {'days': 30}
    },
}

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)