"""V1 API router aggregator."""

from fastapi import APIRouter

from callscreen.api.v1.auth import router as auth_router
from callscreen.api.v1.calls import router as calls_router
from callscreen.api.v1.community import router as community_router
from callscreen.api.v1.contacts import router as contacts_router
from callscreen.api.v1.health import health_router
from callscreen.api.v1.intel import router as intel_router
from callscreen.api.v1.messages import router as messages_router
from callscreen.api.v1.personas import router as personas_router
from callscreen.api.v1.settings import router as settings_router
from callscreen.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(calls_router, prefix="/calls", tags=["calls"])
api_router.include_router(community_router, prefix="/community", tags=["community"])
api_router.include_router(contacts_router, prefix="/contacts", tags=["contacts"])
api_router.include_router(intel_router, prefix="/intel", tags=["intel"])
api_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_router.include_router(personas_router, prefix="/personas", tags=["personas"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(health_router, tags=["health"])
