"""Collect all bot routers into a single router."""

from . import admin, common, context, keys, models, chat
from .common import router

__all__ = ["router"]
