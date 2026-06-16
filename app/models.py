from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
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


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    name = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="experiments")
    data_points = relationship("ExperimentDataPoint", back_populates="experiment", cascade="all, delete-orphan", order_by="ExperimentDataPoint.time_point")


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
    name = Column(String(200), nullable=False)
    scale_count = Column(Integer, nullable=False)
    time_interval = Column(Float, nullable=False)
    error_threshold = Column(Float, nullable=False, default=5.0)
    needs_review = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    container = relationship("Container", back_populates="scale_schemes")
    scale_marks = relationship("ScaleMark", back_populates="scheme", cascade="all, delete-orphan", order_by="ScaleMark.scale_index")


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
