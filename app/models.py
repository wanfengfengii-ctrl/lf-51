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
