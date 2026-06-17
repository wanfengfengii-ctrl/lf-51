from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import export_service

router = APIRouter()


@router.get("/calibrations/{calibration_id}/export")
def export_calibration_json(calibration_id: int, db: Session = Depends(get_db)):
    data, media_type, filename = export_service.export_calibration_json(db, calibration_id)
    return JSONResponse(content=data, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/calibrations/{calibration_id}/export/csv")
def export_calibration_csv(calibration_id: int, db: Session = Depends(get_db)):
    content, media_type, filename = export_service.export_calibration_csv(db, calibration_id)
    return PlainTextResponse(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/series/schemes/{scheme_id}/export")
def export_series_scheme_json(scheme_id: int, dynasty: str = "modern", db: Session = Depends(get_db)):
    data, media_type, filename = export_service.export_series_scheme_json(db, scheme_id, dynasty)
    return JSONResponse(content=data, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/series/schemes/{scheme_id}/export/csv")
def export_series_scheme_csv(scheme_id: int, dynasty: str = "modern", db: Session = Depends(get_db)):
    content, media_type, filename = export_service.export_series_scheme_csv(db, scheme_id, dynasty)
    return PlainTextResponse(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/multi_calibrations/{calibration_id}/export")
def export_multi_calibration_json(calibration_id: int, report_type: str = "full", db: Session = Depends(get_db)):
    data, media_type, filename = export_service.export_multi_calibration_json(db, calibration_id, report_type)
    return JSONResponse(content=data, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/multi_calibrations/{calibration_id}/export/csv")
def export_multi_calibration_csv(calibration_id: int, db: Session = Depends(get_db)):
    content, media_type, filename = export_service.export_multi_calibration_csv(db, calibration_id)
    return PlainTextResponse(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
