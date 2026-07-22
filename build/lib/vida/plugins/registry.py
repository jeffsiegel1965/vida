"""Plugin registry — discover and look up Vida plugins."""

from __future__ import annotations

from typing import Any, Optional

from .base import VidaPlugin


class PluginRegistry:
    """In-process registry of Vida plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, VidaPlugin] = {}

    def register(self, plugin: VidaPlugin) -> None:
        name = getattr(plugin, "name", None)
        if not name or not isinstance(name, str):
            raise ValueError("plugin must have a non-empty string name")
        if name in self._plugins:
            raise ValueError(f"plugin already registered: {name}")
        # Lightweight structural check
        if not hasattr(plugin, "status") or not hasattr(plugin, "describe"):
            raise TypeError("plugin must implement describe() and status()")
        if not hasattr(plugin, "chain") or not hasattr(plugin, "capabilities"):
            raise TypeError("plugin must define chain and capabilities")
        self._plugins[name] = plugin

    def get(self, name: str) -> Optional[VidaPlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in sorted(self._plugins):
            p = self._plugins[name]
            try:
                meta = p.describe()
            except Exception as e:  # pragma: no cover — defensive
                meta = {"error": str(e)}
            out.append(
                {
                    "name": name,
                    "chain": getattr(p, "chain", ""),
                    "capabilities": list(getattr(p, "capabilities", [])),
                    "describe": meta,
                }
            )
        return out

    def names(self) -> list[str]:
        return sorted(self._plugins.keys())

    def clear(self) -> None:
        """Test helper."""
        self._plugins.clear()


_DEFAULT: Optional[PluginRegistry] = None


def get_default_registry() -> PluginRegistry:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = PluginRegistry()
    return _DEFAULT
