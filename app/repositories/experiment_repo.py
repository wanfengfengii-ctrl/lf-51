from sqlalchemy.orm import Session
from app.models import Experiment, ExperimentDataPoint
from typing import Optional


def get_experiments_by_container(db: Session, container_id: int) -> list:
    return db.query(Experiment).filter(Experiment.container_id == container_id).all()


def get_experiment_by_id(db: Session, experiment_id: int) -> Optional[Experiment]:
    return db.query(Experiment).filter(Experiment.id == experiment_id).first()


def create_experiment(db: Session, container_id: int, name: str, notes: Optional[str] = None) -> Experiment:
    experiment = Experiment(container_id=container_id, name=name, notes=notes)
    db.add(experiment)
    db.flush()
    return experiment


def create_data_point(db: Session, experiment_id: int, time_point: float, water_level: float) -> ExperimentDataPoint:
    dp = ExperimentDataPoint(experiment_id=experiment_id, time_point=time_point, water_level=water_level)
    db.add(dp)
    return dp


def delete_experiment(db: Session, experiment: Experiment) -> None:
    db.delete(experiment)
    db.commit()
