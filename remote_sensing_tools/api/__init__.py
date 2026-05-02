"""API package exports.

Imports are resolved lazily so helper modules can be tested without requiring
the optional web stack to be installed in the current interpreter.
"""

__all__ = ["create_app", "setup_routes"]


def __getattr__(name):
    if name == "create_app":
        from .app import create_app

        return create_app
    if name == "setup_routes":
        from .routes import setup_routes

        return setup_routes
    raise AttributeError(name)
