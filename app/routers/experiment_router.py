from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..services import experiment_service, container_service
from ..exceptions import ValidationError
from ..repositories import experiment_repo

from fastapi.templating import Jinja2Templates
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/containers/{container_id}/experiments/new", response_class=HTMLResponse)
def new_experiment_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    return templates.TemplateResponse("experiment_form.html", {
        "request": request,
        "container": container,
        "experiment": None
    })


@router.post("/containers/{container_id}/experiments", response_class=HTMLResponse)
def create_experiment(
    request: Request,
    container_id: int,
    name: str = Form(...),
    notes: Optional[str] = Form(None),
    time_points: str = Form(...),
    water_levels: str = Form(...),
    db: Session = Depends(get_db),
):
    container = container_service.get_container_or_404(db, container_id)
    form_data = {
        "name": name,
        "notes": notes,
        "time_points": time_points,
        "water_levels": water_levels,
    }
    try:
        experiment = experiment_service.create_experiment(
            db, container_id, name, notes, time_points, water_levels
        )
    except ValidationError as e:
        return templates.TemplateResponse("experiment_form.html", {
            "request": request,
            "container": container,
            "errors": e.errors,
            "form_data": form_data,
        })
    return RedirectResponse(
        url=f"/containers/{container_id}/experiments/{experiment.id}",
        status_code=303,
    )


@router.get("/containers/{container_id}/experiments/{experiment_id}", response_class=HTMLResponse)
def view_experiment(request: Request, container_id: int, experiment_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    experiment = experiment_service.get_experiment_or_404(db, experiment_id)
    return templates.TemplateResponse("experiment_detail.html", {
        "request": request,
        "container": container,
        "experiment": experiment,
    })


@router.post("/experiments/{experiment_id}/delete")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    container_id = experiment_service.delete_experiment(db, experiment_id)
    return RedirectResponse(url=f"/containers/{container_id}", status_code=303)


@router.get("/api/experiments/{experiment_id}/data")
def get_experiment_data(experiment_id: int, db: Session = Depends(get_db)):
    experiment = experiment_service.get_experiment_or_404(db, experiment_id)
    return {
        "times": [dp.time_point for dp in experiment.data_points],
        "levels": [dp.water_level for dp in experiment.data_points],
    }
