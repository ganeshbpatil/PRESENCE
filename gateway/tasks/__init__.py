"""
gateway/tasks/__init__.py

Celery's autodiscover_tasks(["gateway"]) (see celery_app.py) imports this
package, but does not recurse into submodules on its own — each task
module must be imported here so its @app.task decorator actually registers
it.
"""
from gateway.tasks import attribution, sync  # noqa: F401
