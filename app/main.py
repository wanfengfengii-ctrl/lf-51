from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os

from .database import engine, get_db, Base
from .middleware import ErrorHandlerMiddleware
from .exceptions import BusinessException

Base.metadata.create_all(bind=engine)

app = FastAPI(title="漏壶刻度研究系统")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.add_middleware(ErrorHandlerMiddleware)


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "errors": exc.errors}
    )


from .routers import container_router, experiment_router, scheme_router
from .routers import calibration_router, series_router, multi_calibration_router, export_router

app.include_router(container_router.router)
app.include_router(experiment_router.router)
app.include_router(scheme_router.router)
app.include_router(calibration_router.router)
app.include_router(series_router.router)
app.include_router(multi_calibration_router.router)
app.include_router(export_router.router)
