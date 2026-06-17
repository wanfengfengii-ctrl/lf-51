from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from fastapi.templating import Jinja2Templates
import os

from ..database import get_db
from ..services import container_service
from ..exceptions import ValidationError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    containers = container_service.list_containers(db)
    return templates.TemplateResponse("index.html", {"request": request, "containers": containers})


@router.get("/containers/new", response_class=HTMLResponse)
async def new_container_form(request: Request):
    return templates.TemplateResponse("container_form.html", {"request": request, "container": None})


@router.post("/containers", response_class=HTMLResponse)
async def create_container(
    request: Request,
    name: str = Form(...),
    shape: str = Form(...),
    capacity: float = Form(...),
    orifice_diameter: float = Form(...),
    initial_water_level: float = Form(...),
    description: Optional[str] = Form(None),
    shape_params: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        container = container_service.create_container(
            db,
            name=name, shape=shape, capacity=capacity,
            orifice_diameter=orifice_diameter,
            initial_water_level=initial_water_level,
            description=description, shape_params=shape_params
        )
        return RedirectResponse(f"/containers/{container.id}", status_code=303)
    except ValidationError as e:
        return templates.TemplateResponse("container_form.html", {
            "request": request,
            "container": None,
            "errors": e.errors,
            "form_data": {
                "name": name, "shape": shape, "capacity": capacity,
                "orifice_diameter": orifice_diameter,
                "initial_water_level": initial_water_level,
                "description": description if description is not None else '',
                "shape_params": shape_params if shape_params is not None else ''
            }
        })


@router.get("/containers/{container_id}", response_class=HTMLResponse)
async def view_container(request: Request, container_id: int, db: Session = Depends(get_db)):
    container, experiments, schemes = container_service.get_container_detail(db, container_id)
    return templates.TemplateResponse("container_detail.html", {
        "request": request,
        "container": container,
        "experiments": experiments,
        "schemes": schemes
    })


@router.get("/containers/{container_id}/edit", response_class=HTMLResponse)
async def edit_container_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container, _, _ = container_service.get_container_detail(db, container_id)
    return templates.TemplateResponse("container_form.html", {"request": request, "container": container})


@router.post("/containers/{container_id}/update", response_class=HTMLResponse)
async def update_container(
    request: Request,
    container_id: int,
    name: str = Form(...),
    shape: str = Form(...),
    capacity: float = Form(...),
    orifice_diameter: float = Form(...),
    initial_water_level: float = Form(...),
    description: Optional[str] = Form(None),
    shape_params: Optional[str] = Form(None),
    change_reason: Optional[str] = Form(None),
    changed_by: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        container_service.update_container(
            db, container_id,
            change_reason=change_reason, changed_by=changed_by,
            name=name, shape=shape, capacity=capacity,
            orifice_diameter=orifice_diameter,
            initial_water_level=initial_water_level,
            description=description, shape_params=shape_params
        )
        return RedirectResponse(f"/containers/{container_id}", status_code=303)
    except ValidationError as e:
        container, _, _ = container_service.get_container_detail(db, container_id)
        return templates.TemplateResponse("container_form.html", {
            "request": request,
            "container": container,
            "errors": e.errors,
            "form_data": {
                "name": name, "shape": shape, "capacity": capacity,
                "orifice_diameter": orifice_diameter,
                "initial_water_level": initial_water_level,
                "description": description if description is not None else '',
                "shape_params": shape_params if shape_params is not None else '',
                "change_reason": change_reason if change_reason is not None else '',
                "changed_by": changed_by if changed_by is not None else ''
            }
        })


@router.post("/containers/{container_id}/delete", response_class=HTMLResponse)
async def delete_container(container_id: int, db: Session = Depends(get_db)):
    container_service.delete_container(db, container_id)
    return RedirectResponse("/", status_code=303)
