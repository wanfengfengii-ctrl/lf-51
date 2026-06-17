from sqlalchemy.orm import Session
from app.models import SeriesSystem, SeriesStage, SeriesTimeScheme
from typing import Optional


def get_all_series_systems(db: Session) -> list:
    return db.query(SeriesSystem).order_by(SeriesSystem.created_at.desc()).all()


def get_series_by_id(db: Session, system_id: int) -> Optional[SeriesSystem]:
    return db.query(SeriesSystem).filter(SeriesSystem.id == system_id).first()


def create_series_system(db: Session, **kwargs) -> SeriesSystem:
    system = SeriesSystem(**kwargs)
    db.add(system)
    db.flush()
    return system


def update_series_system(db: Session, system: SeriesSystem, **kwargs) -> None:
    for key, value in kwargs.items():
        setattr(system, key, value)


def delete_series_system(db: Session, system: SeriesSystem) -> None:
    db.delete(system)
    db.commit()


def create_series_stage(db: Session, **kwargs) -> SeriesStage:
    stage = SeriesStage(**kwargs)
    db.add(stage)
    return stage


def delete_series_stages(db: Session, system: SeriesSystem) -> None:
    for stage in system.stages:
        db.delete(stage)
    db.flush()


def get_series_time_schemes(db: Session, system_id: int) -> list:
    return db.query(SeriesTimeScheme).filter(
        SeriesTimeScheme.system_id == system_id
    ).order_by(SeriesTimeScheme.created_at.desc()).all()


def get_series_time_scheme_by_id(db: Session, scheme_id: int) -> Optional[SeriesTimeScheme]:
    return db.query(SeriesTimeScheme).filter(SeriesTimeScheme.id == scheme_id).first()


def create_series_time_scheme(db: Session, **kwargs) -> SeriesTimeScheme:
    scheme = SeriesTimeScheme(**kwargs)
    db.add(scheme)
    return scheme


def delete_series_time_scheme(db: Session, scheme: SeriesTimeScheme) -> None:
    db.delete(scheme)
    db.commit()
