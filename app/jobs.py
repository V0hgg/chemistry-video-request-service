from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class VideoRequest(BaseModel):
    concept: str = Field(min_length=1, max_length=300)

    @field_validator("concept", mode="before")
    @classmethod
    def clean(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("concept must be 1 to 300 characters")
        return value


class VideoJob(BaseModel):
    id: UUID
    concept: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    video_url: str | None = None
    error: str | None = None


class ClaimedJob(BaseModel):
    id: UUID
    concept: str
    claim_token: str
    attempt_count: int
