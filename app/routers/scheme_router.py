from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..services import scheme_service, container_service
from ..exceptions import ValidationError
from .. import physics, models

from fastapi.templating import Jinja2Templates
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/containers/{container_id}/schemes/new", response_class=HTMLResponse)
def new_scheme(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    return templates.TemplateResponse("scheme_form.html", {
        "request": request,
        "container": container,
    })


@router.post("/containers/{container_id}/schemes")
def create_scheme(
    request: Request,
    container_id: int,
    name: str = Form(...),
    scale_count: int = Form(...),
    time_interval: float = Form(...),
    error_threshold: float = Form(5.0),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        scheme = scheme_service.create_scheme(
            db, container_id, name, scale_count, time_interval, error_threshold, description
        )
        return RedirectResponse(url=f"/containers/{container_id}/schemes/{scheme.id}", status_code=303)
    except ValidationError as e:
        container = container_service.get_container_or_404(db, container_id)
        return templates.TemplateResponse("scheme_form.html", {
            "request": request,
            "container": container,
            "errors": e.errors,
            "form_data": {
                "name": name,
                "scale_count": scale_count,
                "time_interval": time_interval,
                "error_threshold": error_threshold,
                "description": description,
            },
        }, status_code=400)


@router.get("/containers/{container_id}/schemes/{scheme_id}", response_class=HTMLResponse)
def view_scheme(request: Request, container_id: int, scheme_id: int, db: Session = Depends(get_db)):
    scheme = scheme_service.get_scheme_or_404(db, scheme_id)
    container = container_service.get_container_or_404(db, container_id)
    return templates.TemplateResponse("scheme_detail.html", {
        "request": request,
        "container": container,
        "scheme": scheme,
    })


@router.post("/schemes/{scheme_id}/delete")
def delete_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = scheme_service.get_scheme_or_404(db, scheme_id)
    container_id = scheme.container_id
    scheme_service.delete_scheme(db, scheme_id)
    return RedirectResponse(url=f"/containers/{container_id}", status_code=303)


@router.get("/containers/{container_id}/schemes/{scheme_id}/recalculate")
def recalculate_scheme(container_id: int, scheme_id: int, db: Session = Depends(get_db)):
    scheme = scheme_service.recalculate_scheme(db, container_id, scheme_id)
    return RedirectResponse(url=f"/containers/{container_id}/schemes/{scheme.id}", status_code=303)


@router.get("/containers/{container_id}/compare", response_class=HTMLResponse)
def compare_schemes(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
    experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
    return templates.TemplateResponse("compare.html", {
        "request": request,
        "container": container,
        "schemes": schemes,
        "experiments": experiments,
    })


@router.get("/api/containers/{container_id}/water_curve")
def water_curve_api(container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    curve = physics.simulate_water_curve(
        container.initial_water_level,
        container.orifice_diameter,
        container.shape,
        container.capacity,
        container.shape_params,
    )
    return {"times": [p[0] for p in curve], "levels": [p[1] for p in curve]}


@router.get("/api/schemes/{scheme_id}/marks")
def scheme_marks_api(scheme_id: int, db: Session = Depends(get_db)):
    scheme = scheme_service.get_scheme_or_404(db, scheme_id)
    return {"marks": [{
        "index": m.scale_index,
        "theoretical_time": m.theoretical_time,
        "estimated_time": m.estimated_time,
        "water_level": m.water_level,
        "error": m.error,
        "exceeds_threshold": m.exceeds_threshold
    } for m in scheme.scale_marks]}


@router.get("/api/containers/{container_id}/schemes/compare")
def compare_schemes_api(container_id: int, db: Session = Depends(get_db)):
    schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
    result = []
    for scheme in schemes:
        avg_error = physics.calculate_average_error([{"error": m.error} for m in scheme.scale_marks])
        max_error = physics.calculate_max_error([{"error": m.error} for m in scheme.scale_marks])
        exceeds_count = sum(1 for m in scheme.scale_marks if m.exceeds_threshold)
        result.append({
            'scheme_id': scheme.id,
            'scheme_name': scheme.name,
            'scale_count': scheme.scale_count,
            'time_interval': scheme.time_interval,
            'error_threshold': scheme.error_threshold,
            'needs_review': scheme.needs_review,
            'avg_error': round(avg_error, 4),
            'max_error': round(max_error, 4),
            'exceeds_count': exceeds_count
        })
    return {"schemes": result}
