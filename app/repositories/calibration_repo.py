from sqlalchemy.orm import Session
from app.models import CalibrationRecord, CandidateScheme, ReviewRecord, ParameterVersion
from typing import Optional


def get_calibrations_by_container(db: Session, container_id: int) -> list:
    return db.query(CalibrationRecord).filter(
        CalibrationRecord.container_id == container_id
    ).order_by(CalibrationRecord.created_at.desc()).all()


def get_calibration_by_id(db: Session, calibration_id: int) -> Optional[CalibrationRecord]:
    return db.query(CalibrationRecord).filter(CalibrationRecord.id == calibration_id).first()


def create_calibration(db: Session, **kwargs) -> CalibrationRecord:
    calibration = CalibrationRecord(**kwargs)
    db.add(calibration)
    db.flush()
    return calibration


def create_candidate_scheme(db: Session, **kwargs) -> CandidateScheme:
    candidate = CandidateScheme(**kwargs)
    db.add(candidate)
    return candidate


def get_candidates_by_calibration(db: Session, calibration_id: int) -> list:
    return db.query(CandidateScheme).filter(
        CandidateScheme.calibration_id == calibration_id
    ).order_by(CandidateScheme.rank).all()


def create_review_record(db: Session, **kwargs) -> ReviewRecord:
    review = ReviewRecord(**kwargs)
    db.add(review)
    return review


def create_parameter_version(db: Session, **kwargs) -> ParameterVersion:
    version = ParameterVersion(**kwargs)
    db.add(version)
    return version


def get_parameter_versions(db: Session, container_id: int) -> list:
    return db.query(ParameterVersion).filter(
        ParameterVersion.container_id == container_id
    ).order_by(ParameterVersion.version_number.desc()).all()
