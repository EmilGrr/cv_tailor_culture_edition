from typing import Literal

from pydantic import BaseModel, Field


class Contact(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    links: list[str] = Field(default_factory=list)


class Bullet(BaseModel):
    text: str
    source: str = ""


class Experience(BaseModel):
    role: str = ""
    employer: str = ""
    place: str = ""
    start: str = ""
    end: str = ""
    bullets: list[Bullet] = Field(default_factory=list)


class Project(BaseModel):
    year: str = ""
    title: str = ""
    role: str = ""
    partner: str = ""
    scope: str = ""
    source: str = ""


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    period: str = ""
    details: str = ""


class Language(BaseModel):
    name: str = ""
    level: str = ""


class Volunteer(BaseModel):
    role: str = ""
    organisation: str = ""
    period: str = ""
    details: str = ""


class CV(BaseModel):
    language: Literal["sv", "en"] = "sv"
    contact: Contact = Field(default_factory=Contact)
    summary: str = ""
    core_skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    digital_skills: list[str] = Field(default_factory=list)
    volunteer: list[Volunteer] = Field(default_factory=list)
    references: str = ""
    hidden_sections: list[str] = Field(default_factory=list)
    gaps_and_questions: list[str] = Field(default_factory=list)
    left_out: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    text: str
    evidence: str = ""
    source: str = ""


class JobAnalysis(BaseModel):
    title: str = ""
    employer: str = ""
    language: Literal["sv", "en"] = "sv"
    requirements: list[Requirement] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class Draft(BaseModel):
    analysis: JobAnalysis
    cv: CV


# Sections the user can regenerate individually, mapped to their CV field.
REGENERABLE_SECTIONS = (
    "summary",
    "core_skills",
    "experience",
    "projects",
    "education",
    "languages",
    "digital_skills",
    "volunteer",
)

# Sections the user can remove from the CV (contact details are always kept).
HIDEABLE_SECTIONS = REGENERABLE_SECTIONS + ("references",)
