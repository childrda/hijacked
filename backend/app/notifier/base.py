"""Notifier interface for email alerts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Notifier(ABC):
    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        """Send email. Raises on failure."""
        ...
