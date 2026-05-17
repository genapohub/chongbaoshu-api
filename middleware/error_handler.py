from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

async def error_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail}
    )

def throw_error(code: int, message: str):
    raise HTTPException(status_code=code, detail=message)
