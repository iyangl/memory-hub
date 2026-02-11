from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class BusinessError(Exception):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            payload["details"] = self.details
        return payload
