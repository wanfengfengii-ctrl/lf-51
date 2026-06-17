from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..repositories import calibration_repo, series_repo, multi_calibration_repo
from ..exceptions import NotFoundError
from .. import models, physics


def export_calibration_json(db: Session, calibration_id: int) -> Tuple[dict, str, str]:
    calibration = calibration_repo.get_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("校准记录不存在")

    container = calibration.container
    experiment = calibration.experiment
    candidates = calibration_repo.get_candidates_by_calibration(db, calibration_id)

    export_data = {
        "calibration": {
            "id": calibration.id,
            "name": calibration.name,
            "created_at": calibration.created_at.isoformat() if calibration.created_at else None,
            "status": calibration.status,
            "notes": calibration.notes,
            "calibrated_parameters": {
                "orifice_diameter": calibration.calibrated_orifice_diameter,
                "discharge_coefficient": calibration.calibrated_discharge_coefficient,
                "original_orifice_diameter": container.orifice_diameter,
                "original_discharge_coefficient": 0.6
            },
            "fit_metrics": {
                "rmse": calibration.rmse,
                "mae": calibration.mae,
                "r_squared": calibration.r_squared
            }
        },
        "container": {
            "id": container.id,
            "name": container.name,
            "shape": container.shape,
            "capacity": container.capacity,
            "initial_water_level": container.initial_water_level
        },
        "experiment": {
            "id": experiment.id,
            "name": experiment.name,
            "data_points": [{"time": dp.time_point, "level": dp.water_level} for dp in experiment.data_points]
        },
        "candidate_schemes": [{
            "rank": c.rank,
            "name": c.name,
            "scale_count": c.scale_count,
            "time_interval": c.time_interval,
            "is_recommended": c.is_recommended,
            "error_metrics": {
                "avg_error": c.avg_error,
                "max_error": c.max_error,
                "exceeds_count": c.exceeds_count
            },
            "marks": c.marks_data
        } for c in candidates]
    }

    filename = f"calibration_{calibration_id}_result.json"
    return export_data, "application/json", filename


def export_calibration_csv(db: Session, calibration_id: int) -> Tuple[str, str, str]:
    calibration = calibration_repo.get_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("校准记录不存在")

    recommended = db.query(models.CandidateScheme).filter(
        models.CandidateScheme.calibration_id == calibration_id,
        models.CandidateScheme.is_recommended == True
    ).first()

    if not recommended:
        raise NotFoundError("没有找到推荐方案")

    csv_lines = [
        "刻度序号,理论时间(秒),估计时间(秒),水位(cm),误差(秒),是否超阈值",
    ]

    for mark in recommended.marks_data:
        csv_lines.append(
            f"{mark['scale_index']},{mark['theoretical_time']:.2f},{mark['estimated_time']:.2f},"
            f"{mark['water_level']:.4f},{mark['error']:.4f},{'是' if mark['exceeds_threshold'] else '否'}"
        )

    csv_content = "\n".join(csv_lines)
    filename = f"calibration_{calibration_id}_scale_marks.csv"
    return csv_content, "text/csv; charset=utf-8", filename


def export_series_scheme_json(db: Session, scheme_id: int, dynasty: str = "modern") -> Tuple[dict, str, str]:
    scheme = series_repo.get_series_time_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("计时方案不存在")
    system = scheme.system
    from .series_service import _stage_to_dict
    stages = [_stage_to_dict(s) for s in sorted(system.stages, key=lambda x: x.stage_order)]
    export_data = physics.generate_dynasty_export(
        {
            "marks": scheme.marks,
            "total_duration": scheme.total_duration,
            "total_error": scheme.total_error,
            "avg_error": scheme.avg_error,
            "max_error": scheme.max_error
        },
        {"name": system.name, "dynasty": system.dynasty},
        stages,
        dynasty
    )
    export_data["generated_at"] = scheme.created_at.isoformat() if scheme.created_at else None
    filename = f"series_{scheme_id}_{dynasty}_scale.json"
    return export_data, "application/json", filename


def export_series_scheme_csv(db: Session, scheme_id: int, dynasty: str = "modern") -> Tuple[str, str, str]:
    scheme = series_repo.get_series_time_scheme_by_id(db, scheme_id)
    if not scheme:
        raise NotFoundError("计时方案不存在")

    fmt = physics.DYNASTY_FORMATS.get(dynasty, physics.DYNASTY_FORMATS["modern"])
    csv_lines = [
        f"朝代制式,{fmt['name']}",
        f"方案名称,{scheme.name}",
        f"总时长(小时),{scheme.total_duration / 3600:.3f}",
        f"累计误差(秒),{scheme.total_error:.3f}",
        f"平均误差(秒),{scheme.avg_error:.3f}",
        f"最大误差(秒),{scheme.max_error:.3f}",
        "",
        "时辰序号,时辰名称,对应现代时段,理论时间(秒),估计时间(秒),水位,误差(秒),是否超阈值,每时辰刻度数,刻度单位"
    ]
    for m in scheme.marks:
        hrs = m.get("shichen_hours", (0, 0))
        hr_str = f"{hrs[0]:02d}:00-{hrs[1]:02d}:00" if isinstance(hrs, (list, tuple)) else ""
        csv_lines.append(
            f"{m['scale_index']},{m.get('shichen_name','')},{hr_str},"
            f"{m['theoretical_time']:.2f},{m['estimated_time']:.2f},"
            f"{m['water_level']:.4f},{m['error']:.3f},"
            f"{'是' if m.get('exceeds_threshold') else '否'},"
            f"{m.get('subdivision_count', fmt['subdivisions'])},{m.get('subdivision_unit', fmt['unit'])}"
        )
    csv_content = "\n".join(csv_lines)
    filename = f"series_{scheme_id}_{dynasty}_scale.csv"
    return csv_content, "text/csv; charset=utf-8", filename


def export_multi_calibration_json(db: Session, calibration_id: int, report_type: str = "full") -> Tuple[dict, str, str]:
    calibration = multi_calibration_repo.get_multi_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("多源校准记录不存在")

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
            "experiment_id": fr.experiment_id,
            "experiment_name": fr.experiment.name if fr.experiment else "",
            "calibrated_orifice_diameter": fr.calibrated_orifice_diameter,
            "calibrated_discharge_coefficient": fr.calibrated_discharge_coefficient,
            "rmse": fr.rmse,
            "mae": fr.mae,
            "r_squared": fr.r_squared
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "conclusion": ca.conclusion
        }

    candidate_schemes = []
    for cs in calibration.candidate_schemes:
        expert_scores = []
        for s in cs.expert_scores:
            expert_scores.append({
                "expert_name": s.expert_name,
                "accuracy_score": s.accuracy_score,
                "feasibility_score": s.feasibility_score,
                "historical_consistency_score": s.historical_consistency_score,
                "overall_score": s.overall_score,
                "comments": s.comments
            })
        candidate_schemes.append({
            "id": cs.id,
            "name": cs.name,
            "scale_count": cs.scale_count,
            "time_interval": cs.time_interval,
            "avg_error": cs.avg_error,
            "max_error": cs.max_error,
            "overall_score": cs.overall_score,
            "rank": cs.rank,
            "is_eliminated": cs.is_eliminated,
            "is_final": cs.is_final,
            "expert_scores": expert_scores
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "version_number": vr.version_number,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by
        })

    cal_dict = {
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "notes": calibration.notes
    }

    export_data = physics.generate_review_report_content(
        cal_dict,
        experiments,
        fitting_results,
        consistency,
        candidate_schemes,
        expert_reviews,
        scheme_eliminations,
        version_records,
        report_type
    )
    export_data["exported_at"] = calibration.updated_at.isoformat() if calibration.updated_at else None

    filename = f"multi_calibration_{calibration_id}_{report_type}.json"
    return export_data, "application/json", filename


def export_multi_calibration_csv(db: Session, calibration_id: int) -> Tuple[str, str, str]:
    calibration = multi_calibration_repo.get_multi_calibration_by_id(db, calibration_id)
    if not calibration:
        raise NotFoundError("多源校准记录不存在")

    final_scheme = None
    for cs in calibration.candidate_schemes:
        if cs.is_final:
            final_scheme = cs
            break

    if not final_scheme and calibration.candidate_schemes:
        final_scheme = calibration.candidate_schemes[0]

    if not final_scheme:
        raise NotFoundError("没有找到刻度方案")

    csv_lines = [
        f"校准名称,{calibration.name}",
        f"校准方法,{calibration.calibration_method}",
        f"状态,{calibration.status}",
        f"是否锁定,{'是' if calibration.is_locked else '否'}",
        f"锁定人,{calibration.locked_by or ''}",
        "",
        "=== 联合校准参数 ===",
        f"联合校准孔径,{final_scheme.combined_orifice_diameter}",
        f"联合校准流量系数,{final_scheme.combined_discharge_coefficient}",
        "",
        "=== 最终刻度方案 ===",
        f"方案名称,{final_scheme.name}",
        f"刻度数量,{final_scheme.scale_count}",
        f"时间间隔(秒),{final_scheme.time_interval}",
        f"误差阈值(秒),{final_scheme.error_threshold}",
        f"平均误差(秒),{final_scheme.avg_error:.4f}",
        f"最大误差(秒),{final_scheme.max_error:.4f}",
        f"超阈值数量,{final_scheme.exceeds_count}",
        f"综合评分,{final_scheme.overall_score:.2f}",
        "",
        "刻度序号,理论时间(秒),估计时间(秒),水位(cm),误差(秒),是否超阈值"
    ]

    for mark in final_scheme.marks_data:
        csv_lines.append(
            f"{mark['scale_index']},{mark['theoretical_time']:.2f},{mark['estimated_time']:.2f},"
            f"{mark['water_level']:.4f},{mark['error']:.4f},{'是' if mark['exceeds_threshold'] else '否'}"
        )

    if calibration.expert_reviews:
        csv_lines.append("")
        csv_lines.append("=== 专家评审 ===")
        csv_lines.append("专家姓名,评审结果,总体意见,建议")
        for er in calibration.expert_reviews:
            comments = (er.overall_comments or "").replace(",", "，").replace("\n", " ")
            recs = (er.recommendations or "").replace(",", "，").replace("\n", " ")
            csv_lines.append(f"{er.expert_name},{er.review_result},{comments},{recs}")

    csv_content = "\n".join(csv_lines)
    filename = f"multi_calibration_{calibration_id}_report.csv"
    return csv_content, "text/csv; charset=utf-8", filename
