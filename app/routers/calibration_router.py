from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..services import calibration_service, container_service, scheme_service
from ..repositories import calibration_repo, experiment_repo
from ..exceptions import ValidationError, NotFoundError
from .. import models, schemas, physics

from fastapi.templating import Jinja2Templates
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/containers/{container_id}/calibrations/new", response_class=HTMLResponse)
def new_calibration_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    experiments = experiment_repo.get_experiments_by_container(db, container_id)
    return templates.TemplateResponse("calibration_form.html", {
        "request": request,
        "container": container,
        "experiments": experiments,
        "calibration": None,
    })


@router.post("/containers/{container_id}/calibrations", response_class=HTMLResponse)
def create_calibration(
    request: Request,
    container_id: int,
    experiment_id: int = Form(...),
    name: str = Form(...),
    candidate_count: int = Form(...),
    min_scale_count: int = Form(...),
    max_scale_count: int = Form(...),
    error_threshold: float = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    form_data = {
        "experiment_id": experiment_id,
        "name": name,
        "candidate_count": candidate_count,
        "min_scale_count": min_scale_count,
        "max_scale_count": max_scale_count,
        "error_threshold": error_threshold,
        "notes": notes,
    }
    try:
        calibration = calibration_service.create_calibration(
            db, container_id, experiment_id, name, candidate_count,
            min_scale_count, max_scale_count, error_threshold, notes,
        )
    except ValidationError as e:
        container = container_service.get_container_or_404(db, container_id)
        experiments = experiment_repo.get_experiments_by_container(db, container_id)
        return templates.TemplateResponse("calibration_form.html", {
            "request": request,
            "container": container,
            "experiments": experiments,
            "calibration": None,
            "errors": e.errors if hasattr(e, "errors") else [str(e)],
            "form_data": form_data,
        })
    return RedirectResponse(
        url=f"/containers/{container_id}/calibrations/{calibration.id}/recommendation",
        status_code=303,
    )


@router.get("/containers/{container_id}/calibrations/{calibration_id}/recommendation", response_class=HTMLResponse)
def recommendation(request: Request, container_id: int, calibration_id: int, db: Session = Depends(get_db)):
    container, calibration, recommended, alternatives, parameter_versions, review_records = calibration_service.get_recommendation(db, container_id, calibration_id)
    return templates.TemplateResponse("recommendation.html", {
        "request": request,
        "container": container,
        "calibration": calibration,
        "recommended_scheme": recommended,
        "alternative_schemes": alternatives,
        "parameter_versions": parameter_versions,
        "review_records": review_records,
    })


@router.get("/containers/{container_id}/calibrations", response_class=HTMLResponse)
def list_calibrations(request: Request, container_id: int, db: Session = Depends(get_db)):
    container, calibrations = calibration_service.list_calibrations(db, container_id)
    return templates.TemplateResponse("calibration_list.html", {
        "request": request,
        "container": container,
        "calibrations": calibrations,
    })


@router.post("/candidates/{candidate_id}/apply")
def apply_candidate(candidate_id: int, db: Session = Depends(get_db)):
    scheme, container = scheme_service.apply_candidate_to_scheme(db, candidate_id)
    return RedirectResponse(
        url=f"/containers/{container.id}/schemes/{scheme.id}",
        status_code=303,
    )


@router.post("/api/calibrations/{calibration_id}/review")
def create_review(calibration_id: int, review_data: schemas.ReviewRecordCreate, db: Session = Depends(get_db)):
    review = calibration_service.create_review(
        db, calibration_id, review_data.reviewer, review_data.review_result, review_data.comments,
    )
    return {
        "success": True,
        "review": {
            "id": review.id,
            "reviewer": review.reviewer,
            "review_result": review.review_result,
            "comments": review.comments,
            "reviewed_at": review.reviewed_at
        }
    }


@router.get("/api/calibrations/{calibration_id}/fitting_result")
def fitting_result(calibration_id: int, db: Session = Depends(get_db)):
    calibration = calibration_service.get_calibration_or_404(db, calibration_id)
    experiment = calibration.experiment
    container = calibration.container
    exp_points = [(dp.time_point, dp.water_level) for dp in experiment.data_points]
    calibrated_params = {
        "orifice_diameter": calibration.calibrated_orifice_diameter,
        "discharge_coefficient": calibration.calibrated_discharge_coefficient,
        "shape_params": calibration.calibrated_shape_params,
    }
    fitted_curve = physics.generate_fitted_curve(
        calibrated_params, container.initial_water_level, container.shape,
        container.capacity, container.shape_params,
    )
    return {
        "experiment_curve": [{"time": t, "level": l} for t, l in exp_points],
        "fitted_curve": [{"time": t, "level": l} for t, l in fitted_curve],
        "calibrated_params": {
            "orifice_diameter": calibrated_params["orifice_diameter"],
            "discharge_coefficient": calibrated_params["discharge_coefficient"],
            "original_orifice_diameter": container.orifice_diameter,
            "original_discharge_coefficient": 0.6
        },
        "metrics": {
            "rmse": calibration.rmse,
            "mae": calibration.mae,
            "r_squared": calibration.r_squared
        }
    }


@router.get("/api/calibrations/{calibration_id}/candidates")
def list_candidates(calibration_id: int, db: Session = Depends(get_db)):
    candidates = calibration_repo.get_candidates_by_calibration(db, calibration_id)
    return {"candidates": [
        {
            "id": c.id,
            "name": c.name,
            "scale_count": c.scale_count,
            "time_interval": c.time_interval,
            "error_threshold": c.error_threshold,
            "avg_error": c.avg_error,
            "max_error": c.max_error,
            "exceeds_count": c.exceeds_count,
            "rank": c.rank,
            "is_recommended": c.is_recommended
        }
        for c in candidates
    ]}


@router.get("/api/candidates/{candidate_id}/marks")
def candidate_marks(candidate_id: int, db: Session = Depends(get_db)):
    candidate = calibration_service.get_candidate_or_404(db, candidate_id)
    return {"marks": candidate.marks_data, "error_threshold": candidate.error_threshold}


@router.get("/api/calibrations/{calibration_id}/warning_segments")
def warning_segments(calibration_id: int, db: Session = Depends(get_db)):
    calibration = calibration_service.get_calibration_or_404(db, calibration_id)
    recommended = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id,
        models.CandidateScheme.is_recommended == True,
    ).first()
    if not recommended:
        return {"warning_segments": []}
    warnings = physics.detect_warning_segments(recommended.marks_data, recommended.error_threshold)
    return {"warning_segments": warnings}


@router.get("/api/containers/{container_id}/parameter_versions")
def parameter_versions(container_id: int, db: Session = Depends(get_db)):
    versions = calibration_repo.get_parameter_versions(db, container_id)
    return {"versions": [
        {
            "id": v.id,
            "version_number": v.version_number,
            "old_shape": v.old_shape,
            "new_shape": v.new_shape,
            "old_capacity": v.old_capacity,
            "new_capacity": v.new_capacity,
            "old_orifice_diameter": v.old_orifice_diameter,
            "new_orifice_diameter": v.new_orifice_diameter,
            "old_initial_water_level": v.old_initial_water_level,
            "new_initial_water_level": v.new_initial_water_level,
            "change_reason": v.change_reason,
            "changed_by": v.changed_by,
            "created_at": v.created_at
        }
        for v in versions
    ]}


@router.get("/api/calibrations/{calibration_id}/error_comparison")
def error_comparison(calibration_id: int, db: Session = Depends(get_db)):
    candidates = calibration_repo.get_candidates_by_calibration(db, calibration_id)
    comparison_data = [
        {
            "rank": c.rank,
            "name": c.name,
            "scale_count": c.scale_count,
            "time_interval": c.time_interval,
            "avg_error": c.avg_error,
            "max_error": c.max_error,
            "exceeds_count": c.exceeds_count,
            "is_recommended": c.is_recommended,
        }
        for c in candidates
    ]
    return {"comparison": comparison_data}
