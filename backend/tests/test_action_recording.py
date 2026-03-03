"""Unit tests for action recording (logic only; no DB in these)."""
import pytest
from app.actions.containment import result_from_details


def test_result_from_details_proposed():
    details = {"proposed": True}
    assert result_from_details(details) == "SUCCESS"


def test_result_from_details_success():
    details = {"suspend": {"suspended": True}, "sign_out": {"success": True}}
    assert result_from_details(details) == "SUCCESS"


def test_result_from_details_failed():
    details = {"suspend": {"error": "User not found"}, "suspend_error": "User not found"}
    assert result_from_details(details) == "FAILED"
