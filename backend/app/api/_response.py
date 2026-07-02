from fastapi.responses import JSONResponse


def ok(data: dict) -> JSONResponse:
    """Return a successful JSON envelope."""
    return JSONResponse({"success": True, "data": data})


def err(message: str, code: str, status: int = 400) -> JSONResponse:
    """Return an error JSON envelope."""
    return JSONResponse(
        {"success": False, "error": message, "code": code},
        status_code=status,
    )
