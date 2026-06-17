from typing import Optional
from sqlalchemy.orm import Session
from ..repositories import scheme_repo, container_repo
from ..exceptions import NotFoundError, ValidationError
from .. import physics
from .container_service import get_container_or_404


def get_scheme_or_404(db: Session, scheme_id: int):
    scheme = scheme_repo.get_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("刻度方案不存在")
    return scheme


def validate_scheme_params(scale_count: int, time_interval: float, error_threshold: float) -> list:
    errors = []
    if scale_count <= 0:
        errors.append("刻度数量必须大于0")
    if time_interval <= 0:
        errors.append("时间间隔必须大于0")
    if error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    return errors


def create_scheme(db: Session, container_id: int, name: str, scale_count: int,
                  time_interval: float, error_threshold: float = 5.0, description: Optional[str] = None):
    container = get_container_or_404(db, container_id)
    errors = validate_scheme_params(scale_count, time_interval, error_threshold)
    if errors:
        raise ValidationError(errors)
    marks = physics.generate_scale_marks(
        scale_count, time_interval, container.initial_water_level,
        container.orifice_diameter, container.shape, container.capacity,
        container.shape_params, error_threshold
    )
    scheme = scheme_repo.create_scheme(
        db, container_id=container_id, name=name, scale_count=scale_count,
        time_interval=time_interval, error_threshold=error_threshold,
        description=description, needs_review=False
    )
    for m in marks:
        scheme_repo.create_scale_mark(
            db, scheme_id=scheme.id,
            scale_index=m['scale_index'],
            theoretical_time=m['theoretical_time'],
            estimated_time=m['estimated_time'],
            water_level=m['water_level'],
            error=m['error'],
            exceeds_threshold=m['exceeds_threshold']
        )
    db.commit()
    return scheme


def recalculate_scheme(db: Session, container_id: int, scheme_id: int):
    container = get_container_or_404(db, container_id)
    scheme = get_scheme_or_404(db, scheme_id)
    marks = physics.generate_scale_marks(
        scheme.scale_count, scheme.time_interval, container.initial_water_level,
        container.orifice_diameter, container.shape, container.capacity,
        container.shape_params, scheme.error_threshold
    )
    scheme_repo.delete_scheme_marks(db, scheme)
    for m in marks:
        scheme_repo.create_scale_mark(
            db, scheme_id=scheme.id,
            scale_index=m['scale_index'],
            theoretical_time=m['theoretical_time'],
            estimated_time=m['estimated_time'],
            water_level=m['water_level'],
            error=m['error'],
            exceeds_threshold=m['exceeds_threshold']
        )
    scheme.needs_review = False
    db.commit()
    return scheme


def delete_scheme(db: Session, scheme_id: int):
    scheme = get_scheme_or_404(db, scheme_id)
    container_id = scheme.container_id
    scheme_repo.delete_scheme(db, scheme)
    db.commit()
    return container_id


def apply_candidate_to_scheme(db: Session, candidate_id: int):
    from ..repositories import calibration_repo
    from .calibration_service import get_candidate_or_404
    candidate = get_candidate_or_404(db, candidate_id)
    calibration = candidate.calibration
    container = calibration.container
    scheme = scheme_repo.create_scheme(
        db, container_id=container.id, calibration_id=calibration.id,
        name=f"[校准]{candidate.name}", scale_count=candidate.scale_count,
        time_interval=candidate.time_interval, error_threshold=candidate.error_threshold,
        description=f"基于校准记录 #{calibration.id} 的推荐方案", needs_review=False
    )
    for m in candidate.marks_data:
        scheme_repo.create_scale_mark(
            db, scheme_id=scheme.id,
            scale_index=m['scale_index'],
            theoretical_time=m['theoretical_time'],
            estimated_time=m['estimated_time'],
            water_level=m['water_level'],
            error=m['error'],
            exceeds_threshold=m['exceeds_threshold']
        )
    db.commit()
    return scheme, container
