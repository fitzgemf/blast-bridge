"""Scripted image intake uses the existing human-reviewed training draft path."""

import base64
import json
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product import image_intake, store
from blastbridge.product.agent import ProviderTurn, ScriptedProvider
from blastbridge.product.image_intake import (
    MAX_IMAGE_BYTES,
    image_content_block,
    image_sha256,
    load_image_replay,
    prepare_image,
    run_image_intake,
    validate_upload,
)
from blastbridge.product.models import EventStatus, IntakeSource
from blastbridge.product.seed import DEMO_PEOPLE

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 19)


def image_bytes(image, format="PNG", **options):
    output = BytesIO()
    image.save(output, format=format, **options)
    return output.getvalue()


IMAGE = image_bytes(Image.new("RGB", (1, 1), "white"))


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
    assert result.origins["Launcher 1 physical events"] == "AI transcription (check against image)"
    assert result.origins["Launcher 1 · Launcher chief"] == "demo roster"


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
    assert base64.b64decode(block["source"]["data"]) == prepare_image(IMAGE, "image/png")[0]
    for data, media_type in (
        (IMAGE, "image/jpeg"),
        (b"not an image", "image/png"),
        (b"x" * (MAX_IMAGE_BYTES + 1), "image/png"),
    ):
        with pytest.raises(ValueError):
            validate_upload(data, media_type)
    with pytest.raises(ValueError, match="Use manual entry"):
        load_image_replay(IMAGE)


def test_original_upload_limit_is_twenty_megabytes():
    assert MAX_IMAGE_BYTES == 20 * 1024 * 1024
    boundary = IMAGE + b"\0" * (MAX_IMAGE_BYTES - len(IMAGE))
    assert validate_upload(boundary, "image/png") == "image/png"
    with pytest.raises(ValueError, match="no larger than 20 MB"):
        validate_upload(boundary + b"\0", "image/png")


def test_large_image_is_prepared_in_memory_as_a_small_valid_image_block():
    original = image_bytes(Image.new("RGBA", (3200, 2400), (0, 0, 0, 0)))
    prepared, media_type, note = prepare_image(original, "image/png")
    assert media_type == "image/jpeg" and note == "Image resized for AI reading"
    assert len(prepared) < 3.7 * 1024 * 1024
    with Image.open(BytesIO(prepared)) as image:
        image.load()
        assert image.size == (2000, 1500)
        assert image.getpixel((0, 0)) == (255, 255, 255)
    block = image_content_block(original, "image/png")
    assert block["source"]["media_type"] == "image/jpeg"
    assert base64.b64decode(block["source"]["data"]) == prepared


def test_exif_rotated_jpeg_is_transposed_before_ai_reading():
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Private photo metadata"
    original = image_bytes(Image.new("RGB", (90, 40), "red"), "JPEG", exif=exif)
    prepared, media_type, note = prepare_image(original, "image/jpeg")
    assert media_type == "image/jpeg" and note is None  # rotated only, not resized
    with Image.open(BytesIO(prepared)) as image:
        image.load()
        assert image.size == (40, 90)
        assert image.getexif().get(274, 1) == 1
        assert not image.getexif()
    assert b"Exif\x00\x00" not in prepared


def test_demo_board_is_reencoded_but_replay_matching_uses_original_digest():
    original = (ROOT / "examples/fictional/intake/demo_range_board.png").read_bytes()
    prepared, media_type, note = prepare_image(original, "image/png")
    assert prepared != original
    assert image_sha256(prepared) != image_sha256(original)
    assert media_type == "image/jpeg" and note is None
    load_image_replay(original)
    with pytest.raises(ValueError, match="Use manual entry"):
        load_image_replay(prepared)
    with Image.open(BytesIO(prepared)) as image:
        assert image.mode == "RGB" and not image.getexif()


def test_prepared_input_is_not_decoded_again_and_provider_failure_is_tagged(monkeypatch):
    prepared, media_type, _ = prepare_image(IMAGE, "image/png")

    def unexpected_preparation(*args):
        raise AssertionError("Prepared session bytes must not be decoded again")

    monkeypatch.setattr(image_intake, "prepare_image", unexpected_preparation)
    block = image_content_block(prepared, media_type, prepared=True)
    assert base64.b64decode(block["source"]["data"]) == prepared
    result = run_image_intake(
        prepared, media_type, ScriptedProvider([]), [], [], TODAY, prepared=True
    )
    assert result.provider_error and result.error


def test_undecodable_image_has_a_friendly_error():
    with pytest.raises(
        ValueError, match="The image could not be read. Use a JPEG, PNG or WebP photo."
    ):
        prepare_image(b"\x89PNG\r\n\x1a\nnot an image", "image/png")


def test_oversized_pixel_count_is_refused_before_decoding(monkeypatch):
    buffer = BytesIO()
    Image.new("1", (40, 30)).save(buffer, format="PNG")
    monkeypatch.setattr(image_intake, "MAX_IMAGE_PIXELS", 40 * 30 - 1)

    def no_decode(self):
        raise AssertionError("pixels must not be decoded")

    monkeypatch.setattr(Image.Image, "load", no_decode)
    monkeypatch.setattr("PIL.ImageFile.ImageFile.load", no_decode)
    with pytest.raises(ValueError, match="could not be read"):
        prepare_image(buffer.getvalue(), "image/png")
