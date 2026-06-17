from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from fastapi.templating import Jinja2Templates
import os

from ..database import get_db
from ..services import series_service
from ..repositories import series_repo, container_repo
from ..exceptions import ValidationError, NotFoundError
from .. import models, physics
from ..utils import container_to_dict, stage_to_dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/series", response_class=HTMLResponse)
async def list_series(request: Request, db: Session = Depends(get_db)):
    systems = series_repo.get_all_series_systems(db)
    return templates.TemplateResponse("series_list.html", {"request": request, "systems": systems})


@router.get("/series/new", response_class=HTMLResponse)
async def new_series_form(request: Request, db: Session = Depends(get_db)):
    containers = container_repo.get_all_containers(db)
    container_dicts = [container_to_dict(c) for c in containers]
    return templates.TemplateResponse("series_form.html", {"request": request, "system": None, "containers": container_dicts, "stages": [], "form_data": None})


@router.post("/series", response_class=HTMLResponse)
async def create_series(
    request: Request,
    name: str = Form(...),
    dynasty: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    enable_temp_effect: Optional[str] = Form(None),
    base_temperature: float = Form(20.0),
    stage_container_ids: str = Form(...),
    stage_names: Optional[str] = Form(None),
    stage_refill_enabled: Optional[str] = Form(None),
    stage_refill_trigger: Optional[str] = Form(None),
    stage_refill_target: Optional[str] = Form(None),
    stage_orifice_override: Optional[str] = Form(None),
    stage_initial_override: Optional[str] = Form(None),
    stage_discharge_coeff: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    enable_temp = enable_temp_effect is not None
    try:
        system = series_service.create_series_system(
            db, name, dynasty, description, enable_temp, base_temperature,
            stage_container_ids, stage_names, stage_refill_enabled,
            stage_refill_trigger, stage_refill_target, stage_orifice_override,
            stage_initial_override, stage_discharge_coeff
        )
        return RedirectResponse(f"/series/{system.id}", status_code=303)
    except ValidationError as e:
        containers = container_repo.get_all_containers(db)
        container_dicts = [container_to_dict(c) for c in containers]
        return templates.TemplateResponse("series_form.html", {
            "request": request,
            "system": None,
            "containers": container_dicts,
            "stages": [],
            "errors": e.errors,
            "form_data": {
                "name": name,
                "dynasty": dynasty or "",
                "description": description or "",
                "enable_temp_effect": enable_temp,
                "base_temperature": base_temperature,
                "stage_container_ids": stage_container_ids,
                "stage_names": stage_names or "",
                "stage_refill_enabled": stage_refill_enabled or "",
                "stage_refill_trigger": stage_refill_trigger or "",
                "stage_refill_target": stage_refill_target or "",
                "stage_orifice_override": stage_orifice_override or "",
                "stage_initial_override": stage_initial_override or "",
                "stage_discharge_coeff": stage_discharge_coeff or ""
            }
        }, status_code=400)


@router.get("/series/{system_id}", response_class=HTMLResponse)
async def view_series(request: Request, system_id: int, db: Session = Depends(get_db)):
    system = series_service.get_system_or_404(db, system_id)
    time_schemes = series_repo.get_series_time_schemes(db, system_id)
    return templates.TemplateResponse("series_detail.html", {"request": request, "system": system, "time_schemes": time_schemes})


@router.get("/series/{system_id}/edit", response_class=HTMLResponse)
async def edit_series_form(request: Request, system_id: int, db: Session = Depends(get_db)):
    system = series_service.get_system_or_404(db, system_id)
    containers = container_repo.get_all_containers(db)
    container_dicts = [container_to_dict(c) for c in containers]
    stage_dicts = series_service.get_stages_dicts(db, system_id)
    return templates.TemplateResponse("series_form.html", {"request": request, "system": system, "containers": container_dicts, "stages": stage_dicts, "form_data": None})


@router.post("/series/{system_id}/update", response_class=HTMLResponse)
async def update_series(
    request: Request,
    system_id: int,
    name: str = Form(...),
    dynasty: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    enable_temp_effect: Optional[str] = Form(None),
    base_temperature: float = Form(20.0),
    stage_container_ids: str = Form(...),
    stage_names: Optional[str] = Form(None),
    stage_refill_enabled: Optional[str] = Form(None),
    stage_refill_trigger: Optional[str] = Form(None),
    stage_refill_target: Optional[str] = Form(None),
    stage_orifice_override: Optional[str] = Form(None),
    stage_initial_override: Optional[str] = Form(None),
    stage_discharge_coeff: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    enable_temp = enable_temp_effect is not None
    try:
        series_service.update_series_system(
            db, system_id, name, dynasty, description, enable_temp, base_temperature,
            stage_container_ids, stage_names, stage_refill_enabled,
            stage_refill_trigger, stage_refill_target, stage_orifice_override,
            stage_initial_override, stage_discharge_coeff
        )
        return RedirectResponse(f"/series/{system_id}", status_code=303)
    except ValidationError as e:
        system = series_service.get_system_or_404(db, system_id)
        containers = container_repo.get_all_containers(db)
        container_dicts = [container_to_dict(c) for c in containers]
        stage_dicts = series_service.get_stages_dicts(db, system_id)
        return templates.TemplateResponse("series_form.html", {
            "request": request,
            "system": system,
            "containers": container_dicts,
            "stages": stage_dicts,
            "errors": e.errors,
            "form_data": {
                "name": name,
                "dynasty": dynasty or "",
                "description": description or "",
                "enable_temp_effect": enable_temp,
                "base_temperature": base_temperature,
                "stage_container_ids": stage_container_ids,
                "stage_names": stage_names or "",
                "stage_refill_enabled": stage_refill_enabled or "",
                "stage_refill_trigger": stage_refill_trigger or "",
                "stage_refill_target": stage_refill_target or "",
                "stage_orifice_override": stage_orifice_override or "",
                "stage_initial_override": stage_initial_override or "",
                "stage_discharge_coeff": stage_discharge_coeff or ""
            }
        }, status_code=400)


@router.post("/series/{system_id}/delete", response_class=HTMLResponse)
async def delete_series(system_id: int, db: Session = Depends(get_db)):
    series_service.delete_series_system(db, system_id)
    return RedirectResponse("/series", status_code=303)


@router.post("/series/{system_id}/simulate", response_class=HTMLResponse)
async def simulate_series(
    request: Request,
    system_id: int,
    name: str = Form(...),
    shichen_count: int = Form(12),
    dynasty_format: str = Form("modern"),
    error_threshold: float = Form(30.0),
    temp_amplitude: float = Form(8.0),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        db_scheme = series_service.run_simulation(
            db, system_id, name, shichen_count, dynasty_format,
            error_threshold, temp_amplitude, description
        )
        return RedirectResponse(f"/series/{system_id}/schemes/{db_scheme.id}", status_code=303)
    except ValidationError as e:
        system = series_service.get_system_or_404(db, system_id)
        time_schemes = series_repo.get_series_time_schemes(db, system_id)
        return templates.TemplateResponse("series_detail.html", {
            "request": request,
            "system": system,
            "time_schemes": time_schemes,
            "errors": e.errors
        }, status_code=400)


@router.get("/series/{system_id}/schemes/{scheme_id}", response_class=HTMLResponse)
async def view_series_scheme(request: Request, system_id: int, scheme_id: int, db: Session = Depends(get_db)):
    system = series_service.get_system_or_404(db, system_id)
    scheme = series_repo.get_series_time_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("资源不存在")
    stages = series_service.get_stages_dicts(db, system_id)
    time_schemes = series_repo.get_series_time_schemes(db, system_id)
    return templates.TemplateResponse("series_detail.html", {
        "request": request,
        "system": system,
        "time_schemes": time_schemes,
        "active_scheme": scheme,
        "stages": stages
    })


@router.post("/series/schemes/{scheme_id}/delete")
async def delete_series_scheme(scheme_id: int, db: Session = Depends(get_db)):
    system_id = series_service.delete_series_scheme(db, scheme_id)
    return RedirectResponse(f"/series/{system_id}", status_code=303)


@router.get("/api/series/{system_id}/simulate")
async def api_simulate_series(
    system_id: int,
    shichen_count: int = 12,
    dynasty_format: str = "modern",
    error_threshold: float = 30.0,
    temp_amplitude: float = 8.0,
    db: Session = Depends(get_db)
):
    system = series_service.get_system_or_404(db, system_id)
    stages = series_service.get_stages_dicts(db, system_id)
    sim = physics.simulate_series_system(
        stages, enable_temp_effect=system.enable_temp_effect,
        base_temperature=system.base_temperature, temp_amplitude=temp_amplitude
    )
    last_curve = sim["stage_curves"][-1] if sim["stage_curves"] else []
    scheme = physics.generate_shichen_time_scheme(
        last_curve, sim["total_duration"], shichen_count, error_threshold, dynasty_format
    )
    stage_curves_out = [[{"time": t, "level": l} for t, l in sc] for sc in sim["stage_curves"]]
    temp_curve_out = [{"time": t, "temp": tmp} for t, tmp in sim.get("temp_curve", [])]
    return {
        "stage_curves": stage_curves_out,
        "temp_curve": temp_curve_out,
        "total_duration": sim["total_duration"],
        "marks": scheme["marks"],
        "total_error": scheme["total_error"],
        "avg_error": scheme["avg_error"],
        "max_error": scheme["max_error"],
        "error_curve": scheme["error_curve"],
        "warning_segments": scheme["warning_segments"],
        "recommendations": scheme["recommendations"]
    }


@router.get("/api/series/schemes/{scheme_id}/data")
async def api_series_scheme_data(scheme_id: int, db: Session = Depends(get_db)):
    scheme = series_repo.get_series_time_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("计时方案不存在")
    return {
        "id": scheme.id,
        "system_id": scheme.system_id,
        "name": scheme.name,
        "shichen_count": scheme.shichen_count,
        "dynasty_format": scheme.dynasty_format,
        "error_threshold": scheme.error_threshold,
        "total_duration": scheme.total_duration,
        "total_error": scheme.total_error,
        "avg_error": scheme.avg_error,
        "max_error": scheme.max_error,
        "marks": scheme.marks,
        "stage_curves": scheme.stage_curves,
        "error_curve": scheme.error_curve,
        "warning_segments": scheme.warning_segments,
        "recommendations": scheme.recommendations,
        "temp_curve": scheme.temp_curve,
        "description": scheme.description
    }
