from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from ..database import get_db
from ..services import multi_calibration_service, container_service
from ..repositories import multi_calibration_repo, experiment_repo, container_repo
from ..exceptions import NotFoundError, ValidationError, BusinessRuleError
from .. import models, schemas, physics

from fastapi.templating import Jinja2Templates
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()


@router.get("/containers/{container_id}/multi_calibrations", response_class=HTMLResponse)
def list_multi_calibrations(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    calibrations = multi_calibration_repo.get_multi_calibrations_by_container(db, container_id)
    return templates.TemplateResponse("multi_calibration_list.html", {"request": request, "container": container, "calibrations": calibrations})


@router.get("/containers/{container_id}/multi_calibrations/new", response_class=HTMLResponse)
def new_multi_calibration_form(request: Request, container_id: int, db: Session = Depends(get_db)):
    container = container_service.get_container_or_404(db, container_id)
    experiments = experiment_repo.get_experiments_by_container(db, container_id)
    return templates.TemplateResponse("multi_calibration_form.html", {"request": request, "container": container, "experiments": experiments, "calibration": None, "form_data": None})


@router.get("/containers/{container_id}/multi_calibrations/{calibration_id}", response_class=HTMLResponse)
def view_multi_calibration(request: Request, container_id: int, calibration_id: int, db: Session = Depends(get_db)):
    ctx = multi_calibration_service.build_multi_calibration_template_context(db, container_id, calibration_id)
    return templates.TemplateResponse("multi_calibration_detail.html", {
        "request": request,
        "container": ctx["container"],
        "calibration": ctx["calibration"],
        "experiments": ctx["experiments"],
        "fitting_results": ctx["fitting_results"],
        "consistency_analysis": ctx["consistency_analysis"],
        "candidate_schemes": ctx["candidate_schemes"],
        "expert_reviews": ctx["expert_reviews"],
        "scheme_eliminations": ctx["scheme_eliminations"],
        "elim_lookup": ctx["elim_lookup"],
        "version_records": ctx["version_records"],
        "review_reports": ctx["review_reports"],
    })


@router.post("/api/multi_calibrations", response_model=schemas.MultiSourceCalibrationResponse)
def api_create_multi_calibration(data: schemas.MultiSourceCalibrationCreate, db: Session = Depends(get_db)):
    db_calibration = multi_calibration_service.create_multi_calibration(db, data)
    return db_calibration


@router.post("/api/multi_calibrations/{calibration_id}/run")
def api_run_multi_calibration(calibration_id: int, db: Session = Depends(get_db)):
    return multi_calibration_service.run_multi_calibration(db, calibration_id)


@router.post("/api/multi_calibrations/{calibration_id}/generate_candidates")
def api_generate_multi_candidates(calibration_id: int, data: schemas.MultiSourceCalibrationCreate, db: Session = Depends(get_db)):
    return multi_calibration_service.generate_multi_candidates(db, calibration_id, data)


@router.get("/api/multi_calibrations/{calibration_id}/detail")
def api_get_multi_calibration_detail(calibration_id: int, db: Session = Depends(get_db)):
    return multi_calibration_service.get_calibration_detail_dict(db, calibration_id)


@router.post("/api/expert_scores")
def api_create_expert_score(data: schemas.ExpertScoreCreate, db: Session = Depends(get_db)):
    return multi_calibration_service.create_expert_score(db, data)


@router.get("/api/multi_candidates/{candidate_id}/expert_scores")
def api_get_candidate_expert_scores(candidate_id: int, db: Session = Depends(get_db)):
    candidate = multi_calibration_service.get_multi_candidate_or_404(db, candidate_id)
    scores = [{"id": s.id, "expert_name": s.expert_name, "accuracy_score": s.accuracy_score, "feasibility_score": s.feasibility_score, "historical_consistency_score": s.historical_consistency_score, "overall_score": s.overall_score, "comments": s.comments, "scored_at": s.scored_at.isoformat() if s.scored_at else None} for s in candidate.expert_scores]
    return {"scores": scores, "summary": physics.aggregate_expert_scores(scores)}


@router.post("/api/multi_calibrations/{calibration_id}/expert_reviews")
def api_create_expert_review(calibration_id: int, data: schemas.ExpertReviewCreate, db: Session = Depends(get_db)):
    return multi_calibration_service.create_expert_review(db, calibration_id, data)


@router.post("/api/scheme_eliminations")
def api_eliminate_scheme(data: schemas.SchemeEliminationCreate, db: Session = Depends(get_db)):
    return multi_calibration_service.eliminate_scheme(db, data)


@router.post("/api/multi_calibrations/{calibration_id}/finalize")
def api_finalize_scheme(calibration_id: int, data: schemas.FinalizeSchemeRequest, db: Session = Depends(get_db)):
    return multi_calibration_service.finalize_scheme(db, calibration_id, data)


@router.post("/api/multi_calibrations/{calibration_id}/versions")
def api_create_version_record(calibration_id: int, data: Dict[str, Any], db: Session = Depends(get_db)):
    return multi_calibration_service.create_version_record(db, calibration_id, data)


@router.post("/api/versions/compare")
def api_compare_versions(data: schemas.VersionCompareRequest, db: Session = Depends(get_db)):
    v1 = db.query(models.SchemeVersionRecord).filter(models.SchemeVersionRecord.id == data.version1_id).first()
    v2 = db.query(models.SchemeVersionRecord).filter(models.SchemeVersionRecord.id == data.version2_id).first()
    if not v1 or not v2:
        raise NotFoundError("版本记录不存在")
    compare_result = physics.compare_versions(v1.version_data or {}, v2.version_data or {})
    return {
        "version1": {
            "id": v1.id,
            "version_number": v1.version_number,
            "change_description": v1.change_description,
            "changed_by": v1.changed_by,
            "created_at": v1.created_at.isoformat() if v1.created_at else None,
            "version_data": v1.version_data or {},
        },
        "version2": {
            "id": v2.id,
            "version_number": v2.version_number,
            "change_description": v2.change_description,
            "changed_by": v2.changed_by,
            "created_at": v2.created_at.isoformat() if v2.created_at else None,
            "version_data": v2.version_data or {},
        },
        "differences": compare_result["differences"],
        "similarity_score": compare_result["similarity_score"],
        "change_count": compare_result["change_count"],
    }


@router.get("/api/multi_calibrations/{calibration_id}/versions")
def api_get_calibration_versions(calibration_id: int, db: Session = Depends(get_db)):
    calibration = multi_calibration_service.get_multi_calibration_or_404(db, calibration_id)
    versions = []
    for vr in calibration.version_records:
        versions.append({
            "id": vr.id,
            "version_number": vr.version_number,
            "parent_version_id": vr.parent_version_id,
            "candidate_scheme_id": vr.candidate_scheme_id,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "version_data": vr.version_data,
            "created_at": vr.created_at.isoformat() if vr.created_at else None,
        })
    versions.sort(key=lambda x: x["version_number"])
    return {"versions": versions}


@router.post("/api/multi_calibrations/{calibration_id}/reports")
def api_generate_review_report(calibration_id: int, data: schemas.ReviewReportGenerateRequest, db: Session = Depends(get_db)):
    calibration = multi_calibration_service.get_multi_calibration_or_404(db, calibration_id)

    experiments = []
    for assoc in calibration.experiment_assocs:
        exp = assoc.experiment
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "weight": assoc.weight,
            "is_included": assoc.is_included,
            "data_point_count": len(exp.data_points),
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
        })

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "parameter_consistency": ca.parameter_consistency,
            "metric_consistency": ca.metric_consistency,
            "outlier_experiments": ca.outlier_experiments,
            "conclusion": ca.conclusion,
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
                "comments": s.comments,
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
        })

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result,
            "overall_comments": er.overall_comments,
            "recommendations": er.recommendations,
            "reviewed_at": er.reviewed_at.isoformat() if er.reviewed_at else None,
        })

    scheme_eliminations = []
    for se in calibration.scheme_eliminations:
        scheme_eliminations.append({
            "candidate_scheme_id": se.candidate_scheme_id,
            "candidate_scheme_name": se.candidate_scheme.name if se.candidate_scheme else "",
            "eliminated_by": se.eliminated_by,
            "elimination_reason": se.elimination_reason,
            "elimination_criteria": se.elimination_criteria,
            "eliminated_at": se.eliminated_at.isoformat() if se.eliminated_at else None,
        })

    version_records = []
    for vr in calibration.version_records:
        version_records.append({
            "version_number": vr.version_number,
            "change_description": vr.change_description,
            "changed_by": vr.changed_by,
            "created_at": vr.created_at.isoformat() if vr.created_at else None,
        })

    cal_dict = {
        "id": calibration.id,
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "notes": calibration.notes,
    }

    report_content = physics.generate_review_report_content(
        cal_dict,
        experiments,
        fitting_results,
        consistency,
        candidate_schemes,
        expert_reviews,
        scheme_eliminations,
        version_records,
        data.report_type,
    )

    db_report = models.ReviewReport(
        calibration_id=calibration_id,
        report_type=data.report_type,
        report_format=data.report_format,
        report_content=report_content,
        generated_by=data.generated_by,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return {
        "success": True,
        "report_id": db_report.id,
        "report_type": data.report_type,
        "report_format": data.report_format,
        "report_content": report_content,
    }


@router.get("/api/review_reports/{report_id}")
def api_get_review_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.ReviewReport).filter(models.ReviewReport.id == report_id).first()
    if not report:
        raise NotFoundError("评审报告不存在")
    return {
        "id": report.id,
        "calibration_id": report.calibration_id,
        "report_type": report.report_type,
        "report_format": report.report_format,
        "report_content": report.report_content,
        "generated_by": report.generated_by,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/api/multi_calibrations/{calibration_id}/institutional_conclusion")
def api_get_institutional_conclusion(calibration_id: int, db: Session = Depends(get_db)):
    calibration = multi_calibration_service.get_multi_calibration_or_404(db, calibration_id)

    consistency_score = None
    if calibration.consistency_analysis:
        consistency_score = calibration.consistency_analysis.overall_consistency_score

    approved_count = sum(1 for er in calibration.expert_reviews if er.review_result == "approved")

    summary = {
        "name": calibration.name,
        "calibration_method": calibration.calibration_method,
        "status": calibration.status,
        "is_locked": calibration.is_locked,
        "experiment_count": len(calibration.experiment_assocs),
        "fitting_result_count": len(calibration.fitting_results),
        "total_candidate_schemes": len(calibration.candidate_schemes),
        "active_schemes": sum(1 for cs in calibration.candidate_schemes if not cs.is_eliminated),
        "eliminated_schemes": sum(1 for cs in calibration.candidate_schemes if cs.is_eliminated),
        "expert_review_count": len(calibration.expert_reviews),
        "approved_reviews": approved_count,
        "rejected_reviews": sum(1 for er in calibration.expert_reviews if er.review_result == "rejected"),
        "version_count": len(calibration.version_records),
        "has_final_scheme": any(cs.is_final for cs in calibration.candidate_schemes),
        "consistency_score": consistency_score,
    }

    consistency = None
    if calibration.consistency_analysis:
        ca = calibration.consistency_analysis
        consistency = {
            "overall_consistency_score": ca.overall_consistency_score,
            "conclusion": ca.conclusion,
        }

    expert_reviews = []
    for er in calibration.expert_reviews:
        expert_reviews.append({
            "expert_name": er.expert_name,
            "review_result": er.review_result,
        })

    final_scheme = None
    for cs in calibration.candidate_schemes:
        if cs.is_final:
            final_scheme = {
                "id": cs.id,
                "name": cs.name,
                "scale_count": cs.scale_count,
                "avg_error": cs.avg_error,
                "overall_score": cs.overall_score,
            }
            break

    return physics.generate_institutional_review_conclusion(summary, consistency, expert_reviews, final_scheme)


@router.get("/api/multi_candidates/{candidate_id}/marks")
def api_multi_candidate_marks(candidate_id: int, db: Session = Depends(get_db)):
    candidate = multi_calibration_service.get_multi_candidate_or_404(db, candidate_id)
    return {
        "marks": candidate.marks_data,
        "error_threshold": candidate.error_threshold,
        "scheme_name": candidate.name,
        "scale_count": candidate.scale_count,
        "time_interval": candidate.time_interval,
    }


@router.post("/api/multi_calibrations/{calibration_id}/delete")
def api_delete_multi_calibration(calibration_id: int, db: Session = Depends(get_db)):
    container_id = multi_calibration_service.delete_multi_calibration(db, calibration_id)
    return {"success": True, "container_id": container_id}
