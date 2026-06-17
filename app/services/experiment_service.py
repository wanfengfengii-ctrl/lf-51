from typing import Optional, List
from sqlalchemy.orm import Session
from ..repositories import experiment_repo, container_repo
from ..exceptions import NotFoundError, ValidationError
from .container_service import get_container_or_404


def get_experiment_or_404(db: Session, experiment_id: int):
    experiment = experiment_repo.get_experiment_by_id(db, experiment_id)
    if not experiment:
        raise NotFoundError("实验不存在")
    return experiment


def parse_data_points(time_points_str: str, water_levels_str: str) -> tuple:
    try:
        tp_list = [float(x.strip()) for x in time_points_str.split(",") if x.strip()]
        wl_list = [float(x.strip()) for x in water_levels_str.split(",") if x.strip()]
    except ValueError:
        raise ValidationError(["时间点和水位必须是有效的数字"])
    return tp_list, wl_list


def validate_experiment_data(tp_list: list, wl_list: list, capacity: float) -> list:
    errors = []
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
                if wl > capacity:
                    errors.append(f"第{i+1}个水位({wl})不能超过容器容量({capacity})")
                    break
    return errors


def create_experiment(db: Session, container_id: int, name: str, notes: Optional[str],
                      time_points: str, water_levels: str):
    container = get_container_or_404(db, container_id)
    tp_list, wl_list = parse_data_points(time_points, water_levels)
    errors = validate_experiment_data(tp_list, wl_list, container.capacity)
    if errors:
        raise ValidationError(errors)
    exp = experiment_repo.create_experiment(db, container_id=container_id, name=name, notes=notes)
    for t, wl in zip(tp_list, wl_list):
        experiment_repo.create_data_point(db, experiment_id=exp.id, time_point=t, water_level=wl)
    db.commit()
    return exp


def delete_experiment(db: Session, experiment_id: int):
    experiment = get_experiment_or_404(db, experiment_id)
    container_id = experiment.container_id
    experiment_repo.delete_experiment(db, experiment)
    db.commit()
    return container_id
