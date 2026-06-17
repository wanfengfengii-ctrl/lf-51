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


@app.get("/series/new", response_class=HTMLResponse)
async def new_series_form(request: Request, db: Session = Depends(get_db)):
    containers = db.query(models.Container).order_by(models.Container.created_at.desc()).all()
    return templates.TemplateResponse("series_form.html", {
        "request": request, "system": None, "containers": containers
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
        return templates.TemplateResponse("series_form.html", {
            "request": request, "system": None, "containers": containers,
            "errors": errors, "form_data": {
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
    return templates.TemplateResponse("series_form.html", {
        "request": request, "system": system, "containers": containers
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
        return templates.TemplateResponse("series_form.html", {
            "request": request, "system": system, "containers": containers,
            "errors": errors, "form_data": {
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
