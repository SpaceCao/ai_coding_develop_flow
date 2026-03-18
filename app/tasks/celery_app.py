"""Celery 应用配置"""

from celery import Celery

from config.settings import settings

celery_app = Celery(
    "ai_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.tasks.coding_tasks.*": {"queue": "coding"},
        "app.tasks.review_tasks.*": {"queue": "review"},
        "app.tasks.deploy_tasks.*": {"queue": "deploy"},
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
