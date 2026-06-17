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
