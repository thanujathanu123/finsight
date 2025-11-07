from kombu.utils.url import safequote
from urllib.parse import quote

broker_url = f"sqla+sqlite:///celery.sqlite"
result_backend = 'django-db'
cache_backend = 'django-cache'
accept_content = ['application/json']
task_serializer = 'json'
result_serializer = 'json'