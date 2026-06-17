from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from ..repositories import series_repo, container_repo
from ..exceptions import NotFoundError, ValidationError
from .. import physics


from ..utils import container_to_dict as _container_to_dict, stage_to_dict as _stage_to_dict


def get_system_or_404(db: Session, system_id: int):
    system = series_repo.get_series_by_id(db, system_id)
    if not system:
        raise NotFoundError("串联系统不存在")
    return system


def parse_stage_container_ids(stage_container_ids: str) -> list:
    try:
        return [int(x.strip()) for x in stage_container_ids.split(",") if x.strip()]
    except ValueError:
        raise ValidationError(["串联容器ID列表格式错误"])


def _parse_pipe_delimited(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split("|")]


def _get_item(lst, i, default=None):
    return lst[i].strip() if i < len(lst) and lst[i].strip() else default


def validate_series_input(name: str, container_ids: list, db: Session) -> list:
    errors = []
    if not name:
        errors.append("系统名称不能为空")
    if len(container_ids) < 1:
        errors.append("至少需要一级漏壶")
    for cid in container_ids:
        c = container_repo.get_container_by_id(db, cid)
        if not c:
            errors.append(f"容器 ID={cid} 不存在")
    return errors


def _build_stages_from_form(db, system_id, container_ids, stage_names, stage_refill_enabled,
                             stage_refill_trigger, stage_refill_target, stage_orifice_override,
                             stage_initial_override, stage_discharge_coeff):
    refill_set = set()
    if stage_refill_enabled:
        for x in stage_refill_enabled.split(","):
            x = x.strip()
            if x:
                try:
                    refill_set.add(int(x))
                except ValueError:
                    pass
    name_list = _parse_pipe_delimited(stage_names)
    trigger_list = _parse_pipe_delimited(stage_refill_trigger)
    target_list = _parse_pipe_delimited(stage_refill_target)
    orifice_list = _parse_pipe_delimited(stage_orifice_override)
    init_list = _parse_pipe_delimited(stage_initial_override)
    dc_list = _parse_pipe_delimited(stage_discharge_coeff)
    for idx, cid in enumerate(container_ids):
        trigger_v = _get_item(trigger_list, idx)
        target_v = _get_item(target_list, idx)
        orifice_v = _get_item(orifice_list, idx)
        init_v = _get_item(init_list, idx)
        dc_v = _get_item(dc_list, idx)
        series_repo.create_series_stage(
            db, system_id=system_id, container_id=cid, stage_order=idx,
            stage_name=_get_item(name_list, idx),
            is_refill_enabled=idx in refill_set,
            refill_trigger_level=float(trigger_v) if trigger_v else None,
            refill_target_level=float(target_v) if target_v else None,
            orifice_diameter_override=float(orifice_v) if orifice_v else None,
            initial_level_override=float(init_v) if init_v else None,
            discharge_coefficient=float(dc_v) if dc_v else 0.6
        )


def create_series_system(db: Session, name: str, dynasty: Optional[str], description: Optional[str],
                          enable_temp_effect: bool, base_temperature: float,
                          stage_container_ids: str, stage_names: Optional[str] = None,
                          stage_refill_enabled: Optional[str] = None,
                          stage_refill_trigger: Optional[str] = None,
                          stage_refill_target: Optional[str] = None,
                          stage_orifice_override: Optional[str] = None,
                          stage_initial_override: Optional[str] = None,
                          stage_discharge_coeff: Optional[str] = None):
    container_ids = parse_stage_container_ids(stage_container_ids)
    errors = validate_series_input(name, container_ids, db)
    if errors:
        raise ValidationError(errors)
    system = series_repo.create_series_system(
        db, name=name, dynasty=dynasty, description=description,
        enable_temp_effect=enable_temp_effect, base_temperature=base_temperature
    )
    _build_stages_from_form(db, system.id, container_ids, stage_names, stage_refill_enabled,
                             stage_refill_trigger, stage_refill_target, stage_orifice_override,
                             stage_initial_override, stage_discharge_coeff)
    db.commit()
    db.refresh(system)
    return system


def update_series_system(db: Session, system_id: int, name: str, dynasty: Optional[str],
                          description: Optional[str], enable_temp_effect: bool, base_temperature: float,
                          stage_container_ids: str, stage_names: Optional[str] = None,
                          stage_refill_enabled: Optional[str] = None,
                          stage_refill_trigger: Optional[str] = None,
                          stage_refill_target: Optional[str] = None,
                          stage_orifice_override: Optional[str] = None,
                          stage_initial_override: Optional[str] = None,
                          stage_discharge_coeff: Optional[str] = None):
    system = get_system_or_404(db, system_id)
    container_ids = parse_stage_container_ids(stage_container_ids)
    errors = validate_series_input(name, container_ids, db)
    if errors:
        raise ValidationError(errors)
    series_repo.update_series_system(db, system, name=name, dynasty=dynasty, description=description,
                                      enable_temp_effect=enable_temp_effect, base_temperature=base_temperature)
    series_repo.delete_series_stages(db, system)
    _build_stages_from_form(db, system.id, container_ids, stage_names, stage_refill_enabled,
                             stage_refill_trigger, stage_refill_target, stage_orifice_override,
                             stage_initial_override, stage_discharge_coeff)
    db.commit()
    return system


def delete_series_system(db: Session, system_id: int):
    system = get_system_or_404(db, system_id)
    series_repo.delete_series_system(db, system)


def run_simulation(db: Session, system_id: int, name: str, shichen_count: int = 12,
                   dynasty_format: str = "modern", error_threshold: float = 30.0,
                   temp_amplitude: float = 8.0, description: Optional[str] = None):
    system = get_system_or_404(db, system_id)
    errors = []
    if shichen_count < 1 or shichen_count > 24:
        errors.append("时辰数必须在1-24之间")
    if error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    if not name:
        errors.append("方案名称不能为空")
    if errors:
        raise ValidationError(errors)
    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    sim = physics.simulate_series_system(
        stages, enable_temp_effect=system.enable_temp_effect,
        base_temperature=system.base_temperature, temp_amplitude=temp_amplitude
    )
    last_curve = sim["stage_curves"][-1] if sim["stage_curves"] else []
    scheme_result = physics.generate_shichen_time_scheme(
        last_curve, sim["total_duration"], shichen_count, error_threshold, dynasty_format
    )
    stage_curves_json = []
    for sc in sim["stage_curves"]:
        stage_curves_json.append([{"time": t, "level": l} for t, l in sc])
    temp_curve_json = [{"time": t, "temp": tmp} for t, tmp in sim.get("temp_curve", [])]
    db_scheme = series_repo.create_series_time_scheme(
        db, system_id=system.id, name=name, shichen_count=shichen_count,
        dynasty_format=dynasty_format, error_threshold=error_threshold,
        total_duration=sim["total_duration"], total_error=scheme_result["total_error"],
        avg_error=scheme_result["avg_error"], max_error=scheme_result["max_error"],
        marks=scheme_result["marks"], stage_curves=stage_curves_json,
        error_curve=scheme_result["error_curve"], warning_segments=scheme_result["warning_segments"],
        recommendations=scheme_result["recommendations"], temp_curve=temp_curve_json,
        description=description
    )
    db.commit()
    return db_scheme


def delete_series_scheme(db: Session, scheme_id: int):
    scheme = series_repo.get_series_time_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("计时方案不存在")
    system_id = scheme.system_id
    series_repo.delete_series_time_scheme(db, scheme)
    return system_id


def get_stages_dicts(db: Session, system_id: int):
    system = get_system_or_404(db, system_id)
    return [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]


def get_containers_dicts(db: Session):
    containers = container_repo.get_all_containers(db)
    return [_container_to_dict(c) for c in containers]
