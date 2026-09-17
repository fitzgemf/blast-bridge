"""Controlled vocabularies; unknown is never equivalent to absent or zero."""

from enum import StrEnum


class Branch(StrEnum):
    ARMY = "army"
    MARINE_CORPS = "marine_corps"
    NAVY = "navy"
    AIR_FORCE = "air_force"
    SPACE_FORCE = "space_force"
    COAST_GUARD = "coast_guard"
    UNKNOWN = "unknown"


class Component(StrEnum):
    ACTIVE = "active"
    RESERVE = "reserve"
    NATIONAL_GUARD = "national_guard"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    OFFICIAL = "official"
    PEER_REVIEWED = "peer_reviewed"
    SENSOR = "sensor"
    CONTEMPORANEOUS_SELF_REPORT = "contemporaneous_self_report"
    RETROSPECTIVE_SELF_REPORT = "retrospective_self_report"
    SUBJECT_MATTER_EXPERT = "subject_matter_expert"
    ASSUMPTION = "assumption"
    SYNTHETIC = "synthetic"


class DataKind(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    SELF_REPORTED = "self_reported"
    SYNTHETIC = "synthetic"
    DOCUMENTED = "documented"


class WeaponFamily(StrEnum):
    ROCKET_MISSILE_ARTILLERY = "rocket_missile_artillery"
    SELF_PROPELLED_HOWITZER = "self_propelled_howitzer"
    TOWED_HOWITZER = "towed_howitzer"
    MORTAR = "mortar"
    TANK_MAIN_GUN = "tank_main_gun"
    HEAVY_MACHINE_GUN = "heavy_machine_gun"
    SHOULDER_FIRED = "shoulder_fired"
    EXPLOSIVE_BREACHING = "explosive_breaching"
    OTHER = "other"


class Tier1Status(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Context(StrEnum):
    TRAINING = "training"
    DEPLOYMENT = "deployment"
    OPERATIONAL = "operational"
    OTHER = "other"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    WEAPON_FIRING = "weapon_firing"
    EXPLOSIVE_BREACHING = "explosive_breaching"
    DETONATION = "detonation"
    OTHER = "other"
    UNKNOWN = "unknown"


class Participation(StrEnum):
    FIRED = "fired"
    NEARBY = "nearby"
    BOTH = "both"
    UNKNOWN = "unknown"


class BodyPosition(StrEnum):
    STANDING = "standing"
    KNEELING = "kneeling"
    PRONE = "prone"
    SEATED = "seated"
    OTHER = "other"
    UNKNOWN = "unknown"


class Environment(StrEnum):
    OPEN_AIR = "open_air"
    ENCLOSED = "enclosed"
    PARTIALLY_ENCLOSED = "partially_enclosed"
    VEHICLE_INTERIOR = "vehicle_interior"
    OTHER = "other"
    UNKNOWN = "unknown"


class SensorAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PressureUnit(StrEnum):
    PA = "Pa"
    KPA = "kPa"
    PSI = "psi"


class ImpulseUnit(StrEnum):
    PA_S = "Pa*s"
    KPA_MS = "kPa*ms"
    PSI_MS = "psi*ms"


class SensorQuality(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    SUSPECT = "suspect"
    REJECTED = "rejected"


class SymptomSeverity(StrEnum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class MedicalEvaluationStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    PLANNED = "planned"
    EVALUATED = "evaluated"
    UNKNOWN = "unknown"
