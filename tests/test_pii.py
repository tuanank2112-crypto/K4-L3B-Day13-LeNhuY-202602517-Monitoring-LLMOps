import json

from app.logging_config import scrub_event
from app.pii import hash_user_id, scrub_text, summarize_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD của tôi là 001099012345, cần cập nhật")
    assert "001099012345" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_formats() -> None:
    for card in ("4111 1111 1111 1111", "4111-1111-1111-1111", "4111111111111111"):
        out = scrub_text(f"Card {card} expired")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out
        assert "REDACTED_PHONE_VN" not in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport C1234567 for travel")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT_VN" in out


def test_non_pii_text_is_unchanged() -> None:
    text = "P95 latency is 3000ms for req-1a2b3c4d at 2026-09-30T10:00:00Z"
    assert scrub_text(text) == text


def test_summarize_text_scrubs_before_truncating() -> None:
    out = summarize_text("Call 0987654321 about card 4111 1111 1111 1111 " + "x" * 200)
    assert "0987654321" not in out
    assert "4111" not in out
    assert out.endswith("...")


def test_hash_user_id_is_stable_and_not_reversible_text() -> None:
    assert hash_user_id("u01") == hash_user_id("u01")
    assert hash_user_id("u01") != "u01"
    assert len(hash_user_id("u01")) == 12


def test_scrub_event_covers_nested_fields_and_exception_text() -> None:
    event = {
        "event": "request_failed student@vinuni.edu.vn",
        "correlation_id": "req-1a2b3c4d",
        "payload": {"detail": "phone 0901234567", "items": ["card 4111 1111 1111 1111"]},
        "exception": "ValueError: CCCD 001099012345",
        "latency_ms": 120,
    }

    scrubbed = scrub_event(None, "info", event)
    raw = json.dumps(scrubbed, ensure_ascii=False)

    for secret in ("student@vinuni.edu.vn", "0901234567", "4111 1111 1111 1111", "001099012345"):
        assert secret not in raw
    assert scrubbed["correlation_id"] == "req-1a2b3c4d"
    assert scrubbed["latency_ms"] == 120
