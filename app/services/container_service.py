from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..repositories import container_repo, experiment_repo, scheme_repo, calibration_repo
from ..exceptions import NotFoundError, ValidationError


def validate_container_params(capacity: float, orifice_diameter: float, initial_water_level: float) -> list:
    errors = []
    if capacity <= 0:
        errors.append("容器容量必须大于0")
    if orifice_diameter <= 0:
        errors.append("出水孔径必须大于0")
    if initial_water_level <= 0:
        errors.append("初始水位必须大于0")
    if initial_water_level > capacity:
        errors.append("初始水位不能超过容器容量")
    return errors


def get_container_or_404(db: Session, container_id: int):
    container = container_repo.get_container_by_id(db, container_id)
    if not container:
        raise NotFoundError("容器不存在")
    return container


def list_containers(db: Session):
    return container_repo.get_all_containers(db)


def create_container(db: Session, **kwargs):
    errors = validate_container_params(kwargs['capacity'], kwargs['orifice_diameter'], kwargs['initial_water_level'])
    if errors:
        raise ValidationError(errors)
    return container_repo.create_container(db, **kwargs)


def update_container(db: Session, container_id: int, change_reason: Optional[str] = None, changed_by: Optional[str] = None, **kwargs):
    container = get_container_or_404(db, container_id)
    errors = validate_container_params(kwargs['capacity'], kwargs['orifice_diameter'], kwargs['initial_water_level'])
    if errors:
        raise ValidationError(errors)
    param_changed = (
        container.shape != kwargs.get('shape') or
        container.capacity != kwargs.get('capacity') or
        container.orifice_diameter != kwargs.get('orifice_diameter') or
        container.initial_water_level != kwargs.get('initial_water_level') or
        container.shape_params != kwargs.get('shape_params')
    )
    if param_changed:
        version_count = container_repo.count_parameter_versions(db, container_id)
        container_repo.create_parameter_version(
            db,
            container_id=container_id,
            version_number=version_count + 1,
            old_shape=container.shape,
            new_shape=kwargs.get('shape'),
            old_capacity=container.capacity,
            new_capacity=kwargs.get('capacity'),
            old_orifice_diameter=container.orifice_diameter,
            new_orifice_diameter=kwargs.get('orifice_diameter'),
            old_initial_water_level=container.initial_water_level,
            new_initial_water_level=kwargs.get('initial_water_level'),
            old_shape_params=container.shape_params,
            new_shape_params=kwargs.get('shape_params'),
            change_reason=change_reason,
            changed_by=changed_by
        )
        scheme_repo.mark_schemes_need_review(db, container_id)
    container_repo.update_container(db, container, **kwargs)
    db.commit()
    return container


def delete_container(db: Session, container_id: int):
    container = get_container_or_404(db, container_id)
    container_repo.delete_container(db, container)
    db.commit()


def get_container_detail(db: Session, container_id: int):
    container = get_container_or_404(db, container_id)
    experiments = experiment_repo.get_experiments_by_container(db, container_id)
    schemes = scheme_repo.get_schemes_by_container(db, container_id)
    return container, experiments, schemes
