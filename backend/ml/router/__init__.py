"""Onboarding router (docs/onboarding_router.md).

    from router import route
    result = route(survey, user_pseudo_id)   # score, benchmarks, mastery, path, challenges, goal, events
"""
from .router import ROUTER_VERSION, route, tree

__all__ = ["ROUTER_VERSION", "route", "tree"]
