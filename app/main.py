from fastapi import FastAPI, Depends, HTTPException, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
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
                "description": description if description is not None else '',
                "shape_params": shape_params if shape_params is not None else ''
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
    change_reason: Optional[str] = Form(None),
    changed_by: Optional[str] = Form(None),
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
            "errors": errors,
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

    param_changed = (
        container.shape != shape or
        container.capacity != capacity or
        container.orifice_diameter != orifice_diameter or
        container.initial_water_level != initial_water_level or
        container.shape_params != shape_params
    )

    if param_changed:
        max_version = db.query(models.ParameterVersion).filter(
            models.ParameterVersion.container_id == container_id
        ).count()
        
        param_version = models.ParameterVersion(
            container_id=container_id,
            version_number=max_version + 1,
            old_shape=container.shape,
            new_shape=shape,
            old_capacity=container.capacity,
            new_capacity=capacity,
            old_orifice_diameter=container.orifice_diameter,
            new_orifice_diameter=orifice_diameter,
            old_initial_water_level=container.initial_water_level,
            new_initial_water_level=initial_water_level,
            old_shape_params=container.shape_params,
            new_shape_params=shape_params,
            change_reason=change_reason,
            changed_by=changed_by
        )
        db.add(param_version)
        
        schemes = db.query(models.ScaleScheme).filter(models.ScaleScheme.container_id == container_id).all()
        for scheme in schemes:
            scheme.needs_review = True

    container.name = name
    container.shape = shape
    container.capacity = capacity
    container.orifice_diameter = orifice_diameter
    container.initial_water_level = initial_water_level
    container.description = description
    container.shape_params = shape_params

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
            "form_data": {
                "name": name,
                "notes": notes if notes is not None else '',
                "time_points": time_points,
                "water_levels": water_levels
            }
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
                          "description": description if description is not None else ''}
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


# ============================================
# 实验拟合校准与刻度复原推荐模块
# ============================================

@app.get("/containers/{container_id}/calibrations/new", response_class=HTMLResponse)
async def new_calibration_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
    return templates.TemplateResponse("calibration_form.html", {
        "request": request, "container": container, "experiments": experiments, "calibration": None
    })


@app.post("/containers/{container_id}/calibrations", response_class=HTMLResponse)
async def create_calibration(
    request: Request,
    container_id: int,
    name: str = Form(...),
    experiment_id: int = Form(...),
    candidate_count: int = Form(5),
    min_scale_count: int = Form(10),
    max_scale_count: int = Form(50),
    error_threshold: float = Form(5.0),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    experiment = db.query(models.Experiment).filter(models.Experiment.id == experiment_id).first()
    
    if not container or not experiment:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    if experiment.container_id != container_id:
        raise HTTPException(status_code=400, detail="实验不属于该容器")
    
    errors = []
    if len(experiment.data_points) < 2:
        errors.append("实验至少需要2个数据点才能进行校准")
    if candidate_count < 1 or candidate_count > 20:
        errors.append("候选方案数量必须在1-20之间")
    if min_scale_count < 1:
        errors.append("最小刻度数必须大于0")
    if max_scale_count <= min_scale_count:
        errors.append("最大刻度数必须大于最小刻度数")
    if error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    
    if errors:
        experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
        return templates.TemplateResponse("calibration_form.html", {
            "request": request, "container": container, "experiments": experiments, "calibration": None,
            "errors": errors,
            "form_data": {
                "name": name, "experiment_id": experiment_id,
                "candidate_count": candidate_count,
                "min_scale_count": min_scale_count,
                "max_scale_count": max_scale_count,
                "error_threshold": error_threshold,
                "notes": notes if notes is not None else ''
            }
        })
    
    exp_points = [(dp.time_point, dp.water_level) for dp in experiment.data_points]
    
    calibrated_params = physics.calibrate_parameters(
        exp_points,
        container.initial_water_level,
        container.orifice_diameter,
        container.shape,
        container.capacity,
        container.shape_params
    )
    
    db_calibration = models.CalibrationRecord(
        container_id=container_id,
        experiment_id=experiment_id,
        name=name,
        calibrated_orifice_diameter=round(calibrated_params['orifice_diameter'], 6),
        calibrated_discharge_coefficient=round(calibrated_params['discharge_coefficient'], 6),
        calibrated_shape_params=container.shape_params,
        rmse=round(calibrated_params['rmse'], 6),
        mae=round(calibrated_params['mae'], 6),
        r_squared=round(calibrated_params['r_squared'], 6),
        status="completed",
        notes=notes
    )
    db.add(db_calibration)
    db.flush()
    
    candidates = physics.generate_candidate_schemes(
        calibrated_params,
        container.initial_water_level,
        container.shape,
        container.capacity,
        container.shape_params,
        candidate_count,
        min_scale_count,
        max_scale_count,
        error_threshold
    )
    
    for candidate in candidates:
        db_candidate = models.CandidateScheme(
            calibration_id=db_calibration.id,
            name=candidate['name'],
            scale_count=candidate['scale_count'],
            time_interval=candidate['time_interval'],
            error_threshold=error_threshold,
            avg_error=candidate['avg_error'],
            max_error=candidate['max_error'],
            exceeds_count=candidate['exceeds_count'],
            rank=candidate['rank'],
            marks_data=candidate['marks'],
            is_recommended=candidate['is_recommended']
        )
        db.add(db_candidate)
    
    db.commit()
    return RedirectResponse(f"/containers/{container_id}/calibrations/{db_calibration.id}/recommendation", status_code=303)


@app.get("/containers/{container_id}/calibrations/{calibration_id}/recommendation", response_class=HTMLResponse)
async def view_recommendation(
    request: Request,
    container_id: int,
    calibration_id: int,
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    
    if not container or not calibration:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    candidates = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id
    ).order_by(models.CandidateScheme.rank).all()
    
    if not candidates:
        raise HTTPException(status_code=404, detail="没有找到候选方案")
    
    recommended = next((c for c in candidates if c.is_recommended), candidates[0])
    alternatives = [c for c in candidates if not c.is_recommended]
    
    parameter_versions = db.query(models.ParameterVersion).filter(
        models.ParameterVersion.container_id == container_id
    ).order_by(models.ParameterVersion.version_number.desc()).all()
    
    review_records = db.query(models.ReviewRecord).filter(
        models.ReviewRecord.calibration_id == calibration_id
    ).order_by(models.ReviewRecord.reviewed_at.desc()).all()
    
    return templates.TemplateResponse("recommendation.html", {
        "request": request,
        "container": container,
        "calibration": calibration,
        "recommended_scheme": recommended,
        "alternative_schemes": alternatives,
        "parameter_versions": parameter_versions,
        "review_records": review_records
    })


@app.get("/api/calibrations/{calibration_id}/fitting_result")
async def api_fitting_result(calibration_id: int, db: Session = Depends(get_db)):
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="校准记录不存在")
    
    experiment = calibration.experiment
    container = calibration.container
    
    exp_points = [(dp.time_point, dp.water_level) for dp in experiment.data_points]
    
    calibrated_params = {
        'orifice_diameter': calibration.calibrated_orifice_diameter,
        'discharge_coefficient': calibration.calibrated_discharge_coefficient,
        'shape_params': calibration.calibrated_shape_params
    }
    
    fitted_curve = physics.generate_fitted_curve(
        calibrated_params,
        container.initial_water_level,
        container.shape,
        container.capacity,
        container.shape_params
    )
    
    return {
        "experiment_curve": [{"time": t, "level": l} for t, l in exp_points],
        "fitted_curve": [{"time": t, "level": l} for t, l in fitted_curve],
        "calibrated_params": {
            "orifice_diameter": calibrated_params['orifice_diameter'],
            "discharge_coefficient": calibrated_params['discharge_coefficient'],
            "original_orifice_diameter": container.orifice_diameter,
            "original_discharge_coefficient": 0.6
        },
        "metrics": {
            "rmse": calibration.rmse,
            "mae": calibration.mae,
            "r_squared": calibration.r_squared
        }
    }


@app.get("/api/calibrations/{calibration_id}/candidates")
async def api_candidate_schemes(calibration_id: int, db: Session = Depends(get_db)):
    candidates = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id
    ).order_by(models.CandidateScheme.rank).all()
    
    return {
        "candidates": [{
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
        } for c in candidates]
    }


@app.get("/api/candidates/{candidate_id}/marks")
async def api_candidate_marks(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(models.CandidateScheme).filter(models.CandidateScheme.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")
    
    return {
        "marks": candidate.marks_data,
        "error_threshold": candidate.error_threshold
    }


@app.get("/api/calibrations/{calibration_id}/warning_segments")
async def api_warning_segments(calibration_id: int, db: Session = Depends(get_db)):
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="校准记录不存在")
    
    recommended = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id,
        models.CandidateScheme.is_recommended == True
    ).first()
    
    if not recommended:
        return {"warning_segments": []}
    
    warnings = physics.detect_warning_segments(
        recommended.marks_data,
        recommended.error_threshold
    )
    
    return {"warning_segments": warnings}


@app.get("/api/containers/{container_id}/parameter_versions")
async def api_parameter_versions(container_id: int, db: Session = Depends(get_db)):
    versions = db.query(models.ParameterVersion).filter(
        models.ParameterVersion.container_id == container_id
    ).order_by(models.ParameterVersion.version_number.desc()).all()
    
    return {
        "versions": [{
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
        } for v in versions]
    }


@app.get("/api/calibrations/{calibration_id}/error_comparison")
async def api_error_comparison(calibration_id: int, db: Session = Depends(get_db)):
    candidates = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id
    ).order_by(models.CandidateScheme.rank).all()
    
    comparison_data = []
    for c in candidates:
        comparison_data.append({
            "rank": c.rank,
            "name": c.name,
            "scale_count": c.scale_count,
            "time_interval": c.time_interval,
            "avg_error": c.avg_error,
            "max_error": c.max_error,
            "exceeds_count": c.exceeds_count,
            "is_recommended": c.is_recommended
        })
    
    return {"comparison": comparison_data}


@app.post("/api/calibrations/{calibration_id}/review")
async def create_review(
    calibration_id: int,
    review_data: schemas.ReviewRecordCreate,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="校准记录不存在")
    
    db_review = models.ReviewRecord(
        calibration_id=calibration_id,
        reviewer=review_data.reviewer,
        review_result=review_data.review_result,
        comments=review_data.comments
    )
    db.add(db_review)
    
    if review_data.review_result == "approved":
        calibration.status = "approved"
    elif review_data.review_result == "rejected":
        calibration.status = "rejected"
    else:
        calibration.status = "needs_revision"
    
    db.commit()
    db.refresh(db_review)
    
    return {
        "success": True,
        "review": {
            "id": db_review.id,
            "reviewer": db_review.reviewer,
            "review_result": db_review.review_result,
            "comments": db_review.comments,
            "reviewed_at": db_review.reviewed_at
        }
    }


@app.post("/candidates/{candidate_id}/apply", response_class=HTMLResponse)
async def apply_candidate_scheme(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(models.CandidateScheme).filter(models.CandidateScheme.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")
    
    calibration = candidate.calibration
    container = calibration.container
    
    db_scheme = models.ScaleScheme(
        container_id=container.id,
        calibration_id=calibration.id,
        name=f"[校准]{candidate.name}",
        scale_count=candidate.scale_count,
        time_interval=candidate.time_interval,
        error_threshold=candidate.error_threshold,
        description=f"基于校准记录 #{calibration.id} 的推荐方案",
        needs_review=False
    )
    db.add(db_scheme)
    db.flush()
    
    for m in candidate.marks_data:
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
    return RedirectResponse(f"/containers/{container.id}/schemes/{db_scheme.id}", status_code=303)


@app.get("/calibrations/{calibration_id}/export")
async def export_calibration_result(calibration_id: int, db: Session = Depends(get_db)):
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="校准记录不存在")
    
    container = calibration.container
    experiment = calibration.experiment
    candidates = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id
    ).order_by(models.CandidateScheme.rank).all()
    
    export_data = {
        "calibration": {
            "id": calibration.id,
            "name": calibration.name,
            "created_at": calibration.created_at.isoformat() if calibration.created_at else None,
            "status": calibration.status,
            "notes": calibration.notes,
            "calibrated_parameters": {
                "orifice_diameter": calibration.calibrated_orifice_diameter,
                "discharge_coefficient": calibration.calibrated_discharge_coefficient,
                "original_orifice_diameter": container.orifice_diameter,
                "original_discharge_coefficient": 0.6
            },
            "fit_metrics": {
                "rmse": calibration.rmse,
                "mae": calibration.mae,
                "r_squared": calibration.r_squared
            }
        },
        "container": {
            "id": container.id,
            "name": container.name,
            "shape": container.shape,
            "capacity": container.capacity,
            "initial_water_level": container.initial_water_level
        },
        "experiment": {
            "id": experiment.id,
            "name": experiment.name,
            "data_points": [{"time": dp.time_point, "level": dp.water_level} for dp in experiment.data_points]
        },
        "candidate_schemes": [{
            "rank": c.rank,
            "name": c.name,
            "scale_count": c.scale_count,
            "time_interval": c.time_interval,
            "is_recommended": c.is_recommended,
            "error_metrics": {
                "avg_error": c.avg_error,
                "max_error": c.max_error,
                "exceeds_count": c.exceeds_count
            },
            "marks": c.marks_data
        } for c in candidates]
    }
    
    return JSONResponse(
        content=export_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=calibration_{calibration_id}_result.json"
        }
    )


@app.get("/calibrations/{calibration_id}/export/csv")
async def export_calibration_csv(calibration_id: int, db: Session = Depends(get_db)):
    calibration = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.id == calibration_id).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="校准记录不存在")
    
    recommended = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id,
        models.CandidateScheme.is_recommended == True
    ).first()
    
    if not recommended:
        raise HTTPException(status_code=404, detail="没有找到推荐方案")
    
    csv_lines = [
        "刻度序号,理论时间(秒),估计时间(秒),水位(cm),误差(秒),是否超阈值",
    ]
    
    for mark in recommended.marks_data:
        csv_lines.append(
            f"{mark['scale_index']},{mark['theoretical_time']:.2f},{mark['estimated_time']:.2f},"
            f"{mark['water_level']:.4f},{mark['error']:.4f},{'是' if mark['exceeds_threshold'] else '否'}"
        )
    
    csv_content = "\n".join(csv_lines)
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=calibration_{calibration_id}_scale_marks.csv"
        }
    )


@app.get("/containers/{container_id}/calibrations", response_class=HTMLResponse)
async def list_calibrations(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    
    calibrations = db.query(models.CalibrationRecord).filter(
        models.CalibrationRecord.container_id == container_id
    ).order_by(models.CalibrationRecord.created_at.desc()).all()
    
    return templates.TemplateResponse("calibration_list.html", {
        "request": request, "container": container, "calibrations": calibrations
    })


# ============================================
# 多漏壶串联系统模拟与昼夜计时校正模块
# ============================================

def _stage_to_dict(stage: models.SeriesStage) -> Dict[str, Any]:
    c = stage.container
    return {
        "id": stage.id,
        "container_id": stage.container_id,
        "container_name": c.name if c else "",
        "container_shape": c.shape if c else "cylindrical",
        "container_capacity": c.capacity if c else 100,
        "container_orifice_diameter": c.orifice_diameter if c else 0.5,
        "container_initial_water_level": c.initial_water_level if c else 80,
        "shape": c.shape if c else "cylindrical",
        "capacity": c.capacity if c else 100,
        "orifice_diameter": c.orifice_diameter if c else 0.5,
        "initial_water_level": c.initial_water_level if c else 80,
        "shape_params": c.shape_params if c else None,
        "stage_order": stage.stage_order,
        "stage_name": stage.stage_name,
        "is_refill_enabled": stage.is_refill_enabled,
        "refill_trigger_level": stage.refill_trigger_level,
        "refill_target_level": stage.refill_target_level,
        "orifice_diameter_override": stage.orifice_diameter_override,
        "initial_level_override": stage.initial_level_override,
        "discharge_coefficient": stage.discharge_coefficient
    }


@app.get("/series", response_class=HTMLResponse)
async def list_series_systems(request: Request, db: Session = Depends(get_db)):
    systems = db.query(models.SeriesSystem).order_by(models.SeriesSystem.created_at.desc()).all()
    return templates.TemplateResponse("series_list.html", {
        "request": request, "systems": systems
    })


def _container_to_dict(c: models.Container) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "shape": c.shape,
        "capacity": c.capacity,
        "orifice_diameter": c.orifice_diameter,
        "initial_water_level": c.initial_water_level,
        "shape_params": c.shape_params,
        "description": c.description
    }


def _stage_to_dict(s: models.SeriesStage) -> Dict[str, Any]:
    return {
        "id": s.id,
        "stage_order": s.stage_order,
        "stage_name": s.stage_name,
        "container_id": s.container_id,
        "container": _container_to_dict(s.container) if s.container else None,
        "discharge_coefficient": s.discharge_coefficient,
        "is_refill_enabled": s.is_refill_enabled,
        "refill_trigger_level": s.refill_trigger_level,
        "refill_target_level": s.refill_target_level,
        "initial_level_override": s.initial_level_override,
        "orifice_diameter_override": s.orifice_diameter_override,
    }


@app.get("/series/new", response_class=HTMLResponse)
async def new_series_form(request: Request, db: Session = Depends(get_db)):
    containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
    container_dicts = [_container_to_dict(c) for c in containers]
    return templates.TemplateResponse("series_form.html", {
        "request": request, "system": None, "containers": container_dicts,
        "stages": [], "form_data": None
    })


@app.post("/series", response_class=HTMLResponse)
async def create_series_system(
    request: Request,
    name: str = Form(...),
    dynasty: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    enable_temp_effect: bool = Form(False),
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
    errors = []
    if not name:
        errors.append("系统名称不能为空")

    try:
        container_ids = [int(x.strip()) for x in stage_container_ids.split(",") if x.strip()]
    except ValueError:
        errors.append("串联容器ID列表格式错误")
        container_ids = []

    if len(container_ids) < 1:
        errors.append("至少需要一级漏壶")

    for cid in container_ids:
        c = db.query(models.Container).filter(models.Container.id == cid).first()
        if not c:
            errors.append(f"容器 ID={cid} 不存在")

    if errors:
        containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
        container_dicts = [_container_to_dict(c) for c in containers]
        return templates.TemplateResponse("series_form.html", {
            "request": request, "system": None, "containers": container_dicts,
            "stages": [], "errors": errors, "form_data": {
                "name": name, "dynasty": dynasty or "",
                "description": description or "",
                "enable_temp_effect": enable_temp_effect,
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
        })

    refill_set = set()
    if stage_refill_enabled:
        for x in stage_refill_enabled.split(","):
            x = x.strip()
            if x:
                try:
                    refill_set.add(int(x))
                except ValueError:
                    pass

    name_list = [x.strip() for x in (stage_names or "").split("|")] if stage_names else []
    trigger_list = [x.strip() for x in (stage_refill_trigger or "").split("|")] if stage_refill_trigger else []
    target_list = [x.strip() for x in (stage_refill_target or "").split("|")] if stage_refill_target else []
    orifice_list = [x.strip() for x in (stage_orifice_override or "").split("|")] if stage_orifice_override else []
    init_list = [x.strip() for x in (stage_initial_override or "").split("|")] if stage_initial_override else []
    dc_list = [x.strip() for x in (stage_discharge_coeff or "").split("|")] if stage_discharge_coeff else []

    db_system = models.SeriesSystem(
        name=name, dynasty=dynasty, description=description,
        enable_temp_effect=enable_temp_effect, base_temperature=base_temperature
    )
    db.add(db_system)
    db.flush()

    for idx, cid in enumerate(container_ids):
        def _get(lst, i, default=None):
            return lst[i].strip() if i < len(lst) and lst[i].strip() else default

        trigger_v = _get(trigger_list, idx)
        target_v = _get(target_list, idx)
        orifice_v = _get(orifice_list, idx)
        init_v = _get(init_list, idx)
        dc_v = _get(dc_list, idx)

        db_stage = models.SeriesStage(
            system_id=db_system.id,
            container_id=cid,
            stage_order=idx,
            stage_name=_get(name_list, idx),
            is_refill_enabled=idx in refill_set,
            refill_trigger_level=float(trigger_v) if trigger_v else None,
            refill_target_level=float(target_v) if target_v else None,
            orifice_diameter_override=float(orifice_v) if orifice_v else None,
            initial_level_override=float(init_v) if init_v else None,
            discharge_coefficient=float(dc_v) if dc_v else 0.6
        )
        db.add(db_stage)

    db.commit()
    db.refresh(db_system)
    return RedirectResponse(f"/series/{db_system.id}", status_code=303)


@app.get("/series/{system_id}", response_class=HTMLResponse)
async def view_series_system(request: Request, system_id: int, db: Session = Depends(get_db)):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")
    time_schemes = db.query(models.SeriesTimeScheme).filter(
        models.SeriesTimeScheme.system_id == system_id
    ).order_by(models.SeriesTimeScheme.created_at.desc()).all()
    return templates.TemplateResponse("series_detail.html", {
        "request": request, "system": system, "time_schemes": time_schemes
    })


@app.get("/series/{system_id}/edit", response_class=HTMLResponse)
async def edit_series_form(request: Request, system_id: int, db: Session = Depends(get_db)):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")
    containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
    container_dicts = [_container_to_dict(c) for c in containers]
    stage_dicts = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    return templates.TemplateResponse("series_form.html", {
        "request": request, "system": system, "containers": container_dicts,
        "stages": stage_dicts, "form_data": None
    })


@app.post("/series/{system_id}/update", response_class=HTMLResponse)
async def update_series_system(
    request: Request,
    system_id: int,
    name: str = Form(...),
    dynasty: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    enable_temp_effect: bool = Form(False),
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
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")

    errors = []
    try:
        container_ids = [int(x.strip()) for x in stage_container_ids.split(",") if x.strip()]
    except ValueError:
        errors.append("串联容器ID列表格式错误")
        container_ids = []

    if len(container_ids) < 1:
        errors.append("至少需要一级漏壶")

    for cid in container_ids:
        c = db.query(models.Container).filter(models.Container.id == cid).first()
        if not c:
            errors.append(f"容器 ID={cid} 不存在")

    if errors:
        containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
        container_dicts = [_container_to_dict(c) for c in containers]
        stage_dicts = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
        return templates.TemplateResponse("series_form.html", {
            "request": request, "system": system, "containers": container_dicts,
            "stages": stage_dicts, "errors": errors, "form_data": {
                "name": name, "dynasty": dynasty or "",
                "description": description or "",
                "enable_temp_effect": enable_temp_effect,
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
        })

    refill_set = set()
    if stage_refill_enabled:
        for x in stage_refill_enabled.split(","):
            x = x.strip()
            if x:
                try:
                    refill_set.add(int(x))
                except ValueError:
                    pass

    name_list = [x.strip() for x in (stage_names or "").split("|")] if stage_names else []
    trigger_list = [x.strip() for x in (stage_refill_trigger or "").split("|")] if stage_refill_trigger else []
    target_list = [x.strip() for x in (stage_refill_target or "").split("|")] if stage_refill_target else []
    orifice_list = [x.strip() for x in (stage_orifice_override or "").split("|")] if stage_orifice_override else []
    init_list = [x.strip() for x in (stage_initial_override or "").split("|")] if stage_initial_override else []
    dc_list = [x.strip() for x in (stage_discharge_coeff or "").split("|")] if stage_discharge_coeff else []

    system.name = name
    system.dynasty = dynasty
    system.description = description
    system.enable_temp_effect = enable_temp_effect
    system.base_temperature = base_temperature

    for old in system.stages:
        db.delete(old)
    db.flush()

    for idx, cid in enumerate(container_ids):
        def _get(lst, i, default=None):
            return lst[i].strip() if i < len(lst) and lst[i].strip() else default

        trigger_v = _get(trigger_list, idx)
        target_v = _get(target_list, idx)
        orifice_v = _get(orifice_list, idx)
        init_v = _get(init_list, idx)
        dc_v = _get(dc_list, idx)

        db_stage = models.SeriesStage(
            system_id=system.id,
            container_id=cid,
            stage_order=idx,
            stage_name=_get(name_list, idx),
            is_refill_enabled=idx in refill_set,
            refill_trigger_level=float(trigger_v) if trigger_v else None,
            refill_target_level=float(target_v) if target_v else None,
            orifice_diameter_override=float(orifice_v) if orifice_v else None,
            initial_level_override=float(init_v) if init_v else None,
            discharge_coefficient=float(dc_v) if dc_v else 0.6
        )
        db.add(db_stage)

    db.commit()
    return RedirectResponse(f"/series/{system.id}", status_code=303)


@app.post("/series/{system_id}/delete", response_class=HTMLResponse)
async def delete_series_system(system_id: int, db: Session = Depends(get_db)):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")
    db.delete(system)
    db.commit()
    return RedirectResponse("/series", status_code=303)


@app.post("/series/{system_id}/simulate", response_class=HTMLResponse)
async def run_series_simulation(
    system_id: int,
    name: str = Form(...),
    shichen_count: int = Form(12),
    dynasty_format: str = Form("modern"),
    error_threshold: float = Form(30.0),
    temp_amplitude: float = Form(8.0),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")

    errors = []
    if shichen_count < 1 or shichen_count > 24:
        errors.append("时辰数必须在1-24之间")
    if error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    if not name:
        errors.append("方案名称不能为空")

    if errors:
        time_schemes = db.query(models.SeriesTimeScheme).filter(
            models.SeriesTimeScheme.system_id == system_id
        ).order_by(models.SeriesTimeScheme.created_at.desc()).all()
        return templates.TemplateResponse("series_detail.html", {
            "request": None, "system": system, "time_schemes": time_schemes,
            "errors": errors
        })

    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    sim = physics.simulate_series_system(
        stages,
        enable_temp_effect=system.enable_temp_effect,
        base_temperature=system.base_temperature,
        temp_amplitude=temp_amplitude
    )

    last_curve = sim["stage_curves"][-1] if sim["stage_curves"] else []
    scheme_result = physics.generate_shichen_time_scheme(
        last_curve, sim["total_duration"], shichen_count, error_threshold, dynasty_format
    )

    stage_curves_json = []
    for sc in sim["stage_curves"]:
        stage_curves_json.append([{"time": t, "level": l} for t, l in sc])

    temp_curve_json = [{"time": t, "temp": tmp} for t, tmp in sim.get("temp_curve", [])]

    db_scheme = models.SeriesTimeScheme(
        system_id=system.id,
        name=name,
        shichen_count=shichen_count,
        dynasty_format=dynasty_format,
        error_threshold=error_threshold,
        total_duration=sim["total_duration"],
        total_error=scheme_result["total_error"],
        avg_error=scheme_result["avg_error"],
        max_error=scheme_result["max_error"],
        marks=scheme_result["marks"],
        stage_curves=stage_curves_json,
        error_curve=scheme_result["error_curve"],
        warning_segments=scheme_result["warning_segments"],
        recommendations=scheme_result["recommendations"],
        temp_curve=temp_curve_json,
        description=description
    )
    db.add(db_scheme)
    db.commit()
    return RedirectResponse(f"/series/{system_id}/schemes/{db_scheme.id}", status_code=303)


@app.get("/series/{system_id}/schemes/{scheme_id}", response_class=HTMLResponse)
async def view_series_scheme(
    request: Request, system_id: int, scheme_id: int, db: Session = Depends(get_db)
):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    scheme = db.query(models.SeriesTimeScheme).filter(models.SeriesTimeScheme.id == scheme_id).first()
    if not system or not scheme:
        raise HTTPException(status_code=404, detail="资源不存在")
    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    return templates.TemplateResponse("series_detail.html", {
        "request": request, "system": system,
        "time_schemes": db.query(models.SeriesTimeScheme).filter(
            models.SeriesTimeScheme.system_id == system_id
        ).order_by(models.SeriesTimeScheme.created_at.desc()).all(),
        "active_scheme": scheme, "stages": stages
    })


@app.post("/series/schemes/{scheme_id}/delete", response_class=HTMLResponse)
async def delete_series_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.SeriesTimeScheme).filter(models.SeriesTimeScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="计时方案不存在")
    system_id = scheme.system_id
    db.delete(scheme)
    db.commit()
    return RedirectResponse(f"/series/{system_id}", status_code=303)


@app.get("/api/series/{system_id}/simulate")
async def api_series_simulate(
    system_id: int,
    error_threshold: float = 30.0,
    shichen_count: int = 12,
    dynasty_format: str = "modern",
    temp_amplitude: float = 8.0,
    db: Session = Depends(get_db)
):
    system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == system_id).first()
    if not system:
        raise HTTPException(status_code=404, detail="串联系统不存在")

    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    sim = physics.simulate_series_system(
        stages, enable_temp_effect=system.enable_temp_effect,
        base_temperature=system.base_temperature, temp_amplitude=temp_amplitude
    )

    last_curve = sim["stage_curves"][-1] if sim["stage_curves"] else []
    scheme = physics.generate_shichen_time_scheme(
        last_curve, sim["total_duration"], shichen_count, error_threshold, dynasty_format
    )

    stage_curves_out = []
    for sc in sim["stage_curves"]:
        stage_curves_out.append([{"time": t, "level": l} for t, l in sc])

    temp_curve_out = [{"time": t, "temp": tmp} for t, tmp in sim.get("temp_curve", [])]

    return {
        "stage_curves": stage_curves_out,
        "temp_curve": temp_curve_out,
        "total_duration": sim["total_duration"],
        "final_levels": sim["final_levels"],
        "error_threshold": error_threshold,
        "shichen_count": shichen_count,
        "dynasty_format": dynasty_format,
        "marks": scheme["marks"],
        "error_curve": scheme["error_curve"],
        "total_error": scheme["total_error"],
        "avg_error": scheme["avg_error"],
        "max_error": scheme["max_error"],
        "warning_segments": scheme["warning_segments"],
        "recommendations": scheme["recommendations"]
    }


@app.get("/api/series/schemes/{scheme_id}/data")
async def api_series_scheme_data(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.SeriesTimeScheme).filter(models.SeriesTimeScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="计时方案不存在")
    return {
        "id": scheme.id,
        "name": scheme.name,
        "shichen_count": scheme.shichen_count,
        "dynasty_format": scheme.dynasty_format,
        "error_threshold": scheme.error_threshold,
        "total_duration": scheme.total_duration,
        "total_error": scheme.total_error,
        "avg_error": scheme.avg_error,
        "max_error": scheme.max_error,
        "marks": scheme.marks,
        "stage_curves": scheme.stage_curves or [],
        "error_curve": scheme.error_curve or [],
        "warning_segments": scheme.warning_segments or [],
        "recommendations": scheme.recommendations or [],
        "temp_curve": scheme.temp_curve or []
    }


@app.get("/series/schemes/{scheme_id}/export")
async def export_series_scheme_json(
    scheme_id: int, dynasty: str = "modern", db: Session = Depends(get_db)
):
    scheme = db.query(models.SeriesTimeScheme).filter(models.SeriesTimeScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="计时方案不存在")
    system = scheme.system
    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    export_data = physics.generate_dynasty_export(
        {
            "marks": scheme.marks,
            "total_duration": scheme.total_duration,
            "total_error": scheme.total_error,
            "avg_error": scheme.avg_error,
            "max_error": scheme.max_error
        },
        {"name": system.name, "dynasty": system.dynasty},
        stages,
        dynasty
    )
    export_data["generated_at"] = scheme.created_at.isoformat() if scheme.created_at else None
    return JSONResponse(
        content=export_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=series_{scheme_id}_{dynasty}_scale.json"
        }
    )


@app.get("/series/schemes/{scheme_id}/export/csv")
async def export_series_scheme_csv(
    scheme_id: int, dynasty: str = "modern", db: Session = Depends(get_db)
):
    scheme = db.query(models.SeriesTimeScheme).filter(models.SeriesTimeScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="计时方案不存在")

    fmt = physics.DYNASTY_FORMATS.get(dynasty, physics.DYNASTY_FORMATS["modern"])
    csv_lines = [
        f"朝代制式,{fmt['name']}",
        f"方案名称,{scheme.name}",
        f"总时长(小时),{scheme.total_duration / 3600:.3f}",
        f"累计误差(秒),{scheme.total_error:.3f}",
        f"平均误差(秒),{scheme.avg_error:.3f}",
        f"最大误差(秒),{scheme.max_error:.3f}",
        "",
        "时辰序号,时辰名称,对应现代时段,理论时间(秒),估计时间(秒),水位,误差(秒),是否超阈值,每时辰刻度数,刻度单位"
    ]
    for m in scheme.marks:
        hrs = m.get("shichen_hours", (0, 0))
        hr_str = f"{hrs[0]:02d}:00-{hrs[1]:02d}:00" if isinstance(hrs, (list, tuple)) else ""
        csv_lines.append(
            f"{m['scale_index']},{m.get('shichen_name','')},{hr_str},"
            f"{m['theoretical_time']:.2f},{m['estimated_time']:.2f},"
            f"{m['water_level']:.4f},{m['error']:.3f},"
            f"{'是' if m.get('exceeds_threshold') else '否'},"
            f"{m.get('subdivision_count', fmt['subdivisions'])},{m.get('subdivision_unit', fmt['unit'])}"
        )
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content="\n".join(csv_lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=series_{scheme_id}_{dynasty}_scale.csv"
        }
    )


# ============================================
# 多源实验对比校准与制度化刻度复原评审模块
# ============================================


# ---------- HTML 页面路由 ----------

@app.get("/containers/{container_id}/multi_calibrations", response_class=HTMLResponse)
async def list_multi_calibrations(
    request: Request, container_id: int, db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    calibrations = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.container_id == container_id
    ).order_by(models.MultiSourceCalibration.created_at.desc()).all()
    return templates.TemplateResponse("multi_calibration_list.html", {
        "request": request,
        "container": container,
        "calibrations": calibrations
    })


@app.get("/containers/{container_id}/multi_calibrations/new", response_class=HTMLResponse)
async def new_multi_calibration_form(
    request: Request, container_id: int, db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")
    experiments = db.query(models.Experiment).filter(models.Experiment.container_id == container_id).all()
    return templates.TemplateResponse("multi_calibration_form.html", {
        "request": request,
        "container": container,
        "experiments": experiments,
        "calibration": None,
        "form_data": None
    })


@app.get("/containers/{container_id}/multi_calibrations/{calibration_id}", response_class=HTMLResponse)
async def view_multi_calibration(
    request: Request, container_id: int, calibration_id: int, db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not container or not calibration:
        raise HTTPException(status_code=404, detail="资源不存在")

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = calibration.fitting_results
    consistency = calibration.consistency_analysis

    candidate_schemes = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.calibration_id == calibration_id
    ).order_by(models.MultiSourceCandidateScheme.rank).all()

    expert_reviews = calibration.expert_reviews
    scheme_eliminations = calibration.scheme_eliminations
    version_records = calibration.version_records
    review_reports = calibration.review_reports

    for cs in candidate_schemes:
        scores_list = []
        for s in cs.expert_scores:
            scores_list.append({
                "id": s.id,
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments,
                "scored_at": s.scored_at
            })
        cs._expert_scores_list = scores_list

    elim_lookup = {}
    for se in scheme_eliminations:
        elim_lookup[se.candidate_scheme_id] = {
            "id": se.id,
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else ""
        }

    return templates.TemplateResponse("multi_calibration_detail.html", {
        "request": request,
        "container": container,
        "calibration": calibration,
        "experiments": experiments,
        "fitting_results": fitting_results,
        "consistency_analysis": consistency,
        "candidate_schemes": candidate_schemes,
        "expert_reviews": expert_reviews,
        "scheme_eliminations": scheme_eliminations,
        "elim_lookup": elim_lookup,
        "version_records": version_records,
        "review_reports": review_reports
    })


# ---------- API 端点：多源校准核心 ----------

@app.post("/api/multi_calibrations", response_model=schemas.MultiSourceCalibrationResponse)
async def api_create_multi_calibration(
    data: schemas.MultiSourceCalibrationCreate,
    db: Session = Depends(get_db)
):
    container = db.query(models.Container).filter(models.Container.id == data.container_id).first()
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    if data.system_id is not None:
        system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == data.system_id).first()
        if not system:
            raise HTTPException(status_code=404, detail="串联系统不存在")

    errors = []
    if not data.experiments:
        errors.append("至少需要选择一组实验数据")
    if data.min_scale_count < 1:
        errors.append("最小刻度数必须大于0")
    if data.max_scale_count <= data.min_scale_count:
        errors.append("最大刻度数必须大于最小刻度数")
    if data.error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    valid_experiment_ids = set()
    for exp in data.experiments:
        db_exp = db.query(models.Experiment).filter(
            models.Experiment.id == exp.experiment_id,
            models.Experiment.container_id == data.container_id
        ).first()
        if not db_exp:
            raise HTTPException(status_code=400, detail=f"实验 ID={exp.experiment_id} 不存在")
        if len(db_exp.data_points) < 2:
            raise HTTPException(status_code=400, detail=f"实验 '{db_exp.name}' 至少需要2个数据点")
        valid_experiment_ids.add(exp.experiment_id)

    db_calibration = models.MultiSourceCalibration(
        container_id=data.container_id,
        system_id=data.system_id,
        name=data.name,
        calibration_method=data.calibration_method,
        status="pending",
        is_locked=False,
        notes=data.notes
    )
    db.add(db_calibration)
    db.flush()

    for exp_assoc in data.experiments:
        assoc = models.MultiSourceExperimentAssoc(
            calibration_id=db_calibration.id,
            experiment_id=exp_assoc.experiment_id,
            weight=exp_assoc.weight,
            is_included=exp_assoc.is_included
        )
        db.add(assoc)

    db.commit()
    db.refresh(db_calibration)
    return db_calibration


@app.post("/api/multi_calibrations/{calibration_id}/run")
async def api_run_multi_calibration(
    calibration_id: int,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    container = calibration.container
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    experiments_data = []
    for assoc in calibration.experiment_assocs:
        if not assoc.is_included:
            continue
        exp = assoc.experiment
        exp_points = [(dp.time_point, dp.water_level) for dp in exp.data_points]
        experiments_data.append({
            "experiment_id": exp.id,
            "experiment_name": exp.name,
            "points": exp_points,
            "weight": assoc.weight,
            "is_included": assoc.is_included
        })

    if not experiments_data:
        raise HTTPException(status_code=400, detail="没有有效的实验数据")

    try:
        result = physics.multi_source_calibrate(
            experiments_data,
            container.initial_water_level,
            container.orifice_diameter,
            container.shape,
            container.capacity,
            container.shape_params,
            calibration.calibration_method
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    for fr in calibration.fitting_results:
        db.delete(fr)
    if calibration.consistency_analysis:
        db.delete(calibration.consistency_analysis)
    for cs in calibration.candidate_schemes:
        db.delete(cs)
    db.flush()

    for fr in result["fitting_results"]:
        db_fr = models.MultiSourceFittingResult(
            calibration_id=calibration.id,
            experiment_id=fr["experiment_id"],
            calibrated_orifice_diameter=round(fr["calibrated_orifice_diameter"], 6),
            calibrated_discharge_coefficient=round(fr["calibrated_discharge_coefficient"], 6),
            calibrated_shape_params=container.shape_params,
            rmse=round(fr["rmse"], 6),
            mae=round(fr["mae"], 6),
            r_squared=round(fr["r_squared"], 6),
            fitting_curve=fr.get("fitting_curve")
        )
        db.add(db_fr)

    consistency_result = physics.analyze_consistency(result["fitting_results"])
    db_consistency = models.ConsistencyAnalysis(
        calibration_id=calibration.id,
        overall_consistency_score=consistency_result["overall_consistency_score"],
        parameter_consistency=consistency_result["parameter_consistency"],
        metric_consistency=consistency_result["metric_consistency"],
        outlier_experiments=consistency_result.get("outlier_experiments"),
        analysis_details=consistency_result.get("analysis_details"),
        conclusion=consistency_result.get("conclusion")
    )
    db.add(db_consistency)

    db.commit()
    db.refresh(calibration)

    return {
        "success": True,
        "calibration_id": calibration.id,
        "combined_params": result["combined_params"],
        "parameter_statistics": result["parameter_statistics"],
        "fitting_count": len(result["fitting_results"]),
        "consistency_score": consistency_result["overall_consistency_score"]
    }


@app.post("/api/multi_calibrations/{calibration_id}/generate_candidates")
async def api_generate_multi_candidates(
    calibration_id: int,
    data: schemas.MultiSourceCalibrationCreate,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    container = calibration.container
    if not container:
        raise HTTPException(status_code=404, detail="容器不存在")

    if not calibration.fitting_results:
        raise HTTPException(status_code=400, detail="请先执行联合校准")

    experiments_data = []
    for assoc in calibration.experiment_assocs:
        if not assoc.is_included:
            continue
        exp = assoc.experiment
        exp_points = [(dp.time_point, dp.water_level) for dp in exp.data_points]
        experiments_data.append({
            "experiment_id": exp.id,
            "experiment_name": exp.name,
            "points": exp_points,
            "weight": assoc.weight,
            "is_included": assoc.is_included
        })

    ms_result = physics.multi_source_calibrate(
        experiments_data,
        container.initial_water_level,
        container.orifice_diameter,
        container.shape,
        container.capacity,
        container.shape_params,
        calibration.calibration_method
    )
    combined_params = ms_result["combined_params"]

    candidates = physics.generate_multi_source_candidate_schemes(
        combined_params,
        container.initial_water_level,
        container.shape,
        container.capacity,
        container.shape_params,
        data.candidate_count,
        data.min_scale_count,
        data.max_scale_count,
        data.error_threshold
    )

    for old_cs in calibration.candidate_schemes:
        db.delete(old_cs)
    for old_elim in calibration.scheme_eliminations:
        db.delete(old_elim)
    db.flush()

    for candidate in candidates:
        db_cs = models.MultiSourceCandidateScheme(
            calibration_id=calibration.id,
            name=candidate["name"],
            scale_count=candidate["scale_count"],
            time_interval=candidate["time_interval"],
            error_threshold=candidate["error_threshold"],
            combined_orifice_diameter=candidate["combined_orifice_diameter"],
            combined_discharge_coefficient=candidate["combined_discharge_coefficient"],
            avg_error=candidate["avg_error"],
            max_error=candidate["max_error"],
            exceeds_count=candidate["exceeds_count"],
            overall_score=candidate["overall_score"],
            rank=candidate["rank"],
            marks_data=candidate["marks"],
            is_eliminated=False,
            is_final=False
        )
        db.add(db_cs)

    calibration.status = "candidates_generated"
    db.commit()

    return {
        "success": True,
        "calibration_id": calibration.id,
        "candidate_count": len(candidates),
        "candidates": [{
            "id": None,
            "name": c["name"],
            "scale_count": c["scale_count"],
            "time_interval": c["time_interval"],
            "avg_error": c["avg_error"],
            "max_error": c["max_error"],
            "overall_score": c["overall_score"],
            "rank": c["rank"]
        } for c in candidates]
    }


@app.get("/api/multi_calibrations/{calibration_id}/detail")
async def api_get_multi_calibration_detail(
    calibration_id: int, db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = []
    for fr in calibration.fitting_results:
        fitting_results.append({
            "id": fr.id,
            "experiment_id": fr.experiment_id,
            "experiment_name": fr.experiment.name if fr.experiment else "",
            "calibrated_orifice_diameter": fr.calibrated_orifice_diameter,
            "calibrated_discharge_coefficient": fr.calibrated_discharge_coefficient,
            "rmse": fr.rmse,
            "mae": fr.mae,
            "r_squared": fr.r_squared,
            "fitting_curve": fr.fitting_curve
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "id": ca.id,
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "analysis_details": ca.analysis_details,
            "conclusion": ca.conclusion
        }

    candidate_schemes = []
    for cs in calibration.candidate_schemes:
        expert_scores = []
        for s in cs.expert_scores:
            expert_scores.append({
                "id": s.id,
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments,
                "scored_at": s.scored_at.isoformat() if s.scored_at else None
            })
        candidate_schemes.append({
            "id": cs.id,
            "name": cs.name,
            "scale_count": cs.scale_count,
            "time_interval": cs.time_interval,
            "error_threshold": cs.error_threshold,
            "combined_orifice_diameter": cs.combined_orifice_diameter,
            "combined_discharge_coefficient": cs.combined_discharge_coefficient,
            "avg_error": cs.avg_error,
            "max_error": cs.max_error,
            "exceeds_count": cs.exceeds_count,
            "overall_score": cs.overall_score,
            "rank": cs.rank,
            "is_eliminated": cs.is_eliminated,
            "elimination_reason": cs.elimination_reason,
            "is_final": cs.is_final,
            "expert_scores": expert_scores,
            "expert_summary": physics.aggregate_expert_scores(expert_scores)
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "id": er.id,
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations,
            "reviewed_at": er.reviewed_at.isoformat() if er.reviewed_at else None
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "id": se.id,
            "candidate_scheme_id": se.candidate_scheme_id,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at.isoformat() if se.eliminated_at else None
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "id": vr.id,
            "version_number": vr.version_number,
            "parent_version_id": vr.parent_version_id,
            "candidate_scheme_id": vr.candidate_scheme_id,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "version_data": vr.version_data,
            "created_at": vr.created_at.isoformat() if vr.created_at else None
        })

    review_reports = []
    for rr in calibration.review_reports:
        review_reports.append({
            "id": rr.id,
            "report_type": rr.report_type,
            "report_format": rr.report_format,
            "generated_by": rr.generated_by,
            "created_at": rr.created_at.isoformat() if rr.created_at else None
        })

    return {
        "calibration": {
            "id": calibration.id,
            "container_id": calibration.container_id,
            "system_id": calibration.system_id,
            "name": calibration.name,
            "calibration_method": calibration.calibration_method,
            "status": calibration.status,
            "is_locked": calibration.is_locked,
            "locked_at": calibration.locked_at.isoformat() if calibration.locked_at else None,
            "locked_by": calibration.locked_by,
            "final_scheme_id": calibration.final_scheme_id,
            "notes": calibration.notes,
            "created_at": calibration.created_at.isoformat() if calibration.created_at else None,
            "updated_at": calibration.updated_at.isoformat() if calibration.updated_at else None
        },
        "experiments": experiments,
        "fitting_results": fitting_results,
        "consistency_analysis": consistency,
        "candidate_schemes": candidate_schemes,
        "expert_reviews": expert_reviews,
        "scheme_eliminations": scheme_eliminations,
        "version_records": version_records,
        "review_reports": review_reports
    }


# ---------- API 端点：专家评分与方案淘汰 ----------

@app.post("/api/expert_scores")
async def api_create_expert_score(
    data: schemas.ExpertScoreCreate,
    db: Session = Depends(get_db)
):
    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == data.candidate_scheme_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")

    overall = (data.accuracy_score * 0.4 + data.feasibility_score * 0.3 +
               data.historical_consistency_score * 0.3)

    db_score = models.ExpertScore(
        candidate_scheme_id=data.candidate_scheme_id,
        expert_name=data.expert_name,
        accuracy_score=data.accuracy_score,
        feasibility_score=data.feasibility_score,
        historical_consistency_score=data.historical_consistency_score,
        overall_score=round(overall, 2),
        comments=data.comments
    )
    db.add(db_score)
    db.commit()
    db.refresh(db_score)

    return {
        "success": True,
        "score": {
            "id": db_score.id,
            "candidate_scheme_id": db_score.candidate_scheme_id,
            "expert_name": db_score.expert_name,
            "accuracy_score": db_score.accuracy_score,
            "feasibility_score": db_score.feasibility_score,
            "historical_consistency_score": db_score.historical_consistency_score,
            "overall_score": db_score.overall_score,
            "comments": db_score.comments,
            "scored_at": db_score.scored_at.isoformat() if db_score.scored_at else None
        }
    }


@app.get("/api/multi_candidates/{candidate_id}/expert_scores")
async def api_get_candidate_expert_scores(
    candidate_id: int, db: Session = Depends(get_db)
):
    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")

    scores = []
    for s in candidate.expert_scores:
        scores.append({
            "id": s.id,
            "expert_name": s.expert_name,
            "accuracy_score": s.accuracy_score,
            "feasibility_score": s.feasibility_score,
            "historical_consistency_score": s.historical_consistency_score,
            "overall_score": s.overall_score,
            "comments": s.comments,
            "scored_at": s.scored_at.isoformat() if s.scored_at else None
        })

    return {
        "scores": scores,
        "summary": physics.aggregate_expert_scores(scores)
    }


@app.post("/api/multi_calibrations/{calibration_id}/expert_reviews")
async def api_create_expert_review(
    calibration_id: int,
    data: schemas.ExpertReviewCreate,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    db_review = models.ExpertReview(
        calibration_id=calibration_id,
        expert_name=data.expert_name,
        review_result=data.review_result,
        overall_comments=data.overall_comments,
        recommendations=data.recommendations
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)

    return {
        "success": True,
        "review": {
            "id": db_review.id,
            "calibration_id": db_review.calibration_id,
            "expert_name": db_review.expert_name,
            "review_result": db_review.review_result,
            "overall_comments": db_review.overall_comments,
            "recommendations": db_review.recommendations,
            "reviewed_at": db_review.reviewed_at.isoformat() if db_review.reviewed_at else None
        }
    }


@app.post("/api/scheme_eliminations")
async def api_eliminate_scheme(
    data: schemas.SchemeEliminationCreate,
    db: Session = Depends(get_db)
):
    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == data.candidate_scheme_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")

    if candidate.is_final:
        raise HTTPException(status_code=400, detail="最终方案不能被淘汰")

    calibration_id = candidate.calibration_id

    db_elim = models.SchemeElimination(
        calibration_id=calibration_id,
        candidate_scheme_id=data.candidate_scheme_id,
        eliminated_by=data.eliminated_by,
        elimination_reason=data.elimination_reason,
        elimination_criteria=data.elimination_criteria
    )
    db.add(db_elim)

    candidate.is_eliminated = True
    candidate.elimination_reason = data.elimination_reason

    db.commit()
    db.refresh(db_elim)

    return {
        "success": True,
        "elimination": {
            "id": db_elim.id,
            "candidate_scheme_id": db_elim.candidate_scheme_id,
            "candidate_scheme_name": candidate.name,
            "eliminated_by": db_elim.eliminated_by,
            "elimination_reason": db_elim.elimination_reason,
            "elimination_criteria": db_elim.elimination_criteria,
            "eliminated_at": db_elim.eliminated_at.isoformat() if db_elim.eliminated_at else None
        }
    }


# ---------- API 端点：版本对比与定稿锁定 ----------

@app.post("/api/multi_calibrations/{calibration_id}/finalize")
async def api_finalize_scheme(
    calibration_id: int,
    data: schemas.FinalizeSchemeRequest,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    if calibration.is_locked:
        raise HTTPException(status_code=400, detail="该校准已锁定，无法再次定稿")

    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == data.candidate_scheme_id,
        models.MultiSourceCandidateScheme.calibration_id == calibration_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")

    if candidate.is_eliminated:
        raise HTTPException(status_code=400, detail="已淘汰的方案不能作为最终方案")

    from sqlalchemy import func
    max_version = db.query(func.max(models.SchemeVersionRecord.version_number)).filter(
        models.SchemeVersionRecord.calibration_id == calibration_id
    ).scalar() or 0
    new_version_number = max_version + 1

    scheme_data = {
        "name": candidate.name,
        "scale_count": candidate.scale_count,
        "time_interval": candidate.time_interval,
        "error_threshold": candidate.error_threshold,
        "combined_orifice_diameter": candidate.combined_orifice_diameter,
        "combined_discharge_coefficient": candidate.combined_discharge_coefficient,
        "avg_error": candidate.avg_error,
        "max_error": candidate.max_error,
        "exceeds_count": candidate.exceeds_count,
        "overall_score": candidate.overall_score
    }

    db_version = models.SchemeVersionRecord(
        calibration_id=calibration_id,
        version_number=new_version_number,
        parent_version_id=None,
        candidate_scheme_id=candidate.id,
        change_description=data.version_description,
        changed_by=data.locked_by,
        version_data=scheme_data
    )
    db.add(db_version)
    db.flush()

    for cs in calibration.candidate_schemes:
        cs.is_final = False
    candidate.is_final = True

    calibration.final_scheme_id = candidate.id
    calibration.is_locked = True
    calibration.locked_at = func.now()
    calibration.locked_by = data.locked_by
    calibration.status = "finalized"

    db.commit()

    return {
        "success": True,
        "calibration_id": calibration.id,
        "final_scheme": {
            "id": candidate.id,
            "name": candidate.name,
            "scale_count": candidate.scale_count,
            "time_interval": candidate.time_interval,
            "avg_error": candidate.avg_error,
            "max_error": candidate.max_error,
            "overall_score": candidate.overall_score
        },
        "version_number": new_version_number,
        "locked_by": data.locked_by
    }


@app.post("/api/multi_calibrations/{calibration_id}/versions")
async def api_create_version_record(
    calibration_id: int,
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    from sqlalchemy import func
    max_version = db.query(func.max(models.SchemeVersionRecord.version_number)).filter(
        models.SchemeVersionRecord.calibration_id == calibration_id
    ).scalar() or 0
    new_version_number = max_version + 1

    db_version = models.SchemeVersionRecord(
        calibration_id=calibration_id,
        version_number=new_version_number,
        parent_version_id=data.get("parent_version_id"),
        candidate_scheme_id=data.get("candidate_scheme_id"),
        change_description=data.get("change_description", ""),
        changed_by=data.get("changed_by", "system"),
        version_data=data.get("version_data")
    )
    db.add(db_version)
    db.commit()
    db.refresh(db_version)

    return {
        "success": True,
        "version": {
            "id": db_version.id,
            "version_number": db_version.version_number,
            "parent_version_id": db_version.parent_version_id,
            "candidate_scheme_id": db_version.candidate_scheme_id,
            "change_description": db_version.change_description,
            "changed_by": db_version.changed_by,
            "created_at": db_version.created_at.isoformat() if db_version.created_at else None
        }
    }


@app.post("/api/versions/compare")
async def api_compare_versions(
    data: schemas.VersionCompareRequest,
    db: Session = Depends(get_db)
):
    v1 = db.query(models.SchemeVersionRecord).filter(
        models.SchemeVersionRecord.id == data.version1_id
    ).first()
    v2 = db.query(models.SchemeVersionRecord).filter(
        models.SchemeVersionRecord.id == data.version2_id
    ).first()

    if not v1 or not v2:
        raise HTTPException(status_code=404, detail="版本记录不存在")

    v1_data = v1.version_data or {}
    v2_data = v2.version_data or {}

    compare_result = physics.compare_versions(v1_data, v2_data)

    return {
        "version1": {
            "id": v1.id,
            "version_number": v1.version_number,
            "change_description": v1.change_description,
            "changed_by": v1.changed_by,
            "created_at": v1.created_at.isoformat() if v1.created_at else None,
            "version_data": v1_data
        },
        "version2": {
            "id": v2.id,
            "version_number": v2.version_number,
            "change_description": v2.change_description,
            "changed_by": v2.changed_by,
            "created_at": v2.created_at.isoformat() if v2.created_at else None,
            "version_data": v2_data
        },
        "differences": compare_result["differences"],
        "similarity_score": compare_result["similarity_score"],
        "change_count": compare_result["change_count"]
    }


@app.get("/api/multi_calibrations/{calibration_id}/versions")
async def api_get_calibration_versions(
    calibration_id: int, db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    versions = []
    for vr in calibration.version_records:
        versions.append({
            "id": vr.id,
            "version_number": vr.version_number,
            "parent_version_id": vr.parent_version_id,
            "candidate_scheme_id": vr.candidate_scheme_id,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "version_data": vr.version_data,
            "created_at": vr.created_at.isoformat() if vr.created_at else None
        })

    versions.sort(key=lambda x: x["version_number"])
    return {"versions": versions}


# ---------- API 端点：评审报告导出 ----------

@app.post("/api/multi_calibrations/{calibration_id}/reports")
async def api_generate_review_report(
    calibration_id: int,
    data: schemas.ReviewReportGenerateRequest,
    db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = []
    for fr in calibration.fitting_results:
        fitting_results.append({
            "id": fr.id,
            "experiment_id": fr.experiment_id,
            "experiment_name": fr.experiment.name if fr.experiment else "",
            "calibrated_orifice_diameter": fr.calibrated_orifice_diameter,
            "calibrated_discharge_coefficient": fr.calibrated_discharge_coefficient,
            "rmse": fr.rmse,
            "mae": fr.mae,
            "r_squared": fr.r_squared
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "conclusion": ca.conclusion
        }

    candidate_schemes = []
    for cs in calibration.candidate_schemes:
        expert_scores = []
        for s in cs.expert_scores:
            expert_scores.append({
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments
            })
        candidate_schemes.append({
            "id": cs.id,
            "name": cs.name,
            "scale_count": cs.scale_count,
            "time_interval": cs.time_interval,
            "error_threshold": cs.error_threshold,
            "combined_orifice_diameter": cs.combined_orifice_diameter,
            "combined_discharge_coefficient": cs.combined_discharge_coefficient,
            "avg_error": cs.avg_error,
            "max_error": cs.max_error,
            "exceeds_count": cs.exceeds_count,
            "overall_score": cs.overall_score,
            "rank": cs.rank,
            "is_eliminated": cs.is_eliminated,
            "elimination_reason": cs.elimination_reason,
            "is_final": cs.is_final,
            "expert_scores": expert_scores
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations,
            "reviewed_at": er.reviewed_at.isoformat() if er.reviewed_at else None
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "candidate_scheme_id": se.candidate_scheme_id,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at.isoformat() if se.eliminated_at else None
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "version_number": vr.version_number,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "created_at": vr.created_at.isoformat() if vr.created_at else None
        })

    cal_dict = {
        "id": calibration.id,
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "notes": calibration.notes
    }

    report_content = physics.generate_review_report_content(
        cal_dict,
        experiments,
        fitting_results,
        consistency,
        candidate_schemes,
        expert_reviews,
        scheme_eliminations,
        version_records,
        data.report_type
    )

    db_report = models.ReviewReport(
        calibration_id=calibration_id,
        report_type=data.report_type,
        report_format=data.report_format,
        report_content=report_content,
        generated_by=data.generated_by
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return {
        "success": True,
        "report_id": db_report.id,
        "report_type": data.report_type,
        "report_format": data.report_format,
        "report_content": report_content
    }


@app.get("/api/review_reports/{report_id}")
async def api_get_review_report(
    report_id: int, db: Session = Depends(get_db)
):
    report = db.query(models.ReviewReport).filter(
        models.ReviewReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="评审报告不存在")

    return {
        "id": report.id,
        "calibration_id": report.calibration_id,
        "report_type": report.report_type,
        "report_format": report.report_format,
        "report_content": report.report_content,
        "generated_by": report.generated_by,
        "created_at": report.created_at.isoformat() if report.created_at else None
    }


@app.get("/multi_calibrations/{calibration_id}/export")
async def export_multi_calibration_json(
    calibration_id: int, report_type: str = "full", db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = []
    for fr in calibration.fitting_results:
        fitting_results.append({
            "experiment_id": fr.experiment_id,
            "experiment_name": fr.experiment.name if fr.experiment else "",
            "calibrated_orifice_diameter": fr.calibrated_orifice_diameter,
            "calibrated_discharge_coefficient": fr.calibrated_discharge_coefficient,
            "rmse": fr.rmse,
            "mae": fr.mae,
            "r_squared": fr.r_squared
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "conclusion": ca.conclusion
        }

    candidate_schemes = []
    for cs in calibration.candidate_schemes:
        expert_scores = []
        for s in cs.expert_scores:
            expert_scores.append({
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments
            })
        candidate_schemes.append({
            "id": cs.id,
            "name": cs.name,
            "scale_count": cs.scale_count,
            "time_interval": cs.time_interval,
            "avg_error": cs.avg_error,
            "max_error": cs.max_error,
            "overall_score": cs.overall_score,
            "rank": cs.rank,
            "is_eliminated": cs.is_eliminated,
            "is_final": cs.is_final,
            "expert_scores": expert_scores
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "version_number": vr.version_number,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by
        })

    cal_dict = {
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "notes": calibration.notes
    }

    export_data = physics.generate_review_report_content(
        cal_dict,
        experiments,
        fitting_results,
        consistency,
        candidate_schemes,
        expert_reviews,
        scheme_eliminations,
        version_records,
        report_type
    )
    export_data["exported_at"] = calibration.updated_at.isoformat() if calibration.updated_at else None

    return JSONResponse(
        content=export_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=multi_calibration_{calibration_id}_{report_type}.json"
        }
    )


@app.get("/multi_calibrations/{calibration_id}/export/csv")
async def export_multi_calibration_csv(
    calibration_id: int, db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    final_scheme = None
    for cs in calibration.candidate_schemes:
        if cs.is_final:
            final_scheme = cs
            break

    if not final_scheme and calibration.candidate_schemes:
        final_scheme = calibration.candidate_schemes[0]

    if not final_scheme:
        raise HTTPException(status_code=404, detail="没有找到刻度方案")

    csv_lines = [
        f"校准名称,{calibration.name}",
        f"校准方法,{calibration.calibration_method}",
        f"状态,{calibration.status}",
        f"是否锁定,{'是' if calibration.is_locked else '否'}",
        f"锁定人,{calibration.locked_by or ''}",
        "",
        "=== 联合校准参数 ===",
        f"联合校准孔径,{final_scheme.combined_orifice_diameter}",
        f"联合校准流量系数,{final_scheme.combined_discharge_coefficient}",
        "",
        "=== 最终刻度方案 ===",
        f"方案名称,{final_scheme.name}",
        f"刻度数量,{final_scheme.scale_count}",
        f"时间间隔(秒),{final_scheme.time_interval}",
        f"误差阈值(秒),{final_scheme.error_threshold}",
        f"平均误差(秒),{final_scheme.avg_error:.4f}",
        f"最大误差(秒),{final_scheme.max_error:.4f}",
        f"超阈值数量,{final_scheme.exceeds_count}",
        f"综合评分,{final_scheme.overall_score:.2f}",
        "",
        "刻度序号,理论时间(秒),估计时间(秒),水位(cm),误差(秒),是否超阈值"
    ]

    for mark in final_scheme.marks_data:
        csv_lines.append(
            f"{mark['scale_index']},{mark['theoretical_time']:.2f},{mark['estimated_time']:.2f},"
            f"{mark['water_level']:.4f},{mark['error']:.4f},{'是' if mark['exceeds_threshold'] else '否'}"
        )

    if calibration.expert_reviews:
        csv_lines.append("")
        csv_lines.append("=== 专家评审 ===")
        csv_lines.append("专家姓名,评审结果,总体意见,建议")
        for er in calibration.expert_reviews:
            comments = (er.overall_comments or "").replace(",", "，").replace("\n", " ")
            recs = (er.recommendations or "").replace(",", "，").replace("\n", " ")
            csv_lines.append(f"{er.expert_name},{er.review_result},{comments},{recs}")

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content="\n".join(csv_lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=multi_calibration_{calibration_id}_report.csv"
        }
    )


@app.get("/api/multi_calibrations/{calibration_id}/institutional_conclusion")
async def api_get_institutional_conclusion(
    calibration_id: int, db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    consistency_score = None
    if calibration.consistency_analysis:
        consistency_score = calibration.consistency_analysis.overall_consistency_score

    approved_count = sum(1 for er in calibration.expert_reviews if er.review_result == "approved")

    summary = {
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "experiment_count": len(calibration.experiment_assocs),
        "fitting_result_count": len(calibration.fitting_results),
        "total_candidate_schemes": len(calibration.candidate_schemes),
        "active_schemes": sum(1 for cs in calibration.candidate_schemes if not cs.is_eliminated),
        "eliminated_schemes": sum(1 for cs in calibration.candidate_schemes if cs.is_eliminated),
        "expert_review_count": len(calibration.expert_reviews),
        "approved_reviews": approved_count,
        "rejected_reviews": sum(1 for er in calibration.expert_reviews if er.review_result == "rejected"),
        "version_count": len(calibration.version_records),
        "has_final_scheme": any(cs.is_final for cs in calibration.candidate_schemes),
        "consistency_score": consistency_score
    }

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "conclusion": ca.conclusion
        }

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result
        })

    final_scheme = None
    for cs in calibration.candidate_schemes:
        if cs.is_final:
            final_scheme = {
                "id": cs.id,
                "name": cs.name,
                "scale_count": cs.scale_count,
                "avg_error": cs.avg_error,
                "overall_score": cs.overall_score
            }
            break

    return physics.generate_institutional_review_conclusion(
        summary, consistency, expert_reviews, final_scheme
    )


@app.get("/api/multi_candidates/{candidate_id}/marks")
async def api_multi_candidate_marks(
    candidate_id: int, db: Session = Depends(get_db)
):
    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == candidate_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选方案不存在")

    return {
        "marks": candidate.marks_data,
        "error_threshold": candidate.error_threshold,
        "scheme_name": candidate.name,
        "scale_count": candidate.scale_count,
        "time_interval": candidate.time_interval
    }


@app.post("/api/multi_calibrations/{calibration_id}/delete")
async def api_delete_multi_calibration(
    calibration_id: int, db: Session = Depends(get_db)
):
    calibration = db.query(models.MultiSourceCalibration).filter(
        models.MultiSourceCalibration.id == calibration_id
    ).first()
    if not calibration:
        raise HTTPException(status_code=404, detail="多源校准记录不存在")

    container_id = calibration.container_id
    db.delete(calibration)
    db.commit()

    return {
        "success": True,
        "container_id": container_id
    }

