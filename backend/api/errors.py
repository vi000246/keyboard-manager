"""Custom HTTPException subclasses with uniform JSON error bodies.

Error codes follow Module Spec §API Contracts > Error Codes.
"""
from __future__ import annotations

from fastapi import HTTPException


class VialNotFound(HTTPException):
    def __init__(self, path: str):
        super().__init__(
            status_code=503,
            detail={
                "error": "VIAL_NOT_FOUND",
                "message": f"vial file not found at {path}",
            },
        )


class VialParseFailed(HTTPException):
    def __init__(self, reason: str):
        super().__init__(
            status_code=422,
            detail={
                "error": "VIAL_PARSE_ERROR",
                "message": reason,
            },
        )
