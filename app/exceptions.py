from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Optional


class BusinessException(Exception):
    def __init__(self, message: str, status_code: int = 400, errors: Optional[List[str]] = None):
        self.message = message
        self.status_code = status_code
        self.errors = errors or []
        super().__init__(self.message)


class NotFoundError(BusinessException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, status_code=404)


class ValidationError(BusinessException):
    def __init__(self, errors: List[str]):
        super().__init__("数据校验失败", status_code=400, errors=errors)


class BusinessRuleError(BusinessException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "errors": exc.errors}
    )
