"""Fictional reports; temporal association does not establish causation."""

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from .models import ProductModel, Text


class SymptomSource(StrEnum):
    SELF_REPORTED = "self_reported"
    MEDICAL_OR_READINESS_RECORDED = "medical_or_readiness_recorded"

    @property
    def label(self) -> str:
        return {
            self.SELF_REPORTED: "Self-reported",
            self.MEDICAL_OR_READINESS_RECORDED: "Recorded by medical/readiness staff",
        }[self]


class TemporalRelationship(StrEnum):
    AFTER_RECORDED_EVENT = "after_recorded_event"
    RELATIONSHIP_UNKNOWN = "relationship_unknown"
    NOT_LINKED_TO_EVENT = "not_linked_to_event"

    @property
    def label(self) -> str:
        return {
            self.AFTER_RECORDED_EVENT: "Reported after a recorded event",
            self.RELATIONSHIP_UNKNOWN: "Relationship to a recorded event unknown",
            self.NOT_LINKED_TO_EVENT: "Not linked to a recorded event",
        }[self]


class Persistence(StrEnum):
    RESOLVED = "resolved"
    STILL_PRESENT = "still_present"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            self.RESOLVED: "Resolved",
            self.STILL_PRESENT: "Still present",
            self.UNKNOWN: "Unknown",
        }[self]


class FunctionalImpact(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            self.YES: "Affecting daily function",
            self.NO: "Not affecting daily function",
            self.UNKNOWN: "Unknown",
        }[self]


class Symptom(StrEnum):
    CONCENTRATION_PROBLEMS = "concentration_problems"
    DIFFICULTY_HEARING = "difficulty_hearing"
    DIZZINESS = "dizziness"
    FATIGUE = "fatigue"
    HEADACHES = "headaches"
    IRRITABILITY = "irritability"
    MEMORY_PROBLEMS = "memory_problems"
    SLEEP_PROBLEMS = "sleep_problems"
    SLOWED_REACTION_TIME = "slowed_reaction_time"
    SLOWED_THINKING = "slowed_thinking"
    TINNITUS = "tinnitus"

    @property
    def label(self) -> str:
        if self is self.TINNITUS:
            return "Tinnitus (ringing in the ears)"
        return self.value.replace("_", " ").capitalize()


class DangerSign(StrEnum):
    WORSENING_HEADACHE = "worsening_headache"
    WEAKNESS_NUMBNESS_COORDINATION = "weakness_numbness_coordination"
    CONVULSIONS_SEIZURES = "convulsions_seizures"
    REPEATED_VOMITING = "repeated_vomiting"
    SLURRED_SPEECH_UNUSUAL_BEHAVIOR = "slurred_speech_unusual_behavior"
    UNEQUAL_PUPILS = "unequal_pupils"
    RECOGNITION_CONFUSION = "recognition_confusion"
    CONSCIOUSNESS = "consciousness"

    @property
    def label(self) -> str:
        return {
            self.WORSENING_HEADACHE: "Headache that gets worse and does not go away",
            self.WEAKNESS_NUMBNESS_COORDINATION: "Weakness, numbness, or decreased coordination",
            self.CONVULSIONS_SEIZURES: "Convulsions or seizures",
            self.REPEATED_VOMITING: "Repeated vomiting",
            self.SLURRED_SPEECH_UNUSUAL_BEHAVIOR: "Slurred speech or unusual behavior",
            self.UNEQUAL_PUPILS: "One pupil larger than the other",
            self.RECOGNITION_CONFUSION: (
                "Cannot recognize people or places, or is confused, restless, or agitated"
            ),
            self.CONSCIOUSNESS: "Loss of consciousness, very drowsy, or cannot be woken up",
        }[self]


class SymptomReportDraft(ProductModel):
    person_id: Text
    event_id: Text | None = None
    report_date: date
    source: SymptomSource
    symptoms: tuple[Symptom, ...] = ()
    danger_signs: tuple[DangerSign, ...] = ()
    note: str | None = None
    temporal_relationship: TemporalRelationship
    persistence: Persistence
    functional_impact: FunctionalImpact

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("note must be at most 500 characters")
        return value or None

    @model_validator(mode="after")
    def valid_report(self) -> Self:
        if len(self.symptoms) != len(set(self.symptoms)):
            raise ValueError("symptoms must not contain duplicates")
        if len(self.danger_signs) != len(set(self.danger_signs)):
            raise ValueError("danger signs must not contain duplicates")
        if not (self.symptoms or self.danger_signs or self.note):
            raise ValueError("record at least one symptom, danger sign or note")
        if (
            self.temporal_relationship is TemporalRelationship.AFTER_RECORDED_EVENT
            and not self.event_id
        ):
            raise ValueError("reported after a recorded event requires a linked event")
        if self.temporal_relationship is TemporalRelationship.NOT_LINKED_TO_EVENT and self.event_id:
            raise ValueError("not linked to an event requires no linked event")
        return self


class SymptomReport(ProductModel):
    report_id: Text
    draft: SymptomReportDraft
    confirmed_at: str
