from typing import Optional, List
from sqlalchemy.orm import Session
from ..repositories import calibration_repo, experiment_repo, container_repo
from ..exceptions import NotFoundError, ValidationError, BusinessRuleError
from .. import physics
from .container_service import get_container_or_404


def get_calibration_or_404(db: Session, calibration_id: int):
    calibration = calibration_repo.get_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("校准记录不存在")
    return calibration


def get_candidate_or_404(db: Session, candidate_id: int):
    from ..repositories.calibration_repo import get_candidate_by_id
    candidate = get_candidate_by_id(db, candidate_id)
    if not candidate:
        raise NotFoundError("候选方案不存在")
    return candidate


def validate_calibration_params(experiment, candidate_count: int, min_scale_count: int,
                                max_scale_count: int, error_threshold: float) -> list:
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
    return errors


def create_calibration(db: Session, container_id: int, experiment_id: int, name: str,
                       candidate_count: int = 5, min_scale_count: int = 10,
                       max_scale_count: int = 50, error_threshold: float = 5.0,
                       notes: Optional[str] = None):
    container = get_container_or_404(db, container_id)
    experiment = experiment_repo.get_experiment_by_id(db, experiment_id)
    if not experiment:
        raise NotFoundError("实验不存在")
    if experiment.container_id != container_id:
        raise BusinessRuleError("实验不属于该容器")
    errors = validate_calibration_params(experiment, candidate_count, min_scale_count, max_scale_count, error_threshold)
    if errors:
        raise ValidationError(errors)
    exp_points = [(dp.time_point, dp.water_level) for dp in experiment.data_points]
    calibrated_params = physics.calibrate_parameters(
        exp_points, container.initial_water_level, container.orifice_diameter,
        container.shape, container.capacity, container.shape_params
    )
    calibration = calibration_repo.create_calibration(
        db, container_id=container_id, experiment_id=experiment_id, name=name,
        calibrated_orifice_diameter=round(calibrated_params['orifice_diameter'], 6),
        calibrated_discharge_coefficient=round(calibrated_params['discharge_coefficient'], 6),
        calibrated_shape_params=container.shape_params,
        rmse=round(calibrated_params['rmse'], 6),
        mae=round(calibrated_params['mae'], 6),
        r_squared=round(calibrated_params['r_squared'], 6),
        status="completed", notes=notes
    )
    candidates = physics.generate_candidate_schemes(
        calibrated_params, container.initial_water_level, container.shape,
        container.capacity, container.shape_params, candidate_count,
        min_scale_count, max_scale_count, error_threshold
    )
    for candidate in candidates:
        calibration_repo.create_candidate_scheme(
            db, calibration_id=calibration.id,
            name=candidate['name'], scale_count=candidate['scale_count'],
            time_interval=candidate['time_interval'], error_threshold=error_threshold,
            avg_error=candidate['avg_error'], max_error=candidate['max_error'],
            exceeds_count=candidate['exceeds_count'], rank=candidate['rank'],
            marks_data=candidate['marks'], is_recommended=candidate['is_recommended']
        )
    db.commit()
    return calibration


def get_recommendation(db: Session, container_id: int, calibration_id: int):
    container = get_container_or_404(db, container_id)
    calibration = get_calibration_or_404(db, calibration_id)
    candidates = calibration_repo.get_candidates_by_calibration(db, calibration_id)
    if not candidates:
        raise NotFoundError("没有找到候选方案")
    recommended = next((c for c in candidates if c.is_recommended), candidates[0])
    alternatives = [c for c in candidates if not c.is_recommended]
    parameter_versions = calibration_repo.get_parameter_versions(db, container_id)
    review_records = calibration.review_records
    return container, calibration, recommended, alternatives, parameter_versions, review_records


def create_review(db: Session, calibration_id: int, reviewer: str, review_result: str, comments: Optional[str] = None):
    calibration = get_calibration_or_404(db, calibration_id)
    review = calibration_repo.create_review_record(
        db, calibration_id=calibration_id, reviewer=reviewer,
        review_result=review_result, comments=comments
    )
    if review_result == "approved":
        calibration.status = "approved"
    elif review_result == "rejected":
        calibration.status = "rejected"
    else:
        calibration.status = "needs_revision"
    db.commit()
    return review


def list_calibrations(db: Session, container_id: int):
    container = get_container_or_404(db, container_id)
    calibrations = calibration_repo.get_calibrations_by_container(db, container_id)
    return container, calibrations
