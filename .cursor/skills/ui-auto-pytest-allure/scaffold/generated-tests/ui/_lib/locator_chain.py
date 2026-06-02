"""Locator list helpers: primary + fallbacks."""

from __future__ import annotations

from typing import Any


def _settings_entry_click_fallback(primary: dict[str, Any]) -> dict[str, Any] | None:
    """Home settings label (tvSettings) is not clickable; its parent btnSettings is."""
    resource_id = str(primary.get("id") or "")
    if not resource_id.endswith(":id/tvSettings"):
        return None
    package = resource_id.rsplit(":", 1)[0]
    return {"id": f"{package}:id/btnSettings"}


def step_locators(step: dict[str, Any]) -> list[dict[str, Any]]:
    """Ordered locators: primary `locator` then `locators_fallback`."""
    locators: list[dict[str, Any]] = []
    primary = step.get("locator")
    if isinstance(primary, dict) and primary:
        locators.append(primary)
        fallback = _settings_entry_click_fallback(primary)
        if fallback and fallback not in locators:
            locators.append(fallback)
    for item in step.get("locators_fallback") or []:
        if isinstance(item, dict) and item:
            locators.append(item)
    return locators


def field_locators(step: dict[str, Any], field: str) -> list[dict[str, Any]]:
    """Locators for expect_visible / expect_not_visible with optional *_fallback."""
    locators: list[dict[str, Any]] = []
    primary = step.get(field)
    if isinstance(primary, dict) and primary:
        locators.append(primary)
    for item in step.get(f"{field}_locators_fallback") or []:
        if isinstance(item, dict) and item and item not in locators:
            locators.append(item)
    return locators
