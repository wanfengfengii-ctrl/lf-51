from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import List, Optional
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
    pass


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
