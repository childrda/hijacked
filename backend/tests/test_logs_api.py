"""Tests for logs API: geo/ip extraction from payload_json."""
from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")

from app.api.routes_logs import _geo_from_payload  # noqa: E402


def test_geo_from_payload_empty():
    assert _geo_from_payload(None) == {
        "ip_address": None,
        "region_code": None,
        "subdivision_code": None,
        "ip_asn": None,
    }
    assert _geo_from_payload({}) == {
        "ip_address": None,
        "region_code": None,
        "subdivision_code": None,
        "ip_asn": None,
    }


def test_geo_from_payload_ip_address():
    payload = {"ipAddress": "199.201.191.170"}
    out = _geo_from_payload(payload)
    assert out["ip_address"] == "199.201.191.170"
    assert out["region_code"] is None
    assert out["subdivision_code"] is None
    assert out["ip_asn"] is None


def test_geo_from_payload_network_info():
    payload = {
        "ipAddress": "199.201.191.170",
        "networkInfo": {
            "regionCode": "US",
            "subdivisionCode": "US-VA",
            "ipAsn": [12345],
        },
    }
    out = _geo_from_payload(payload)
    assert out["ip_address"] == "199.201.191.170"
    assert out["region_code"] == "US"
    assert out["subdivision_code"] == "US-VA"
    assert out["ip_asn"] == 12345


def test_geo_from_payload_ip_asn_single_value():
    payload = {"networkInfo": {"ipAsn": 99999}}
    out = _geo_from_payload(payload)
    assert out["ip_asn"] == 99999


def test_geo_from_payload_ip_asn_array_takes_first():
    payload = {"networkInfo": {"ipAsn": [111, 222]}}
    out = _geo_from_payload(payload)
    assert out["ip_asn"] == 111
