"""Deterministic guidance for fictional reports. Follow-up is not a diagnosis.

Background: Low-level blast exposure does not typically result in mild TBI.
"""

from dataclasses import dataclass
from enum import StrEnum

from .symptoms import FunctionalImpact, Persistence, SymptomReportDraft, TemporalRelationship

GUIDANCE_REVIEWED_AS_OF = "2026-10-19"


@dataclass(frozen=True)
class GuidanceSource:
    key: str
    title: str
    publisher: str
    version: str
    url: str
    verification: str
    use: str


_DHA = "Traumatic Brain Injury Center of Excellence, Defense Health Agency"
_ARCHIVE = (
    "Verified 2026-10-19 from an Internet Archive copy of the official PDF (captured 2026-07-22); "
    "health.mil was not reachable from the verification network."
)
SOURCES: tuple[GuidanceSource, ...] = (
    GuidanceSource(
        "tbicoe_service_member",
        "What You Should Know About Blast Overpressure (Service Member Fact Sheet)",
        _DHA,
        "Released July 2023; revised September 2025",
        "https://health.mil/Reference-Center/Fact-Sheets/2025/09/16/Blast-Overpressure-Service-Member-Fact-Sheet",
        _ARCHIVE,
        "Follow-up rule: 'If your symptoms persist and impact your daily function, inform your "
        "command and medical provider.'",
    ),
    GuidanceSource(
        "tbicoe_provider_tool",
        "Blast Overpressure Provider Support Tool",
        _DHA,
        "Released September 2025",
        "https://health.mil/Reference-Center/Fact-Sheets/2025/09/16/Blast-Overpressure-Provider-Support-Tool",
        _ARCHIVE,
        (
            "Structured symptom list (symptoms that may be reported following "
            "low-level blast exposure)."
        ),
    ),
    GuidanceSource(
        "cdc_danger_signs",
        "Symptoms of Mild TBI and Concussion",
        "Centers for Disease Control and Prevention",
        "Page dated Sept. 15, 2025",
        "https://www.cdc.gov/traumatic-brain-injury/signs-symptoms/index.html",
        "Verified 2026-10-19 from the live page.",
        "Adult danger signs requiring immediate emergency medical care.",
    ),
    GuidanceSource(
        "va_tbi_screening",
        "Traumatic Brain Injury (TBI) Screening",
        "U.S. Department of Veterans Affairs, Polytrauma/TBI System of Care",
        "Last updated September 29, 2026",
        "https://www.polytrauma.va.gov/system-of-care/TBI_Screening.asp",
        "Verified 2026-10-19 from the live page.",
        (
            "A positive screen does not diagnose TBI; it only indicates the need "
            "for further evaluation."
        ),
    ),
    GuidanceSource(
        "mace2",
        "Military Acute Concussion Evaluation 2 (MACE 2)",
        _DHA,
        "Health.mil publication listing dated Feb. 13, 2026",
        "https://health.mil/Reference-Center/Publications/2026/02/13/Military-Acute-Concussion-Evaluation-MACE-2",
        "Listing located 2026-10-19; document content could not be retrieved (host unreachable). "
        "Linked only; not reproduced.",
        "Clinical assessment resource for medically trained personnel. BlastBridge does not "
        "reproduce it and is not a self-screening tool.",
    ),
)


class FollowUpState(StrEnum):
    NO_FOLLOWUP_RULE_TRIGGERED = "no_followup_rule_triggered"
    FOLLOW_UP_SUGGESTED = "follow_up_suggested"
    URGENT_EVALUATION_RECOMMENDED = "urgent_evaluation_recommended"

    @property
    def label(self) -> str:
        return {
            self.NO_FOLLOWUP_RULE_TRIGGERED: "No rule-based follow-up signal",
            self.FOLLOW_UP_SUGGESTED: "Follow-up suggested",
            self.URGENT_EVALUATION_RECOMMENDED: "Urgent medical evaluation recommended",
        }[self]


@dataclass(frozen=True)
class FollowUp:
    state: FollowUpState
    headline: str
    explanation: str
    missing: tuple[str, ...]
    source_keys: tuple[str, ...]


def evaluate(report: SymptomReportDraft) -> FollowUp:
    undocumented = []
    if report.persistence is Persistence.UNKNOWN:
        undocumented.append("persistence")
    if report.functional_impact is FunctionalImpact.UNKNOWN:
        undocumented.append("functional impact")
    if report.temporal_relationship is TemporalRelationship.RELATIONSHIP_UNKNOWN:
        undocumented.append("the relationship to a recorded event")
    missing: tuple[str, ...] = ()
    if undocumented:
        subject = (
            undocumented[0]
            if len(undocumented) == 1
            else (", ".join(undocumented[:-1]) + " and " + undocumented[-1])
        )
        verb = "is" if len(undocumented) == 1 else "are"
        missing = (f"{subject[0].upper() + subject[1:]} {verb} not documented.",)
    if report.danger_signs:
        return FollowUp(
            FollowUpState.URGENT_EVALUATION_RECOMMENDED,
            "Urgent medical evaluation recommended",
            "One or more reported danger signs match current CDC emergency guidance. "
            "Seek emergency medical evaluation now. BlastBridge is surfacing the recorded "
            "danger sign; it does not "
            "diagnose concussion or TBI.",
            missing,
            ("cdc_danger_signs",),
        )
    if (
        report.symptoms
        and report.persistence is Persistence.STILL_PRESENT
        and report.functional_impact is FunctionalImpact.YES
    ):
        explanations = {
            TemporalRelationship.AFTER_RECORDED_EVENT: (
                "Persistent, function-affecting symptoms were reported after the linked recorded "
                "event. Current TBICoE guidance advises service members whose symptoms persist "
                "and impact daily function to inform their command and medical provider. "
                "BlastBridge does not determine whether the recorded exposure caused the symptoms "
                "and does not diagnose concussion or TBI."
            ),
            TemporalRelationship.RELATIONSHIP_UNKNOWN: (
                "Persistent, function-affecting symptoms were reported. Their relationship to "
                "recorded exposure is unknown. Current TBICoE guidance advises service members "
                "whose symptoms persist and impact daily function to inform their command and "
                "medical provider. BlastBridge does not determine whether any exposure caused "
                "the symptoms and does not diagnose concussion or TBI."
            ),
            TemporalRelationship.NOT_LINKED_TO_EVENT: (
                "Persistent, function-affecting symptoms were reported and were not linked to a "
                "recorded training event. Current TBICoE guidance advises service members whose "
                "symptoms persist and impact daily function to inform their command and medical "
                "provider. BlastBridge does not diagnose concussion or TBI."
            ),
        }
        return FollowUp(
            FollowUpState.FOLLOW_UP_SUGGESTED,
            "Follow-up suggested",
            explanations[report.temporal_relationship],
            missing,
            ("tbicoe_service_member",),
        )
    return FollowUp(
        FollowUpState.NO_FOLLOWUP_RULE_TRIGGERED,
        "No rule-based follow-up signal from the currently recorded information.",
        "This does not determine whether an injury is present or absent.",
        missing,
        ("tbicoe_service_member",),
    )


BOUNDARY_NOTE = (
    "Exposure is not injury. A report after an event is a temporal association, not a cause. "
    "Follow-up is not a diagnosis. Unknown is never treated as zero or as reassurance."
)
PRIVACY_NOTE = (
    "Prototype uses fictional data. A production implementation handling health information would "
    "require appropriate identity, authorization, privacy, security and "
    "records-governance controls."
)
GOVERNANCE_NOTE = (
    "Guidance sources reviewed: Oct. 19, 2026. Production use would require ongoing guidance "
    "review and version governance."
)
SYMPTOM_LIST_LABEL = (
    "Symptoms that may be reported following low-level blast exposure (TBICoE guidance)"
)
DANGER_SIGN_LABEL = (
    "CDC danger signs (separate from the symptom list): seek emergency care immediately"
)
EMPTY_FOLLOWUP = "No reports currently match a follow-up rule."
ABSENCE_NOTE = "This does not determine whether an injury is present or absent."
NOTE_RULE_CAPTION = (
    "Notes are not evaluated by the follow-up rule. "
    "Record any danger sign with the danger-sign checkboxes above."
)
