from datetime import date

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tagline: str
    website: str
    email: str
    location: str
    founder_name: str
    founder_title: str


class LetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    candidate_name: str
    candidate_email: str
    candidate_address: str
    position: str
    start_date: date
    employment_type: str
    work_location: str
    letter_date: date
    status: str
