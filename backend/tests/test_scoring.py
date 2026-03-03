"""Unit tests for scoring."""
import pytest
from app.detect.scoring import score_from_rule_hits, score_to_risk_level
from app.detect.rules import CORRELATION_BONUS, get_score, get_label


def test_score_from_rule_hits_single():
    hits = [{"rule": "external_forwarding_enabled", "parameters": {}}]
    assert score_from_rule_hits(hits) == 80


def test_score_from_rule_hits_multiple():
    hits = [
        {"rule": "external_forwarding_enabled"},
        {"rule": "filter_with_delete"},
    ]
    assert score_from_rule_hits(hits) == 80 + 70 + CORRELATION_BONUS


def test_score_to_risk_level():
    assert score_to_risk_level(120) == "CRITICAL"
    assert score_to_risk_level(100) == "CRITICAL"
    assert score_to_risk_level(70) == "HIGH"
    assert score_to_risk_level(40) == "MEDIUM"
    assert score_to_risk_level(20) == "LOW"


def test_get_score_label():
    assert get_score("external_forwarding_enabled") == 80
    assert get_label("external_forwarding_enabled")
    assert get_score("unknown_rule") == 0
    assert get_label("unknown_rule") == ""


def test_score_points_override():
    hits = [{"rule": "mass_outbound_single", "parameters": {"points_override": 77}}]
    assert score_from_rule_hits(hits) == 77
