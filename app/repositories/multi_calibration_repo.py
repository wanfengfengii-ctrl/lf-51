from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import (
    MultiSourceCalibration,
    MultiSourceExperimentAssoc,
    MultiSourceFittingResult,
    ConsistencyAnalysis,
    MultiSourceCandidateScheme,
    ExpertScore,
    ExpertReview,
    SchemeElimination,
    SchemeVersionRecord,
    ReviewReport,
)
from typing import Optional


def get_multi_calibrations_by_container(db: Session, container_id: int) -> list:
    return db.query(MultiSourceCalibration).filter(
        MultiSourceCalibration.container_id == container_id
    ).order_by(MultiSourceCalibration.created_at.desc()).all()


def get_multi_calibration_by_id(db: Session, calibration_id: int) -> Optional[MultiSourceCalibration]:
    return db.query(MultiSourceCalibration).filter(
        MultiSourceCalibration.id == calibration_id
    ).first()


def create_multi_calibration(db: Session, **kwargs) -> MultiSourceCalibration:
    calibration = MultiSourceCalibration(**kwargs)
    db.add(calibration)
    db.flush()
    return calibration


def create_experiment_assoc(db: Session, calibration_id: int, experiment_id: int, weight: float, is_included: bool) -> MultiSourceExperimentAssoc:
    assoc = MultiSourceExperimentAssoc(
        calibration_id=calibration_id,
        experiment_id=experiment_id,
        weight=weight,
        is_included=is_included,
    )
    db.add(assoc)
    return assoc


def delete_fitting_results(db: Session, calibration: MultiSourceCalibration) -> None:
    for fr in calibration.fitting_results:
        db.delete(fr)
    db.flush()


def delete_consistency_analysis(db: Session, calibration: MultiSourceCalibration) -> None:
    if calibration.consistency_analysis:
        db.delete(calibration.consistency_analysis)
    db.flush()


def delete_candidate_schemes(db: Session, calibration: MultiSourceCalibration) -> None:
    for cs in calibration.candidate_schemes:
        db.delete(cs)
    db.flush()


def delete_scheme_eliminations(db: Session, calibration: MultiSourceCalibration) -> None:
    for se in calibration.scheme_eliminations:
        db.delete(se)
    db.flush()


def create_fitting_result(db: Session, **kwargs) -> MultiSourceFittingResult:
    fr = MultiSourceFittingResult(**kwargs)
    db.add(fr)
    return fr


def create_consistency_analysis(db: Session, **kwargs) -> ConsistencyAnalysis:
    ca = ConsistencyAnalysis(**kwargs)
    db.add(ca)
    return ca


def create_multi_candidate_scheme(db: Session, **kwargs) -> MultiSourceCandidateScheme:
    cs = MultiSourceCandidateScheme(**kwargs)
    db.add(cs)
    return cs


def create_expert_score(db: Session, **kwargs) -> ExpertScore:
    score = ExpertScore(**kwargs)
    db.add(score)
    return score


def create_expert_review(db: Session, **kwargs) -> ExpertReview:
    review = ExpertReview(**kwargs)
    db.add(review)
    return review


def create_scheme_elimination(db: Session, **kwargs) -> SchemeElimination:
    elimination = SchemeElimination(**kwargs)
    db.add(elimination)
    return elimination


def create_version_record(db: Session, **kwargs) -> SchemeVersionRecord:
    version = SchemeVersionRecord(**kwargs)
    db.add(version)
    return version


def create_review_report(db: Session, **kwargs) -> ReviewReport:
    report = ReviewReport(**kwargs)
    db.add(report)
    return report


def get_max_version_number(db: Session, calibration_id: int) -> int:
    max_version = db.query(func.max(SchemeVersionRecord.version_number)).filter(
        SchemeVersionRecord.calibration_id == calibration_id
    ).scalar() or 0
    return max_version


def delete_multi_calibration(db: Session, calibration: MultiSourceCalibration) -> None:
    db.delete(calibration)
    db.commit()
