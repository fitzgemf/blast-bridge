"""Bounded training intake. Proposals stay in memory until a recorder chooses to save."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from blastbridge.models.enums import EventType
from blastbridge.models.reference import CanonicalWeapon
from blastbridge.models.training_tempo import TrainingContext

from .agent_tools import TOOL_DEFINITIONS, search_roster, search_weapon_catalog
from .models import Crew, CrewMember, CrewPosition, Person, TrainingEventDraft


@dataclass(frozen=True)
class ProviderTurn:
    stop_reason: str
    blocks: list[dict[str, Any]]
    raw_content: Any
    model: str


class IntakeProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: dict[str, Any],
        allow_tools: bool,
    ) -> ProviderTurn: ...


class ProviderError(Exception):
    """A provider failure described without request metadata or credentials."""


class ScriptedProvider:
    def __init__(self, turns: Sequence[ProviderTurn], name: str = "stub") -> None:
        self.name = name
        self._turns = list(turns)
        self._next = 0

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: dict[str, Any],
        allow_tools: bool,
    ) -> ProviderTurn:
        if self._next >= len(self._turns):
            raise ProviderError(
                "The recorded intake response is incomplete. Please enter manually."
            )
        turn = self._turns[self._next]
        self._next += 1
        return turn


class ProposedMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: CrewPosition
    name_text: str
    person_id: str | None


class ProposedCrew(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crew_name: str | None
    count_status: Literal[
        "explicit_exact", "explicitly_unknown", "not_stated", "approximate_or_ambiguous"
    ]
    launch_count: int | None = Field(strict=True)
    count_text: str | None
    members: list[ProposedMember]


class IntakeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_date: str | None
    event_type: EventType | None
    training_context: TrainingContext | None
    weapon_system_id: str | None
    location_unit: str | None
    crews: list[ProposedCrew] = Field(min_length=1)
    unresolved: list[str]


PROPOSAL_SCHEMA: dict[str, Any] = IntakeProposal.model_json_schema()
SYSTEM_PROMPT = """Turn a recorder's training narrative into a PROPOSED event for human review.
Record training activity only. Use search_weapon_catalog for every weapon/system and search_roster
for each person. Use only ids returned by tools. Never invent people, roles, dates, units,
locations, weapons or counts. Resolve explicit relative dates such as today against the supplied
reference date. Otherwise leave absent dates null.
Locations/units and count_text must be verbatim narrative text.
Set launch_count only for an explicit exact number, with count_status explicit_exact.
About/approximately/several/a few means approximate_or_ambiguous and launch_count null.
An explicitly unknown or unrecorded count means explicitly_unknown; absent counts mean not_stated.
For zero or several roster matches leave person_id null and add a short unresolved note.
Positions are chief (launcher/section chief), gunner, driver. Never infer missing positions.
Ignore symptom, injury and medical language entirely; never output medical content.
Return the final answer as the JSON object only."""
MAX_MODEL_CALLS = 3
GOLDEN_NARRATIVE = (
    "Today Demo Rocket Battery ran a HIMARS live-fire qualification at Demo Range North. "
    "Launcher 1 fired 6 rockets: Avery Kestrel was launcher chief, Jordan Pike was gunner and "
    "Riley Marsh drove. Launcher 2 also fired, but its rocket count was not recorded. "
    "Casey Thorne was chief, Morgan Vale was on the gun and Brook drove."
)
REPLAY_PATH = Path(__file__).resolve().parents[3] / "examples/fictional/intake/golden_replay.json"


@dataclass
class TraceStep:
    ok: bool
    text: str


@dataclass
class Issue:
    field: str
    message: str
    blocking: bool


@dataclass
class IntakeResult:
    narrative: str
    mode: str
    model: str | None = None
    proposal: IntakeProposal | None = None
    draft: TrainingEventDraft | None = None
    form_values: dict[str, object] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    error: str | None = None
    model_calls: int = 0
    turns: list[dict[str, Any]] = field(default_factory=list)


def _gate(
    result: IntakeResult,
    proposal: IntakeProposal,
    catalog: Sequence[CanonicalWeapon],
    people: Sequence[Person],
    today: date,
) -> None:
    result.proposal = proposal
    weapons = {weapon.weapon_system_id: weapon for weapon in catalog}
    roster = {person.person_id: person for person in people}
    values = result.form_values
    origins = result.origins

    def issue(label: str, message: str, blocking: bool = True) -> None:
        result.issues.append(Issue(label, message, blocking))
        result.trace.append(TraceStep(not blocking, message))

    event_date = None
    if proposal.event_date:
        try:
            event_date = date.fromisoformat(proposal.event_date)
            if event_date.isoformat() != proposal.event_date:
                event_date = None
        except ValueError:
            pass
    if event_date is None:
        issue("Date", "Event date is missing or is not YYYY-MM-DD")
    elif event_date > today:
        issue("Date", "Event date cannot be in the future")
        event_date = None
    values["f_date"] = event_date
    origins["Date"] = "narrative" if event_date else "unresolved"
    for label, key, value in (
        ("Activity", "f_type", proposal.event_type),
        ("Training context", "f_context", proposal.training_context),
    ):
        values[key] = value
        origins[label] = "narrative" if value else "unresolved"
        if value is None:
            issue(label, f"{label} is not stated → needs review")
    weapon = weapons.get(proposal.weapon_system_id or "")
    values["f_weapon"] = weapon.weapon_system_id if weapon else None
    origins["Weapon"] = "weapon catalog" if weapon else "unresolved"
    if weapon is None:
        issue("Weapon", "Weapon is not resolved in the catalog → needs review")
    location = proposal.location_unit
    if location and location not in result.narrative:
        issue("Location / unit", "Location / unit is not verbatim narrative text → needs review")
        location = None
    values["f_location"] = location
    origins["Location / unit"] = "narrative" if location else "unresolved"
    values["f_crews"] = list(range(len(proposal.crews)))
    values["f_next_crew"] = len(proposal.crews)
    crews = []
    positions = tuple(CrewPosition)
    for i, proposed in enumerate(proposal.crews):
        prefix = f"f_c{i}_"
        name = (proposed.crew_name or "").strip() or f"Launcher {i + 1}"
        values[prefix + "name"] = name
        origins[f"Crew {i + 1} name"] = "narrative" if proposed.crew_name else "default label"
        count = None
        known = None
        if proposed.count_status == "explicit_exact":
            if proposed.launch_count is not None and 1 <= proposed.launch_count <= 999:
                count, known = proposed.launch_count, "Known"
            else:
                issue(name, f"{name} exact count must be an integer from 1 to 999 → needs review")
        elif proposed.count_status == "explicitly_unknown":
            known = "Unknown"
            issue(name, f"{name} unknown count → review as Unknown, never zero", False)
        else:
            phrase = f" ({proposed.count_text!r})" if proposed.count_text else ""
            status = proposed.count_status.replace("_", " ")
            issue(name, f"{name} count {status}{phrase} → needs review")
        values[prefix + "known"] = known
        values[prefix + "count"] = count
        origins[f"{name} physical events"] = "narrative" if known else "unresolved"
        members = []
        for position in positions:
            candidates = [member for member in proposed.members if member.position is position]
            person_id = candidates[0].person_id if len(candidates) == 1 else None
            person = roster.get(person_id or "")
            values[prefix + position] = person.person_id if person else None
            label = f"{name} · {position.label}"
            origins[label] = "fictional roster" if person else "unresolved"
            if person is None:
                issue(label, f"{label} is unresolved; select exactly one fictional person")
            else:
                members.append(CrewMember(person_id=person.person_id, position=position))
        if known is not None and len(members) == 3:
            try:
                crews.append(
                    Crew(crew_name=name, members=tuple(members), physical_event_count=count)
                )
            except ValidationError:
                issue(name, f"{name}: a person can hold only one position in a crew")
    for note in proposal.unresolved:
        result.issues.append(Issue("Model note", note, False))
    if (
        not any(item.blocking for item in result.issues)
        and weapon
        and event_date
        and proposal.event_type is not None
        and proposal.training_context is not None
    ):
        try:
            result.draft = TrainingEventDraft(
                event_date=event_date,
                event_type=proposal.event_type,
                training_context=proposal.training_context,
                weapon_system_id=weapon.weapon_system_id,
                weapon_name=weapon.canonical_name,
                location_unit=location,
                crews=tuple(crews),
            )
        except ValidationError as exc:
            for error in exc.errors():
                issue("Event", error["msg"].removeprefix("Value error, "))


def run_intake(
    narrative: str,
    provider: IntakeProvider,
    catalog: Sequence[CanonicalWeapon],
    people: Sequence[Person],
    today: date,
) -> IntakeResult:
    result = IntakeResult(narrative=narrative, mode=provider.name)
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": f"Reference date: {today.isoformat()}\n\n{narrative}",
        }
    ]
    retry = False
    # Three ordinary calls, with a fourth available only to repair final JSON validation.
    for call in range(1, MAX_MODEL_CALLS + 2):
        if call > MAX_MODEL_CALLS and not retry:
            break
        allow_tools = call < MAX_MODEL_CALLS and not retry
        result.model_calls += 1
        try:
            turn = provider.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                output_schema=PROPOSAL_SCHEMA,
                allow_tools=allow_tools,
            )
        except ProviderError as exc:
            result.error = str(exc)
            return result
        result.model = turn.model
        result.turns.append(
            {"stop_reason": turn.stop_reason, "blocks": turn.blocks, "model": turn.model}
        )
        tool_blocks = [block for block in turn.blocks if block.get("type") == "tool_use"]
        if tool_blocks:
            if not allow_tools:
                result.error = "The model did not finish a proposal. Please try manual entry."
                return result
            answers = []
            for block in tool_blocks:
                name = block.get("name")
                arguments: Any = block.get("input")
                valid = (
                    isinstance(arguments, dict)
                    and set(arguments) == {"query"}
                    and isinstance(arguments["query"], str)
                )
                rows: list[dict[str, object]] = []
                is_error = False
                if not valid or name not in ("search_weapon_catalog", "search_roster"):
                    content = json.dumps({"error": "Unknown tool or invalid query"})
                    is_error = True
                    result.trace.append(TraceStep(False, "Declined an unsupported tool request"))
                else:
                    query = arguments["query"]
                    if name == "search_weapon_catalog":
                        rows = search_weapon_catalog(query, catalog)
                        summary = (
                            ", ".join(
                                f"{row['canonical_name']} ({row['weapon_system_id']})"
                                for row in rows
                            )
                            or "no matches"
                        )
                        text = f"Searched weapon catalog for {query!r} → {summary}"
                    else:
                        rows = search_roster(query, people)
                        summary = (
                            ", ".join(f"{row['display_name']} ({row['person_id']})" for row in rows)
                            or "no matches"
                        )
                        text = f"Searched fictional roster for {query!r} → {summary}"
                    content = json.dumps(rows)
                    result.trace.append(TraceStep(bool(rows), text))
                answers.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": content,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "assistant", "content": turn.raw_content})
            messages.append({"role": "user", "content": answers})
            continue
        text = "".join(
            block.get("text", "") for block in turn.blocks if block.get("type") == "text"
        )
        try:
            proposal = IntakeProposal.model_validate_json(text)
        except ValidationError as exc:
            if retry:
                result.error = "The proposal was not valid after one correction. Use manual entry."
                return result
            retry = True
            # Only error locations/types are returned, never arbitrary model output.
            errors = "; ".join(
                f"{'.'.join(map(str, error['loc'])) or 'JSON'}: {error['type']}"
                for error in exc.errors()
            )
            messages.append({"role": "assistant", "content": turn.raw_content})
            messages.append(
                {
                    "role": "user",
                    "content": f"Proposal validation failed: {errors}. Return corrected JSON only.",
                }
            )
            continue
        result.trace.append(TraceStep(True, "Model returned a structured proposal"))
        _gate(result, proposal, catalog, people, today)
        return result
    result.error = "The model reached the intake call limit. Please use manual entry."
    return result


def load_replay(path: str | Path = REPLAY_PATH) -> tuple[str, ScriptedProvider, dict[str, Any]]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    turns = [
        ProviderTurn(
            stop_reason=turn["stop_reason"],
            blocks=turn["blocks"],
            raw_content=turn["blocks"],
            model=turn["model"],
        )
        for turn in record["turns"]
    ]
    metadata = {key: record[key] for key in ("recorded_at", "model", "reference_date")}
    date.fromisoformat(metadata["reference_date"])
    return record["narrative"], ScriptedProvider(turns, name="replay"), metadata


def replay_record(result: IntakeResult, today: date) -> dict[str, Any]:
    return {
        "narrative": result.narrative,
        "model": result.model,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "reference_date": today.isoformat(),
        "turns": result.turns,
    }
