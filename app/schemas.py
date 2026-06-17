from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import List, Optional, Dict, Any
from datetime import datetime


class ContainerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    shape: str = Field(..., min_length=1, max_length=50)
    capacity: float = Field(..., gt=0)
    orifice_diameter: float = Field(..., gt=0)
    initial_water_level: float = Field(..., gt=0)
    shape_params: Optional[str] = None
    description: Optional[str] = None

    @field_validator('initial_water_level')
    @classmethod
    def initial_water_not_exceed_capacity(cls, v: float, info: ValidationInfo) -> float:
        capacity = info.data.get('capacity')
        if capacity is not None and v > capacity:
            raise ValueError('初始水位不能超过容器容量')
        return v


class ContainerCreate(ContainerBase):
    pass


class ContainerUpdate(ContainerBase):
    change_reason: Optional[str] = None
    changed_by: Optional[str] = None


class ContainerResponse(ContainerBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataPointBase(BaseModel):
    time_point: float
    water_level: float

    @field_validator('water_level')
    @classmethod
    def water_level_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('水位必须大于0')
        return v


class DataPointCreate(DataPointBase):
    pass


class ExperimentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None


class ExperimentCreate(ExperimentBase):
    data_points: List[DataPointCreate] = []


class ExperimentResponse(ExperimentBase):
    id: int
    container_id: int
    created_at: Optional[datetime] = None
    data_points: List[DataPointBase] = []

    class Config:
        from_attributes = True


class ScaleMarkBase(BaseModel):
    scale_index: int
    theoretical_time: float
    estimated_time: float
    water_level: float
    error: float
    exceeds_threshold: bool = False


class ScaleSchemeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scale_count: int = Field(..., gt=0)
    time_interval: float = Field(..., gt=0)
    error_threshold: float = Field(5.0, gt=0)
    description: Optional[str] = None


class ScaleSchemeCreate(ScaleSchemeBase):
    pass


class ScaleSchemeResponse(ScaleSchemeBase):
    id: int
    container_id: int
    needs_review: bool = False
    created_at: Optional[datetime] = None
    scale_marks: List[ScaleMarkBase] = []

    class Config:
        from_attributes = True


class CalibrationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    experiment_id: int = Field(..., gt=0)
    notes: Optional[str] = None


class CalibrationCreate(CalibrationBase):
    candidate_count: int = Field(5, gt=0, le=20)
    min_scale_count: int = Field(10, gt=0)
    max_scale_count: int = Field(50, gt=0)
    error_threshold: float = Field(5.0, gt=0)


class CalibrationResponse(CalibrationBase):
    id: int
    container_id: int
    calibrated_orifice_diameter: float
    calibrated_discharge_coefficient: float
    calibrated_shape_params: Optional[str] = None
    rmse: float
    mae: float
    r_squared: float
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CandidateSchemeResponse(BaseModel):
    id: int
    calibration_id: int
    name: str
    scale_count: int
    time_interval: float
    error_threshold: float
    avg_error: float
    max_error: float
    exceeds_count: int
    rank: int
    is_recommended: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ParameterVersionResponse(BaseModel):
    id: int
    container_id: int
    version_number: int
    old_shape: Optional[str] = None
    new_shape: Optional[str] = None
    old_capacity: Optional[float] = None
    new_capacity: Optional[float] = None
    old_orifice_diameter: Optional[float] = None
    new_orifice_diameter: Optional[float] = None
    old_initial_water_level: Optional[float] = None
    new_initial_water_level: Optional[float] = None
    old_shape_params: Optional[str] = None
    new_shape_params: Optional[str] = None
    change_reason: Optional[str] = None
    changed_by: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewRecordCreate(BaseModel):
    reviewer: str = Field(..., min_length=1, max_length=100)
    review_result: str = Field(..., pattern="^(approved|rejected|needs_revision)$")
    comments: Optional[str] = None


class ReviewRecordResponse(BaseModel):
    id: int
    calibration_id: int
    reviewer: str
    review_result: str
    comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FittingResultResponse(BaseModel):
    experiment_curve: List[Dict[str, float]]
    fitted_curve: List[Dict[str, float]]
    calibrated_params: Dict[str, Any]
    metrics: Dict[str, float]


class WarningSegmentResponse(BaseModel):
    scale_index: int
    start_time: float
    end_time: float
    error: float
    threshold: float
    severity: str


class RecommendationResponse(BaseModel):
    calibration: CalibrationResponse
    recommended_scheme: CandidateSchemeResponse
    alternative_schemes: List[CandidateSchemeResponse]
    fitting_result: FittingResultResponse
    warning_segments: List[WarningSegmentResponse]
    parameter_versions: List[ParameterVersionResponse]
    review_records: List[ReviewRecordResponse]
    error_comparison: List[Dict[str, Any]]


class SeriesStageBase(BaseModel):
    container_id: int = Field(..., gt=0)
    stage_order: int = Field(..., ge=0)
    stage_name: Optional[str] = None
    is_refill_enabled: bool = False
    refill_trigger_level: Optional[float] = None
    refill_target_level: Optional[float] = None
    orifice_diameter_override: Optional[float] = None
    initial_level_override: Optional[float] = None
    discharge_coefficient: float = Field(0.6, gt=0, le=1)


class SeriesStageCreate(SeriesStageBase):
    pass


class SeriesStageResponse(SeriesStageBase):
    id: int
    container_name: Optional[str] = None
    container_shape: Optional[str] = None
    container_capacity: Optional[float] = None
    container_orifice_diameter: Optional[float] = None
    container_initial_water_level: Optional[float] = None

    class Config:
        from_attributes = True


class SeriesSystemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dynasty: Optional[str] = None
    description: Optional[str] = None
    enable_temp_effect: bool = True
    base_temperature: float = Field(20.0)


class SeriesSystemCreate(SeriesSystemBase):
    stages: List[SeriesStageCreate] = []


class SeriesSystemUpdate(SeriesSystemBase):
    stages: List[SeriesStageCreate] = []


class SeriesSystemResponse(SeriesSystemBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    stages: List[SeriesStageResponse] = []
    stage_count: int = 0

    class Config:
        from_attributes = True


class SeriesTimeSchemeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    shichen_count: int = Field(12, gt=0)
    dynasty_format: Optional[str] = None
    description: Optional[str] = None


class SeriesTimeSchemeCreate(SeriesTimeSchemeBase):
    error_threshold: float = Field(30.0, gt=0)


class SeriesTimeSchemeResponse(SeriesTimeSchemeBase):
    id: int
    system_id: int
    total_duration: float
    total_error: float
    avg_error: float
    max_error: float
    created_at: Optional[datetime] = None
    dynasty: Optional[str] = None
    subdivision_unit: Optional[str] = None
    subdivisions_per_shichen: Optional[int] = None

    class Config:
        from_attributes = True


class SeriesSimulationResponse(BaseModel):
    stage_curves: List[List[Dict[str, float]]]
    temp_curve: List[Dict[str, float]]
    total_duration: float
    final_levels: List[float]
    error_threshold: float
    shichen_count: int
    dynasty_format: str
    marks: List[Dict[str, Any]]
    error_curve: List[Dict[str, float]]
    total_error: float
    avg_error: float
    max_error: float
    warning_segments: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]


class SeriesSimulationRequest(BaseModel):
    error_threshold: float = Field(30.0, gt=0)
    shichen_count: int = Field(12, gt=0, le=24)
    dynasty_format: str = "modern"
    temp_amplitude: float = 8.0
