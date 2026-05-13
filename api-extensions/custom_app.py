"""
Alternative pattern: import orchid-api's ``app`` and attach custom routers.

Use this when you don't want to package your project as an installable
distribution with entry points.  Just run::

    ORCHID_CONFIG=examples/api-extensions/orchid.yml \\
        uvicorn examples.api-extensions.custom_app:app --port 8000

The built-in orchid-api endpoints remain available, and your custom
``/admin/*`` endpoints are added on top.
"""

from __future__ import annotations

from orchid_api.main import app

# Attach our custom routers
from .routers import admin

app.include_router(admin.router)
