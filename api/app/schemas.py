from pydantic import BaseModel, ConfigDict, Field


class PresetOut(BaseModel):
    id: str
    category: str
    label: str
    width_px: int
    height_px: int
    dpi: int
    cm_width: float
    cm_height: float
    min_kb: int
    max_kb: int
    note: str | None = None
    source: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PresetCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    category: str
    label: str
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    dpi: int = Field(gt=0)
    cm_width: float = Field(gt=0)
    cm_height: float = Field(gt=0)
    min_kb: int = Field(gt=0)
    max_kb: int = Field(gt=0)
    note: str | None = None
    source: str | None = None


class ResizeMeta(BaseModel):
    width_px: int
    height_px: int
    dpi: int
    result_kb: float
    min_kb: int
    max_kb: int
    in_range: bool
    message: str
