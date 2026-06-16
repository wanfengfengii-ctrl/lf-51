from fastapi import FastAPI, Depends, HTTPException, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from .database import engine, get_db, Base
from . import models, schemas, physics

Base.metadata.create_all(bind=engine)

app = FastAPI(title="漏壶刻度研究系统")

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "containers": containers})


@app.get("/containers/new", response_class=HTMLResponse)
async def new_container_form(request: Request):
    return templates.TemplateResponse("container_form.html", {"request": request, "container": None})


@app.post("/containers", response_class=HTMLResponse)
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
    errors = []
    if capacity <= 0:
        errors.append("容器容量必须大于0")
    if orifice_diameter <= 0:
        errors.append("出水孔径必须大于0")
    if initial_water_level <= 0:
        errors.append("初始水位必须大于0")
    if initial_water_level > capacity:
        errors.append("初始水位不能超过容器容量")

    if errors:
        return templates.TemplateResponse("container_form.html", {
            "request": request,
            "container": None,
            "errors": errors,
            "form_data": {
                "name": name, "shape": shape, "capacity": capacity,
                "orifice_diameter": orifice_diameter,
                "initial_water_level": initial_water_level,
                "description": description, "shape_params": shape_params
            }
        })

    db_container = models.Container(
        name=name, shape=shape, capacity=capacity,
        orifice_diameter=orifice_diameter,
        initial_water_level=initial_water_level,
        description=description, shape_params=shape_params
    )
    db.add(db_container)
    db.commit()
    db.refresh(db_container)
    return RedirectResponse(f"/containers/{db_container.id}", status_code=303)


@app.get("/containers/{container_id}", response_class=HTMLResponse)
async def view_container(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
    schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
    return templates.TemplateResponse("container_detail.html", {
        "request": request,
        "container": container,
        "experiments": experiments,
        "schemes": schemes
    })


@app.get("/containers/{container_id}/edit", response_class=HTMLResponse)
async def edit_container_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    return templates.TemplateResponse("container_form.html", {"request": request, "container": container})


@app.post("/containers/{container_id}/update", response_class=HTMLResponse)
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
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    errors = []
    if capacity <= 0:
        errors.append("容器容量必须大于0")
    if orifice_diameter <= 0:
        errors.append("出水孔径必须大于0")
    if initial_water_level <= 0:
        errors.append("初始水位必须大于0")
    if initial_water_level > capacity:
        errors.append("初始水位不能超过容器容量")

    if errors:
        return templates.TemplateResponse("container_form.html", {
            "request": request,
            "container": container,
            "errors": errors
        })

    param_changed = (
        container.shape != shape or
        container.capacity != capacity or
        container.orifice_diameter != orifice_diameter or
        container.initial_water_level != initial_water_level or
        container.shape_params != shape_params
    )

    container.name = name
    container.shape = shape
    container.capacity = capacity
    container.orifice_diameter = orifice_diameter
    container.initial_water_level = initial_water_level
    container.description = description
    container.shape_params = shape_params

    if param_changed:
        schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
        for scheme in schemes:
            scheme.needs_review = True

    db.commit()
    return RedirectResponse(f"/containers/{container_id}", status_code=303)


@app.post("/containers/{container_id}/delete", response_class=HTMLResponse)
async def delete_container(container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    db.delete(container)
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/containers/{container_id}/experiments/new", response_class=HTMLResponse)
async def new_experiment_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    return templates.TemplateResponse("experiment_form.html", {
        "request": request, "container": container, "experiment": None
    })


@app.post("/containers/{container_id}/experiments", response_class=HTMLResponse)
async def create_experiment(
    request: Request,
    container_id: int,
    name: str = Form(...),
    notes: Optional[str] = Form(None),
    time_points: str = Form(...),
    water_levels: str = Form(...),
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    errors = []
    try:
        tp_list = [float(x.strip()) for x in time_points.split(",") if x.strip()]
        wl_list = [float(x.strip()) for x in water_levels.split(",") if x.strip()]
    except ValueError:
        errors.append("时间点和水位必须是有效的数字")
        tp_list, wl_list = [], []

    if len(tp_list) != len(wl_list):
        errors.append("时间点数量与水位数量必须一致")

    if not errors:
        if len(tp_list) < 2:
            errors.append("至少需要2个数据点")

        seen_times = set()
        prev_time = None
        for i, t in enumerate(tp_list):
            if prev_time is not None and t <= prev_time:
                errors.append(f"时间点必须严格递增：第{i+1}个时间点({t})不大于前一个({prev_time})")
                break
            if t in seen_times:
                errors.append(f"重复的时间点：{t}")
                break
            seen_times.add(t)
            prev_time = t

        if not errors:
            for i, wl in enumerate(wl_list):
                if wl <= 0:
                    errors.append(f"第{i+1}个水位({wl})必须大于0")
                    break
                if wl > container.capacity:
                    errors.append(f"第{i+1}个水位({wl})不能超过容器容量({container.capacity})")
                    break

    if errors:
        return templates.TemplateResponse("experiment_form.html", {
            "request": request, "container": container, "experiment": None,
            "errors": errors,
            "form_data": {"name": name, "notes": notes, "time_points": time_points, "water_levels": water_levels}
        })

    db_exp = models.Experiment(container_id=container_id, name=name, notes=notes)
    db.add(db_exp)
    db.flush()

    for t, wl in zip(tp_list, wl_list):
        dp = models.ExperimentDataPoint(experiment_id=db_exp.id, time_point=t, water_level=wl)
        db.add(dp)

    db.commit()
    return RedirectResponse(f"/containers/{container_id}/experiments/{db_exp.id}", status_code=303)


@app.get("/containers/{container_id}/experiments/{experiment_id}", response_class=HTMLResponse)
async def view_experiment(request: Request, container_id: int, experiment_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not container or not experiment:
        raise HTTPException(status_code=404, detail="资源不存在")
    return templates.TemplateResponse("experiment_detail.html", {
        "request": request, "container": container, "experiment": experiment
    })


@app.post("/experiments/{experiment_id}/delete", response_class=HTMLResponse)
async def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="实验不存在")
    container_id = experiment.container_id
    db.delete(experiment)
    db.commit()
    return RedirectResponse(f"/containers/{container_id}", status_code=303)


@app.get("/containers/{container_id}/schemes/new", response_class=HTMLResponse)
async def new_scheme_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    return templates.TemplateResponse("scheme_form.html", {
        "request": request, "container": container, "scheme": None
    })


@app.post("/containers/{container_id}/schemes", response_class=HTMLResponse)
async def create_scheme(
    request: Request,
    container_id: int,
    name: str = Form(...),
    scale_count: int = Form(...),
    time_interval: float = Form(...),
    error_threshold: float = Form(5.0),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    errors = []
    if scale_count <= 0:
        errors.append("刻度数量必须大于0")
    if time_interval <= 0:
        errors.append("时间间隔必须大于0")
    if error_threshold <= 0:
        errors.append("误差阈值必须大于0")

    if errors:
        return templates.TemplateResponse("scheme_form.html", {
            "request": request, "container": container, "scheme": None,
            "errors": errors,
            "form_data": {"name": name, "scale_count": scale_count,
                          "time_interval": time_interval,
                          "error_threshold": error_threshold,
                          "description": description}
        })

    marks = physics.generate_scale_marks(
        scale_count, time_interval, container.initial_water_level,
        container.orifice_diameter, container.shape, container.capacity,
        container.shape_params, error_threshold
    )

    db_scheme = models.ScaleScheme(
        container_id=container_id, name=name, scale_count=scale_count,
        time_interval=time_interval, error_threshold=error_threshold,
        description=description, needs_review=False
    )
    db.add(db_scheme)
    db.flush()

    for m in marks:
        sm = models.ScaleMark(
            scheme_id=db_scheme.id,
            scale_index=m['scale_index'],
            theoretical_time=m['theoretical_time'],
            estimated_time=m['estimated_time'],
            water_level=m['water_level'],
            error=m['error'],
            exceeds_threshold=m['exceeds_threshold']
        )
        db.add(sm)

    db.commit()
    return RedirectResponse(f"/containers/{container_id}/schemes/{db_scheme.id}", status_code=303)


@app.get("/containers/{container_id}/schemes/{scheme_id}", response_class=HTMLResponse)
async def view_scheme(request: Request, container_id: int, scheme_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    scheme = db.query(models.ScaleScheme).filter(models.ScaleScheme.id == scheme_id).first()
    if not container or not scheme:
        raise HTTPException(status_code=404, detail="资源不存在")
    return templates.TemplateResponse("scheme_detail.html", {
        "request": request, "container": container, "scheme": scheme
    })


@app.post("/schemes/{scheme_id}/delete", response_class=HTMLResponse)
async def delete_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.ScaleScheme).filter(models.ScaleScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="刻度方案不存在")
    container_id = scheme.container_id
    db.delete(scheme)
    db.commit()
    return RedirectResponse(f"/containers/{container_id}", status_code=303)


@app.get("/containers/{container_id}/schemes/{scheme_id}/recalculate", response_class=HTMLResponse)
async def recalculate_scheme(container_id: int, scheme_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    scheme = db.query(models.ScaleScheme).filter(models.ScaleScheme.id == scheme_id).first()
    if not container or not scheme:
        raise HTTPException(status_code=404, detail="资源不存在")

    marks = physics.generate_scale_marks(
        scheme.scale_count, scheme.time_interval, container.initial_water_level,
        container.orifice_diameter, container.shape, container.capacity,
        container.shape_params, scheme.error_threshold
    )

    for old_mark in scheme.scale_marks:
        db.delete(old_mark)
    db.flush()

    for m in marks:
        sm = models.ScaleMark(
            scheme_id=scheme.id,
            scale_index=m['scale_index'],
            theoretical_time=m['theoretical_time'],
            estimated_time=m['estimated_time'],
            water_level=m['water_level'],
            error=m['error'],
            exceeds_threshold=m['exceeds_threshold']
        )
        db.add(sm)

    scheme.needs_review = False
    db.commit()
    return RedirectResponse(f"/containers/{container_id}/schemes/{scheme_id}", status_code=303)


@app.get("/containers/{container_id}/compare", response_class=HTMLResponse)
async def compare_schemes(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
    experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
    return templates.TemplateResponse("compare.html", {
        "request": request, "container": container,
        "schemes": schemes, "experiments": experiments
    })


@app.get("/api/containers/{container_id}/water_curve")
async def api_water_curve(container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    curve = physics.simulate_water_curve(
        container.initial_water_level, container.orifice_diameter,
        container.shape, container.capacity, container.shape_params
    )
    return {
        "times": [p[0] for p in curve],
        "levels": [p[1] for p in curve]
    }


@app.get("/api/experiments/{experiment_id}/data")
async def api_experiment_data(experiment_id: int, db: Session = Depends(get_db)):
    experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="实验不存在")
    return {
        "times": [dp.time_point for dp in experiment.data_points],
        "levels": [dp.water_level for dp in experiment.data_points]
    }


@app.get("/api/schemes/{scheme_id}/marks")
async def api_scheme_marks(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.ScaleScheme).filter(models.ScaleScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="刻度方案不存在")
    return {
        "marks": [{
            "index": m.scale_index,
            "theoretical_time": m.theoretical_time,
            "estimated_time": m.estimated_time,
            "water_level": m.water_level,
            "error": m.error,
            "exceeds_threshold": m.exceeds_threshold
        } for m in scheme.scale_marks]
    }


@app.get("/api/containers/{container_id}/schemes/compare")
async def api_compare_schemes(container_id: int, db: Session = Depends(get_db)):
    schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
    result = []
    for scheme in schemes:
        avg_error = physics.calculate_average_error([{
            'error': m.error
        } for m in scheme.scale_marks])
        max_error = physics.calculate_max_error([{
            'error': m.error
        } for m in scheme.scale_marks])
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
