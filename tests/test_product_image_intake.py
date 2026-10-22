"""Scripted image intake uses the existing human-reviewed training draft path."""

import base64
import json
from datetime import date
from pathlib import Path

import pytest

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product import store
from blastbridge.product.agent import ProviderTurn, ScriptedProvider
from blastbridge.product.image_intake import (
    MAX_IMAGE_BYTES,
    image_content_block,
    image_sha256,
    load_image_replay,
    run_image_intake,
    validate_upload,
)
from blastbridge.product.models import EventStatus, IntakeSource
from blastbridge.product.seed import DEMO_PEOPLE

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 19)
IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1xoAAAAASUVORK5CYII="
)


@pytest.fixture
def envelope():
    record = json.loads((ROOT / "examples/fictional/intake/image_replay.json").read_text())
    return json.loads("".join(block["text"] for block in record["turns"][-1]["blocks"]))


@pytest.fixture
def conn(tmp_path):
    connection = store.connect(tmp_path / "image.sqlite")
    store.init_db(connection)
    store.seed_people(connection, DEMO_PEOPLE)
    yield connection
    connection.close()


def run(envelope):
    record = json.loads((ROOT / "examples/fictional/intake/image_replay.json").read_text())
    tools = record["turns"][0]["blocks"]
    blocks = [{"type": "text", "text": json.dumps(envelope)}]
    provider = ScriptedProvider(
        [
            ProviderTurn("tool_use", tools, tools, "scripted-image"),
            ProviderTurn("end_turn", blocks, blocks, "scripted-image"),
        ]
    )
    return run_image_intake(
        IMAGE,
        "image/png",
        provider,
        load_weapon_catalog(ROOT / "data/reference/weapons.json"),
        DEMO_PEOPLE,
        TODAY,
    )


def test_exact_visible_count_stays_exact(envelope):
    result = run(envelope)
    assert result.error is None
    assert result.draft is not None
    assert result.draft.crews[0].physical_event_count == 6
    assert result.origins["Launcher 1 physical events"] == "image transcription"
    assert result.origins["Launcher 1 · Launcher chief"] == "fictional roster"


def test_question_mark_and_explicit_unknown_stay_unknown(envelope):
    observed = envelope["observed_text"]
    for marker in ("?", "unknown", "unrecorded"):
        envelope["observed_text"] = observed.replace("?", marker)
        envelope["proposal"]["crews"][1]["count_text"] = marker
        result = run(envelope)
        assert result.draft is not None
        assert result.draft.crews[1].physical_event_count is None
        assert result.form_values["f_c1_known"] == "Unknown"
        assert result.form_values["f_c1_count"] is None


def test_ambiguous_count_never_becomes_numeric(envelope):
    envelope["observed_text"] = envelope["observed_text"].replace(
        "Launcher 1 - 6", "Launcher 1 - several"
    )
    crew = envelope["proposal"]["crews"][0]
    crew["count_text"] = "several"
    # Even an incorrectly exact structured response cannot turn this word into a count.
    result = run(envelope)
    assert result.form_values["f_c0_count"] is None
    assert result.form_values["f_c0_known"] is None
    assert result.draft is None


def test_person_absent_from_observed_text_cannot_enter_draft(envelope):
    envelope["observed_text"] = envelope["observed_text"].replace("Avery Kestrel", "[unreadable]")
    result = run(envelope)
    assert result.form_values["f_c0_chief"] is None
    assert result.origins["Launcher 1 · Launcher chief"] == "unresolved"
    assert result.draft is None


def test_unreadable_text_is_not_invented(envelope):
    envelope["legibility"] = "UNUSABLE"
    envelope["observed_text"] = "[unreadable]"
    # Ignore even a complete proposal when its source is unusable.
    result = run(envelope)
    assert result.error == "The record isn't clear enough to structure reliably."
    assert result.narrative == "[unreadable]"
    assert result.draft is None
    assert result.form_values == {}
    envelope["legibility"] = "PARTIAL"
    envelope["unresolved_visual"] = ["Crew assignment unreadable"]
    assert run(envelope).draft is None


def test_image_proposal_enters_existing_review_path(conn, envelope):
    result = run(envelope)
    assert result.draft is not None
    assert store.list_events(conn, EventStatus.DRAFT) == []
    event_id = store.save_draft(conn, result.draft, intake_source=IntakeSource.AI_LIVE)
    event = store.get_event(conn, event_id)
    assert event.status is EventStatus.DRAFT
    assert event.intake_source is IntakeSource.AI_LIVE
    assert store.member_history(conn, "FIC-001") == []
    assert store.approve_event(conn, event_id, event.revision)
    assert store.get_event(conn, event_id).status is EventStatus.APPROVED


def test_image_bytes_are_not_written_to_storage(conn, tmp_path, envelope):
    before = set(tmp_path.iterdir())
    result = run(envelope)
    assert result.draft is not None
    store.save_draft(conn, result.draft, intake_source=IntakeSource.AI_LIVE)
    assert set(tmp_path.iterdir()) == before
    dump = "\n".join(conn.iterdump())
    assert base64.b64encode(IMAGE).decode("ascii") not in dump
    assert image_sha256(IMAGE) not in dump
    assert result.narrative not in dump
    block = image_content_block(IMAGE, "image/png")
    assert base64.b64decode(block["source"]["data"]) == IMAGE
    for data, media_type in (
        (IMAGE, "image/jpeg"),
        (b"not an image", "image/png"),
        (b"x" * (MAX_IMAGE_BYTES + 1), "image/png"),
    ):
        with pytest.raises(ValueError):
            validate_upload(data, media_type)
    with pytest.raises(ValueError, match="Use manual entry"):
        load_image_replay(IMAGE)
