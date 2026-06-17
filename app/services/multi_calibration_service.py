from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..repositories import multi_calibration_repo
from ..exceptions import NotFoundError, ValidationError, BusinessRuleError
from .. import models, physics


def get_multi_calibration_or_404(db: Session, calibration_id: int):
    calibration = multi_calibration_repo.get_multi_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("多源校准记录不存在")
    return calibration


def get_multi_candidate_or_404(db: Session, candidate_id: int):
    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == candidate_id
    ).first()
    if not candidate:
        raise NotFoundError("候选方案不存在")
    return candidate


def create_multi_calibration(db: Session, data) -> models.MultiSourceCalibration:
    container = db.query(models.Container).filter(models.Container.id == data.container_id).first()
    if not container:
        raise NotFoundError("容器不存在")

    if data.system_id is not None:
        system = db.query(models.SeriesSystem).filter(models.SeriesSystem.id == data.system_id).first()
        if not system:
            raise NotFoundError("串联系统不存在")

    errors = []
    if not data.experiments:
        errors.append("至少需要选择一组实验数据")
    if data.min_scale_count < 1:
        errors.append("最小刻度数必须大于0")
    if data.max_scale_count <= data.min_scale_count:
        errors.append("最大刻度数必须大于最小刻度数")
    if data.error_threshold <= 0:
        errors.append("误差阈值必须大于0")
    if errors:
        raise ValidationError(errors)

    for exp in data.experiments:
        db_exp = db.query(models.Experiment).filter(
            models.Experiment.id == exp.experiment_id,
            models.Experiment.container_id == data.container_id
        ).first()
        if not db_exp:
            raise ValidationError([f"实验 ID={exp.experiment_id} 不存在"])
        if len(db_exp.data_points) < 2:
            raise ValidationError([f"实验 '{db_exp.name}' 至少需要2个数据点"])

    db_calibration = multi_calibration_repo.create_multi_calibration(
        db,
        container_id=data.container_id,
        system_id=data.system_id,
        name=data.name,
        calibration_method=data.calibration_method,
        status="pending",
        is_locked=False,
        notes=data.notes
    )

    for exp_assoc in data.experiments:
        multi_calibration_repo.create_experiment_assoc(
            db,
            calibration_id=db_calibration.id,
            experiment_id=exp_assoc.experiment_id,
            weight=exp_assoc.weight,
            is_included=exp_assoc.is_included
        )

    db.commit()
    db.refresh(db_calibration)
    return db_calibration


def run_multi_calibration(db: Session, calibration_id: int) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)
    container = calibration.container
    if not container:
        raise NotFoundError("容器不存在")

    experiments_data = []
    for assoc in calibration.experiment_assocs:
        if not assoc.is_included:
            continue
        exp = assoc.experiment
        exp_points = [(dp.time_point, dp.water_level) for dp in exp.data_points]
        experiments_data.append({
            "experiment_id": exp.id,
            "experiment_name": exp.name,
            "points": exp_points,
            "weight": assoc.weight,
            "is_included": assoc.is_included
        })

    if not experiments_data:
        raise BusinessRuleError("没有有效的实验数据")

    try:
        result = physics.multi_source_calibrate(
            experiments_data,
            container.initial_water_level,
            container.orifice_diameter,
            container.shape,
            container.capacity,
            container.shape_params,
            calibration.calibration_method
        )
    except ValueError as e:
        raise BusinessRuleError(str(e))

    multi_calibration_repo.delete_fitting_results(db, calibration)
    multi_calibration_repo.delete_consistency_analysis(db, calibration)
    multi_calibration_repo.delete_candidate_schemes(db, calibration)

    for fr in result["fitting_results"]:
        multi_calibration_repo.create_fitting_result(
            db,
            calibration_id=calibration.id,
            experiment_id=fr["experiment_id"],
            calibrated_orifice_diameter=round(fr["calibrated_orifice_diameter"], 6),
            calibrated_discharge_coefficient=round(fr["calibrated_discharge_coefficient"], 6),
            calibrated_shape_params=container.shape_params,
            rmse=round(fr["rmse"], 6),
            mae=round(fr["mae"], 6),
            r_squared=round(fr["r_squared"], 6),
            fitting_curve=fr.get("fitting_curve")
        )

    consistency_result = physics.analyze_consistency(result["fitting_results"])
    multi_calibration_repo.create_consistency_analysis(
        db,
        calibration_id=calibration.id,
        overall_consistency_score=consistency_result["overall_consistency_score"],
        parameter_consistency=consistency_result["parameter_consistency"],
        metric_consistency=consistency_result["metric_consistency"],
        outlier_experiments=consistency_result.get("outlier_experiments"),
        analysis_details=consistency_result.get("analysis_details"),
        conclusion=consistency_result.get("conclusion")
    )

    db.commit()
    db.refresh(calibration)

    return {
        "success": True,
        "calibration_id": calibration.id,
        "combined_params": result["combined_params"],
        "parameter_statistics": result["parameter_statistics"],
        "fitting_count": len(result["fitting_results"]),
        "consistency_score": consistency_result["overall_consistency_score"]
    }


def generate_multi_candidates(db: Session, calibration_id: int, data) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)
    container = calibration.container
    if not container:
        raise NotFoundError("容器不存在")

    if not calibration.fitting_results:
        raise BusinessRuleError("请先执行联合校准")

    experiments_data = []
    for assoc in calibration.experiment_assocs:
        if not assoc.is_included:
            continue
        exp = assoc.experiment
        exp_points = [(dp.time_point, dp.water_level) for dp in exp.data_points]
        experiments_data.append({
            "experiment_id": exp.id,
            "experiment_name": exp.name,
            "points": exp_points,
            "weight": assoc.weight,
            "is_included": assoc.is_included
        })

    ms_result = physics.multi_source_calibrate(
        experiments_data,
        container.initial_water_level,
        container.orifice_diameter,
        container.shape,
        container.capacity,
        container.shape_params,
        calibration.calibration_method
    )
    combined_params = ms_result["combined_params"]

    candidates = physics.generate_multi_source_candidate_schemes(
        combined_params,
        container.initial_water_level,
        container.shape,
        container.capacity,
        container.shape_params,
        data.candidate_count,
        data.min_scale_count,
        data.max_scale_count,
        data.error_threshold
    )

    multi_calibration_repo.delete_candidate_schemes(db, calibration)
    multi_calibration_repo.delete_scheme_eliminations(db, calibration)

    for candidate in candidates:
        multi_calibration_repo.create_multi_candidate_scheme(
            db,
            calibration_id=calibration.id,
            name=candidate["name"],
            scale_count=candidate["scale_count"],
            time_interval=candidate["time_interval"],
            error_threshold=candidate["error_threshold"],
            combined_orifice_diameter=candidate["combined_orifice_diameter"],
            combined_discharge_coefficient=candidate["combined_discharge_coefficient"],
            avg_error=candidate["avg_error"],
            max_error=candidate["max_error"],
            exceeds_count=candidate["exceeds_count"],
            overall_score=candidate["overall_score"],
            rank=candidate["rank"],
            marks_data=candidate["marks"],
            is_eliminated=False,
            is_final=False
        )

    calibration.status = "candidates_generated"
    db.commit()

    return {
        "success": True,
        "calibration_id": calibration.id,
        "candidate_count": len(candidates),
        "candidates": [{
            "id": None,
            "name": c["name"],
            "scale_count": c["scale_count"],
            "time_interval": c["time_interval"],
            "avg_error": c["avg_error"],
            "max_error": c["max_error"],
            "overall_score": c["overall_score"],
            "rank": c["rank"]
        } for c in candidates]
    }


def create_expert_score(db: Session, data) -> Dict[str, Any]:
    candidate = get_multi_candidate_or_404(db, data.candidate_scheme_id)

    overall = (data.accuracy_score * 0.4 + data.feasibility_score * 0.3 +
               data.historical_consistency_score * 0.3)

    db_score = multi_calibration_repo.create_expert_score(
        db,
        candidate_scheme_id=data.candidate_scheme_id,
        expert_name=data.expert_name,
        accuracy_score=data.accuracy_score,
        feasibility_score=data.feasibility_score,
        historical_consistency_score=data.historical_consistency_score,
        overall_score=round(overall, 2),
        comments=data.comments
    )
    db.commit()
    db.refresh(db_score)

    return {
        "success": True,
        "score": {
            "id": db_score.id,
            "candidate_scheme_id": db_score.candidate_scheme_id,
            "expert_name": db_score.expert_name,
            "accuracy_score": db_score.accuracy_score,
            "feasibility_score": db_score.feasibility_score,
            "historical_consistency_score": db_score.historical_consistency_score,
            "overall_score": db_score.overall_score,
            "comments": db_score.comments,
            "scored_at": db_score.scored_at.isoformat() if db_score.scored_at else None
        }
    }


def create_expert_review(db: Session, calibration_id: int, data) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)

    db_review = multi_calibration_repo.create_expert_review(
        db,
        calibration_id=calibration_id,
        expert_name=data.expert_name,
        review_result=data.review_result,
        overall_comments=data.overall_comments,
        recommendations=data.recommendations
    )
    db.commit()
    db.refresh(db_review)

    return {
        "success": True,
        "review": {
            "id": db_review.id,
            "calibration_id": db_review.calibration_id,
            "expert_name": db_review.expert_name,
            "review_result": db_review.review_result,
            "overall_comments": db_review.overall_comments,
            "recommendations": db_review.recommendations,
            "reviewed_at": db_review.reviewed_at.isoformat() if db_review.reviewed_at else None
        }
    }


def eliminate_scheme(db: Session, data) -> Dict[str, Any]:
    candidate = get_multi_candidate_or_404(db, data.candidate_scheme_id)

    if candidate.is_final:
        raise BusinessRuleError("最终方案不能被淘汰")

    calibration_id = candidate.calibration_id

    db_elim = multi_calibration_repo.create_scheme_elimination(
        db,
        calibration_id=calibration_id,
        candidate_scheme_id=data.candidate_scheme_id,
        eliminated_by=data.eliminated_by,
        elimination_reason=data.elimination_reason,
        elimination_criteria=data.elimination_criteria
    )

    candidate.is_eliminated = True
    candidate.elimination_reason = data.elimination_reason

    db.commit()
    db.refresh(db_elim)

    return {
        "success": True,
        "elimination": {
            "id": db_elim.id,
            "candidate_scheme_id": db_elim.candidate_scheme_id,
            "candidate_scheme_name": candidate.name,
            "eliminated_by": db_elim.eliminated_by,
            "elimination_reason": db_elim.elimination_reason,
            "elimination_criteria": db_elim.elimination_criteria,
            "eliminated_at": db_elim.eliminated_at.isoformat() if db_elim.eliminated_at else None
        }
    }


def finalize_scheme(db: Session, calibration_id: int, data) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)

    if calibration.is_locked:
        raise BusinessRuleError("该校准已锁定，无法再次定稿")

    candidate = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.id == data.candidate_scheme_id,
        models.MultiSourceCandidateScheme.calibration_id == calibration_id
    ).first()
    if not candidate:
        raise NotFoundError("候选方案不存在")

    if candidate.is_eliminated:
        raise BusinessRuleError("已淘汰的方案不能作为最终方案")

    max_version = multi_calibration_repo.get_max_version_number(db, calibration_id)
    new_version_number = max_version + 1

    scheme_data = {
        "name": candidate.name,
        "scale_count": candidate.scale_count,
        "time_interval": candidate.time_interval,
        "error_threshold": candidate.error_threshold,
        "combined_orifice_diameter": candidate.combined_orifice_diameter,
        "combined_discharge_coefficient": candidate.combined_discharge_coefficient,
        "avg_error": candidate.avg_error,
        "max_error": candidate.max_error,
        "exceeds_count": candidate.exceeds_count,
        "overall_score": candidate.overall_score
    }

    multi_calibration_repo.create_version_record(
        db,
        calibration_id=calibration_id,
        version_number=new_version_number,
        parent_version_id=None,
        candidate_scheme_id=candidate.id,
        change_description=data.version_description,
        changed_by=data.locked_by,
        version_data=scheme_data
    )

    for cs in calibration.candidate_schemes:
        cs.is_final = False
    candidate.is_final = True

    calibration.final_scheme_id = candidate.id
    calibration.is_locked = True
    calibration.locked_at = func.now()
    calibration.locked_by = data.locked_by
    calibration.status = "finalized"

    db.commit()

    return {
        "success": True,
        "calibration_id": calibration.id,
        "final_scheme": {
            "id": candidate.id,
            "name": candidate.name,
            "scale_count": candidate.scale_count,
            "time_interval": candidate.time_interval,
            "avg_error": candidate.avg_error,
            "max_error": candidate.max_error,
            "overall_score": candidate.overall_score
        },
        "version_number": new_version_number,
        "locked_by": data.locked_by
    }


def create_version_record(db: Session, calibration_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)

    max_version = multi_calibration_repo.get_max_version_number(db, calibration_id)
    new_version_number = max_version + 1

    db_version = multi_calibration_repo.create_version_record(
        db,
        calibration_id=calibration_id,
        version_number=new_version_number,
        parent_version_id=data.get("parent_version_id"),
        candidate_scheme_id=data.get("candidate_scheme_id"),
        change_description=data.get("change_description", ""),
        changed_by=data.get("changed_by", "system"),
        version_data=data.get("version_data")
    )
    db.commit()
    db.refresh(db_version)

    return {
        "success": True,
        "version": {
            "id": db_version.id,
            "version_number": db_version.version_number,
            "parent_version_id": db_version.parent_version_id,
            "candidate_scheme_id": db_version.candidate_scheme_id,
            "change_description": db_version.change_description,
            "changed_by": db_version.changed_by,
            "created_at": db_version.created_at.isoformat() if db_version.created_at else None
        }
    }


def get_calibration_detail_dict(db: Session, calibration_id: int) -> Dict[str, Any]:
    calibration = get_multi_calibration_or_404(db, calibration_id)

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = []
    for fr in calibration.fitting_results:
        fitting_results.append({
            "id": fr.id,
            "experiment_id": fr.experiment_id,
            "experiment_name": fr.experiment.name if fr.experiment else "",
            "calibrated_orifice_diameter": fr.calibrated_orifice_diameter,
            "calibrated_discharge_coefficient": fr.calibrated_discharge_coefficient,
            "rmse": fr.rmse,
            "mae": fr.mae,
            "r_squared": fr.r_squared,
            "fitting_curve": fr.fitting_curve
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "id": ca.id,
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "analysis_details": ca.analysis_details,
            "conclusion": ca.conclusion
        }

    candidate_schemes = []
    for cs in calibration.candidate_schemes:
        expert_scores = []
        for s in cs.expert_scores:
            expert_scores.append({
                "id": s.id,
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments,
                "scored_at": s.scored_at.isoformat() if s.scored_at else None
            })
        candidate_schemes.append({
            "id": cs.id,
            "name": cs.name,
            "scale_count": cs.scale_count,
            "time_interval": cs.time_interval,
            "error_threshold": cs.error_threshold,
            "combined_orifice_diameter": cs.combined_orifice_diameter,
            "combined_discharge_coefficient": cs.combined_discharge_coefficient,
            "avg_error": cs.avg_error,
            "max_error": cs.max_error,
            "exceeds_count": cs.exceeds_count,
            "overall_score": cs.overall_score,
            "rank": cs.rank,
            "is_eliminated": cs.is_eliminated,
            "elimination_reason": cs.elimination_reason,
            "is_final": cs.is_final,
            "expert_scores": expert_scores,
            "expert_summary": physics.aggregate_expert_scores(expert_scores)
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "id": er.id,
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations,
            "reviewed_at": er.reviewed_at.isoformat() if er.reviewed_at else None
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "id": se.id,
            "candidate_scheme_id": se.candidate_scheme_id,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at.isoformat() if se.eliminated_at else None
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "id": vr.id,
            "version_number": vr.version_number,
            "parent_version_id": vr.parent_version_id,
            "candidate_scheme_id": vr.candidate_scheme_id,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "version_data": vr.version_data,
            "created_at": vr.created_at.isoformat() if vr.created_at else None
        })

    review_reports = []
    for rr in calibration.review_reports:
        review_reports.append({
            "id": rr.id,
            "report_type": rr.report_type,
            "report_format": rr.report_format,
            "generated_by": rr.generated_by,
            "created_at": rr.created_at.isoformat() if rr.created_at else None
        })

    return {
        "calibration": {
            "id": calibration.id,
            "container_id": calibration.container_id,
            "system_id": calibration.system_id,
            "name": calibration.name,
            "calibration_method": calibration.calibration_method,
            "status": calibration.status,
            "is_locked": calibration.is_locked,
            "locked_at": calibration.locked_at.isoformat() if calibration.locked_at else None,
            "locked_by": calibration.locked_by,
            "final_scheme_id": calibration.final_scheme_id,
            "notes": calibration.notes,
            "created_at": calibration.created_at.isoformat() if calibration.created_at else None,
            "updated_at": calibration.updated_at.isoformat() if calibration.updated_at else None
        },
        "experiments": experiments,
        "fitting_results": fitting_results,
        "consistency_analysis": consistency,
        "candidate_schemes": candidate_schemes,
        "expert_reviews": expert_reviews,
        "scheme_eliminations": scheme_eliminations,
        "version_records": version_records,
        "review_reports": review_reports
    }


def build_multi_calibration_template_context(db: Session, container_id: int, calibration_id: int) -> Dict[str, Any]:
    container = db.query(models.Container).filter(models.Container.id == container_id).first()
    if not container:
        raise NotFoundError("容器不存在")
    calibration = multi_calibration_repo.get_multi_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("资源不存在")

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points)
        })

    fitting_results = calibration.fitting_results
    consistency = calibration.consistency_analysis

    candidate_schemes = db.query(models.MultiSourceCandidateScheme).filter(
        models.MultiSourceCandidateScheme.calibration_id == calibration_id
    ).order_by(models.MultiSourceCandidateScheme.rank).all()

    expert_reviews = calibration.expert_reviews
    scheme_eliminations = calibration.scheme_eliminations
    version_records = calibration.version_records
    review_reports = calibration.review_reports

    for cs in candidate_schemes:
        scores_list = []
        for s in cs.expert_scores:
            scores_list.append({
                "id": s.id,
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments,
                "scored_at": s.scored_at
            })
        cs._expert_scores_list = scores_list

    elim_lookup = {}
    for se in scheme_eliminations:
        elim_lookup[se.candidate_scheme_id] = {
            "id": se.id,
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else ""
        }

    return {
        "container": container,
        "calibration": calibration,
        "experiments": experiments,
        "fitting_results": fitting_results,
        "consistency_analysis": consistency,
        "candidate_schemes": candidate_schemes,
        "expert_reviews": expert_reviews,
        "scheme_eliminations": scheme_eliminations,
        "elim_lookup": elim_lookup,
        "version_records": version_records,
        "review_reports": review_reports
    }


def delete_multi_calibration(db: Session, calibration_id: int) -> int:
    calibration = get_multi_calibration_or_404(db, calibration_id)
    container_id = calibration.container_id
    multi_calibration_repo.delete_multi_calibration(db, calibration)
    return container_id
