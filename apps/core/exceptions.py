"""
Global DRF exception handler.

Normalises ALL error responses into the format:
    {
        "success": false,
        "error": {
            "code": "PERMISSION_DENIED",
            "message": "..."
        }
    }
"""
import logging

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context) -> Response:
    """Wrap DRF exceptions into a consistent JSON envelope."""
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception (500)
        logger.exception("Unhandled exception: %s", exc)
        return Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Map common exceptions to semantic codes
    error_code = _resolve_error_code(exc, response.status_code)

    # Flatten DRF detail messages
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
    elif isinstance(detail, list):
        message = "; ".join(str(item) for item in detail)
    elif isinstance(detail, dict):
        parts = []
        for field, errors in detail.items():
            if isinstance(errors, list):
                parts.append(f"{field}: {'; '.join(str(e) for e in errors)}")
            else:
                parts.append(f"{field}: {errors}")
        message = " | ".join(parts)
    else:
        message = str(detail)

    response.data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        },
    }
    return response


def _resolve_error_code(exc, status_code: int) -> str:
    """Map exception type/status to a semantic string code."""
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return "AUTHENTICATION_REQUIRED"
    if isinstance(exc, Http404):
        return "NOT_FOUND"
    code_map = {
        400: "VALIDATION_ERROR",
        401: "AUTHENTICATION_REQUIRED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
    }
    return code_map.get(status_code, "API_ERROR")
