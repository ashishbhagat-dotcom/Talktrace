import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "error": True,
            "status_code": response.status_code,
            "detail": response.data,
        }
        # Flatten single-key detail for cleaner API errors
        if isinstance(response.data, dict) and "detail" in response.data:
            error_data["message"] = str(response.data["detail"])
        response.data = error_data
    else:
        logger.exception("Unhandled exception", exc_info=exc)
        response = Response(
            {"error": True, "status_code": 500, "message": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
