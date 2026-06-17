from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    shape = Column(String(50), nullable=False)
    capacity = Column(Float, nullable=False)
    orifice_diameter = Column(Float, nullable=False)
    initial_water_level = Column(Float, nullable=False)
    shape_params = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    experiments = relationship("Experiment", back_populates="container", cascade="all, delete-orphan")
    scale_schemes = relationship("ScaleScheme", back_populates="container", cascade="all, delete-orphan")
    calibration_records = relationship("CalibrationRecord", back_populates="container", cascade="all, delete-orphan")
    parameter_versions = relationship("ParameterVersion", back_populates="container", cascade="all, delete-orphan")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    name = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="experiments")
    data_points = relationship("ExperimentDataPoint", back_populates="experiment", cascade="all, delete-orphan", order_by="ExperimentDataPoint.time_point")
    calibration_records = relationship("CalibrationRecord", back_populates="experiment")


class ExperimentDataPoint(Base):
    __tablename__ = "experiment_data_points"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    time_point = Column(Float, nullable=False)
    water_level = Column(Float, nullable=False)

    experiment = relationship("Experiment", back_populates="data_points")


class ScaleScheme(Base):
    __tablename__ = "scale_schemes"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    calibration_id = Column(Integer, ForeignKey("calibration_records.id"), nullable=True)
    name = Column(String(200), nullable=False)
    scale_count = Column(Integer, nullable=False)
    time_interval = Column(Float, nullable=False)
    error_threshold = Column(Float, nullable=False, default=5.0)
    needs_review = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="scale_schemes")
    scale_marks = relationship("ScaleMark", back_populates="scheme", cascade="all, delete-orphan", order_by="ScaleMark.scale_index")
    calibration = relationship("CalibrationRecord", back_populates="schemes")


class ScaleMark(Base):
    __tablename__ = "scale_marks"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("scale_schemes.id"), nullable=False)
    scale_index = Column(Integer, nullable=False)
    theoretical_time = Column(Float, nullable=False)
    estimated_time = Column(Float, nullable=False)
    water_level = Column(Float, nullable=False)
    error = Column(Float, nullable=False)
    exceeds_threshold = Column(Boolean, nullable=False, default=False)

    scheme = relationship("ScaleScheme", back_populates="scale_marks")


class CalibrationRecord(Base):
    __tablename__ = "calibration_records"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    name = Column(String(200), nullable=False)
    calibrated_orifice_diameter = Column(Float, nullable=False)
    calibrated_discharge_coefficient = Column(Float, nullable=False)
    calibrated_shape_params = Column(Text, nullable=True)
    rmse = Column(Float, nullable=False)
    mae = Column(Float, nullable=False)
    r_squared = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="calibration_records")
    experiment = relationship("Experiment", back_populates="calibration_records")
    schemes = relationship("ScaleScheme", back_populates="calibration")
    candidate_schemes = relationship("CandidateScheme", back_populates="calibration", cascade="all, delete-orphan")
    review_records = relationship("ReviewRecord", back_populates="calibration", cascade="all, delete-orphan")


class CandidateScheme(Base):
    __tablename__ = "candidate_schemes"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("calibration_records.id"), nullable=False)
    name = Column(String(200), nullable=False)
    scale_count = Column(Integer, nullable=False)
    time_interval = Column(Float, nullable=False)
    error_threshold = Column(Float, nullable=False)
    avg_error = Column(Float, nullable=False)
    max_error = Column(Float, nullable=False)
    exceeds_count = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)
    marks_data = Column(JSON, nullable=False)
    is_recommended = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("CalibrationRecord", back_populates="candidate_schemes")


class ParameterVersion(Base):
    __tablename__ = "parameter_versions"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    old_shape = Column(String(50), nullable=True)
    new_shape = Column(String(50), nullable=True)
    old_capacity = Column(Float, nullable=True)
    new_capacity = Column(Float, nullable=True)
    old_orifice_diameter = Column(Float, nullable=True)
    new_orifice_diameter = Column(Float, nullable=True)
    old_initial_water_level = Column(Float, nullable=True)
    new_initial_water_level = Column(Float, nullable=True)
    old_shape_params = Column(Text, nullable=True)
    new_shape_params = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=True)
    changed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="parameter_versions")


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("calibration_records.id"), nullable=False)
    reviewer = Column(String(100), nullable=False)
    review_result = Column(String(20), nullable=False)
    comments = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("CalibrationRecord", back_populates="review_records")


class SeriesSystem(Base):
    __tablename__ = "series_systems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    dynasty = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    temperature_profile = Column(JSON, nullable=True)
    enable_temp_effect = Column(Boolean, nullable=False, default=True)
    base_temperature = Column(Float, nullable=False, default=20.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    stages = relationship("SeriesStage", back_populates="system", cascade="all, delete-orphan", order_by="SeriesStage.stage_order")
    time_schemes = relationship("SeriesTimeScheme", back_populates="system", cascade="all, delete-orphan")


class SeriesStage(Base):
    __tablename__ = "series_stages"

    id = Column(Integer, primary_key=True, index=True)
    system_id = Column(Integer, ForeignKey("series_systems.id"), nullable=False)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    stage_order = Column(Integer, nullable=False)
    stage_name = Column(String(100), nullable=True)
    is_refill_enabled = Column(Boolean, nullable=False, default=False)
    refill_trigger_level = Column(Float, nullable=True)
    refill_target_level = Column(Float, nullable=True)
    orifice_diameter_override = Column(Float, nullable=True)
    initial_level_override = Column(Float, nullable=True)
    discharge_coefficient = Column(Float, nullable=False, default=0.6)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    system = relationship("SeriesSystem", back_populates="stages")
    container = relationship("Container")


class SeriesTimeScheme(Base):
    __tablename__ = "series_time_schemes"

    id = Column(Integer, primary_key=True, index=True)
    system_id = Column(Integer, ForeignKey("series_systems.id"), nullable=False)
    name = Column(String(200), nullable=False)
    shichen_count = Column(Integer, nullable=False, default=12)
    dynasty_format = Column(String(50), nullable=True)
    error_threshold = Column(Float, nullable=False, default=30.0)
    total_duration = Column(Float, nullable=False)
    total_error = Column(Float, nullable=False, default=0.0)
    avg_error = Column(Float, nullable=False, default=0.0)
    max_error = Column(Float, nullable=False, default=0.0)
    marks = Column(JSON, nullable=False)
    stage_curves = Column(JSON, nullable=True)
    error_curve = Column(JSON, nullable=True)
    warning_segments = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    temp_curve = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    system = relationship("SeriesSystem", back_populates="time_schemes")


class ExperimentCondition(Base):
    __tablename__ = "experiment_conditions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    condition_type = Column(String(50), nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    water_quality = Column(String(100), nullable=True)
    measurement_method = Column(String(200), nullable=True)
    instrument_accuracy = Column(Float, nullable=True)
    operator = Column(String(100), nullable=True)
    experiment_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    experiment_assocs = relationship("ExperimentConditionAssoc", back_populates="condition", cascade="all, delete-orphan")


class ExperimentConditionAssoc(Base):
    __tablename__ = "experiment_condition_assocs"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    condition_id = Column(Integer, ForeignKey("experiment_conditions.id"), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment")
    condition = relationship("ExperimentCondition", back_populates="experiment_assocs")


class MultiSourceCalibration(Base):
    __tablename__ = "multi_source_calibrations"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    system_id = Column(Integer, ForeignKey("series_systems.id"), nullable=True)
    name = Column(String(200), nullable=False)
    calibration_method = Column(String(50), nullable=False, default="weighted_average")
    status = Column(String(20), nullable=False, default="pending")
    is_locked = Column(Boolean, nullable=False, default=False)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(100), nullable=True)
    final_scheme_id = Column(Integer, ForeignKey("multi_source_candidate_schemes.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    container = relationship("Container")
    system = relationship("SeriesSystem")
    experiment_assocs = relationship("MultiSourceExperimentAssoc", back_populates="calibration", cascade="all, delete-orphan")
    fitting_results = relationship("MultiSourceFittingResult", back_populates="calibration", cascade="all, delete-orphan")
    consistency_analysis = relationship("ConsistencyAnalysis", back_populates="calibration", uselist=False, cascade="all, delete-orphan")
    candidate_schemes = relationship("MultiSourceCandidateScheme", back_populates="calibration", cascade="all, delete-orphan", foreign_keys="MultiSourceCandidateScheme.calibration_id")
    final_scheme = relationship("MultiSourceCandidateScheme", foreign_keys=[final_scheme_id], post_update=True)
    expert_reviews = relationship("ExpertReview", back_populates="calibration", cascade="all, delete-orphan")
    scheme_eliminations = relationship("SchemeElimination", back_populates="calibration", cascade="all, delete-orphan")
    version_records = relationship("SchemeVersionRecord", back_populates="calibration", cascade="all, delete-orphan")
    review_reports = relationship("ReviewReport", back_populates="calibration", cascade="all, delete-orphan")


class MultiSourceExperimentAssoc(Base):
    __tablename__ = "multi_source_experiment_assocs"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    is_included = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="experiment_assocs")
    experiment = relationship("Experiment")


class MultiSourceFittingResult(Base):
    __tablename__ = "multi_source_fitting_results"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    calibrated_orifice_diameter = Column(Float, nullable=False)
    calibrated_discharge_coefficient = Column(Float, nullable=False)
    calibrated_shape_params = Column(Text, nullable=True)
    rmse = Column(Float, nullable=False)
    mae = Column(Float, nullable=False)
    r_squared = Column(Float, nullable=False)
    fitting_curve = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="fitting_results")
    experiment = relationship("Experiment")


class ConsistencyAnalysis(Base):
    __tablename__ = "consistency_analyses"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    overall_consistency_score = Column(Float, nullable=False)
    parameter_consistency = Column(JSON, nullable=False)
    metric_consistency = Column(JSON, nullable=False)
    outlier_experiments = Column(JSON, nullable=True)
    analysis_details = Column(JSON, nullable=True)
    conclusion = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="consistency_analysis")


class MultiSourceCandidateScheme(Base):
    __tablename__ = "multi_source_candidate_schemes"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    name = Column(String(200), nullable=False)
    scale_count = Column(Integer, nullable=False)
    time_interval = Column(Float, nullable=False)
    error_threshold = Column(Float, nullable=False)
    combined_orifice_diameter = Column(Float, nullable=False)
    combined_discharge_coefficient = Column(Float, nullable=False)
    avg_error = Column(Float, nullable=False)
    max_error = Column(Float, nullable=False)
    exceeds_count = Column(Integer, nullable=False)
    overall_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    marks_data = Column(JSON, nullable=False)
    is_eliminated = Column(Boolean, nullable=False, default=False)
    elimination_reason = Column(Text, nullable=True)
    is_final = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="candidate_schemes", foreign_keys=[calibration_id])
    expert_scores = relationship("ExpertScore", back_populates="candidate_scheme", cascade="all, delete-orphan")


class ExpertScore(Base):
    __tablename__ = "expert_scores"

    id = Column(Integer, primary_key=True, index=True)
    candidate_scheme_id = Column(Integer, ForeignKey("multi_source_candidate_schemes.id"), nullable=False)
    expert_name = Column(String(100), nullable=False)
    accuracy_score = Column(Float, nullable=False)
    feasibility_score = Column(Float, nullable=False)
    historical_consistency_score = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)
    comments = Column(Text, nullable=True)
    scored_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate_scheme = relationship("MultiSourceCandidateScheme", back_populates="expert_scores")


class ExpertReview(Base):
    __tablename__ = "expert_reviews"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    expert_name = Column(String(100), nullable=False)
    review_result = Column(String(20), nullable=False)
    overall_comments = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="expert_reviews")


class SchemeElimination(Base):
    __tablename__ = "scheme_eliminations"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    candidate_scheme_id = Column(Integer, ForeignKey("multi_source_candidate_schemes.id"), nullable=False)
    eliminated_by = Column(String(100), nullable=False)
    elimination_reason = Column(Text, nullable=False)
    elimination_criteria = Column(String(200), nullable=True)
    eliminated_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="scheme_eliminations")
    candidate_scheme = relationship("MultiSourceCandidateScheme")


class SchemeVersionRecord(Base):
    __tablename__ = "scheme_version_records"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    parent_version_id = Column(Integer, ForeignKey("scheme_version_records.id"), nullable=True)
    candidate_scheme_id = Column(Integer, ForeignKey("multi_source_candidate_schemes.id"), nullable=True)
    change_description = Column(Text, nullable=False)
    changed_by = Column(String(100), nullable=False)
    version_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="version_records")
    candidate_scheme = relationship("MultiSourceCandidateScheme")
    parent_version = relationship("SchemeVersionRecord", remote_side=[id])


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(Integer, ForeignKey("multi_source_calibrations.id"), nullable=False)
    report_type = Column(String(50), nullable=False)
    report_format = Column(String(20), nullable=False, default="json")
    report_content = Column(JSON, nullable=False)
    generated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    calibration = relationship("MultiSourceCalibration", back_populates="review_reports")
