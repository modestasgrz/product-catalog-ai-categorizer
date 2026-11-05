from pydantic import BaseModel, Field


class Category(BaseModel):
    id: str
    name: str
    group: str
    url: str
    description: str


class CategoryTree(BaseModel):
    marketplace: str
    categories: list[Category]


class Classification(BaseModel):
    category_id: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class RunSettings(BaseModel):
    model: str = "claude-sonnet-5-5"
    concurrency: int = Field(default=8, ge=1, le=32)
    threshold: float = Field(default=0.70, ge=0, le=1)
    limit: int | None = Field(default=None, ge=1)


class RunReport(BaseModel):
    input_file: str
    rows_total: int
    status_counts: dict[str, int]
    model: str
    threshold: float
    encoding: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    estimated_cost_usd: float
    duration_seconds: float
