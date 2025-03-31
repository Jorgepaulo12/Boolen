from .auth import auth_router
from .courses import course_router
from .wallet import wallet_router
from .admin import admin_router

__all__ = ['auth_router', 'course_router', 'wallet_router', 'admin_router'] 