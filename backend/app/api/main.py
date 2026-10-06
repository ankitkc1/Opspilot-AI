from fastapi import APIRouter

from app.api.routes import (
    dashboard,
    inventory,
    items,
    login,
    private,
    products,
    sales,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(products.router)
api_router.include_router(sales.router)
api_router.include_router(inventory.router)
api_router.include_router(dashboard.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
