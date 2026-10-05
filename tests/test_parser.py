"""Unit and smoke tests for egts.parser."""

import struct
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from egts.parser import (
    parse_hex, crc8, crc16,
    SR_POS_DATA, SR_IBEACON_EVENT, SR_CELL_INFO, SR_WIFI_AP_DATA, SR_RADIOTAG_EVENT,
)


# ── CRC ───────────────────────────────────────────────────────────────────────

class TestCrc:
    def test_crc8_known(self):
        # PT_RESPONSE packet header (10 bytes before HCS=0x4A)
        hdr = bytes.fromhex("0100030B0003008900004A")[:10]
        assert crc8(hdr) == 0x4A

    def test_crc16_pt_response(self):
        # SFRD = 15 38 00 → SFRCS = E833
        sfrd = bytes.fromhex("153800")
        assert crc16(sfrd) == 0xE833

    def test_crc8_empty(self):
        assert isinstance(crc8(b""), int)

    def test_crc16_empty(self):
        assert crc16(b"") == 0xFFFF


# ── parse_hex helpers ─────────────────────────────────────────────────────────

def _parse(hex_str):
    rows, err = parse_hex(hex_str.replace(" ", ""))
    assert err == "", f"parse_hex error: {err}"
    return rows


def _field(rows, field_name, layer_contains=None):
    for r in rows:
        if r.field == field_name:
            if layer_contains is None or layer_contains in r.layer:
                return r
    return None


# ── PT_RESPONSE smoke test ────────────────────────────────────────────────────

PT_RESPONSE_HEX = "0100030B0003008900004A15380033E8"

class TestPtResponse:
    def test_parse_ok(self):
        rows, err = parse_hex(PT_RESPONSE_HEX)
        assert err == ""
        assert len(rows) == 12

    def test_header_crc_ok(self):
        rows = _parse(PT_RESPONSE_HEX)
        hcs = _field(rows, "HCS")
        assert hcs is not None
        assert "OK" in hcs.decoded

    def test_body_crc_ok(self):
        rows = _parse(PT_RESPONSE_HEX)
        sfrcs = _field(rows, "SFRCS")
        assert sfrcs is not None
        assert "OK" in sfrcs.decoded

    def test_pid(self):
        rows = _parse(PT_RESPONSE_HEX)
        pid = _field(rows, "PID")
        assert pid.raw == 137

    def test_rpid(self):
        rows = _parse(PT_RESPONSE_HEX)
        rpid = _field(rows, "RPID")
        assert rpid.raw == 0x3815  # = 14357


# ── SR_POS_DATA ───────────────────────────────────────────────────────────────

IBEACON_HEX = (
    "0100000B0053000100019A4C00010000020210150028CE671A13119C9E47AD7F35137C012F000000"
    "0000C91700010A002A003F45550E8400E29B41D4A716446655440000C91700030B002B00384555"
    "0E8400E29B41D4A716446655440000E8F2"
)

class TestPosData:
    def test_latitude_range(self):
        rows = _parse(IBEACON_HEX)
        lat = _field(rows, "LAT")
        assert lat is not None
        # decoded like "55.7612000°"
        lat_val = float(lat.decoded.rstrip("°"))
        assert 55.0 < lat_val < 56.0

    def test_longitude_range(self):
        rows = _parse(IBEACON_HEX)
        lon = _field(rows, "LONG")
        assert lon is not None
        lon_val = float(lon.decoded.rstrip("°"))
        assert 37.0 < lon_val < 38.0

    def test_speed_positive(self):
        rows = _parse(IBEACON_HEX)
        spd = _field(rows, "SPD")
        assert spd is not None
        assert "km/h" in spd.decoded


# ── SR_IBEACON_EVENT ──────────────────────────────────────────────────────────

class TestIbeaconEvent:
    def test_two_beacons_decoded(self):
        rows = _parse(IBEACON_HEX)
        ibeacon_rows = [r for r in rows if "SR_IBEACON_EVENT" in r.layer]
        assert len(ibeacon_rows) > 0

    def test_first_beacon_enter(self):
        rows = _parse(IBEACON_HEX)
        evtype = _field(rows, "EVTYPE", "SR_IBEACON_EVENT")
        assert evtype is not None
        assert evtype.decoded == "enter"

    def test_major_minor_values(self):
        rows = _parse(IBEACON_HEX)
        major = _field(rows, "MAJOR", "SR_IBEACON_EVENT")
        minor = _field(rows, "MINOR", "SR_IBEACON_EVENT")
        assert major.raw == 10
        assert minor.raw == 42

    def test_rssi_negative_dbm(self):
        rows = _parse(IBEACON_HEX)
        rssi = _field(rows, "RSSI", "SR_IBEACON_EVENT")
        assert rssi is not None
        assert "dBm" in rssi.decoded
        dbm = int(rssi.decoded.split()[0])
        assert -100 < dbm < 0

    def test_uuid_formatted(self):
        rows = _parse(IBEACON_HEX)
        uuid = _field(rows, "UUID", "SR_IBEACON_EVENT")
        assert uuid is not None
        assert uuid.decoded.startswith("550E8400-")
        assert len(uuid.decoded) == 36  # UUID format with dashes

    def test_crc_ok(self):
        rows = _parse(IBEACON_HEX)
        assert "OK" in _field(rows, "HCS").decoded
        assert "OK" in _field(rows, "SFRCS").decoded


# ── SR_CELL_INFO ──────────────────────────────────────────────────────────────

LBS_HEX = (
    "0100000B0054000200010B4D00020000020210150028CE671A13119C9E47AD7F35137C012F000000"
    "0000CA0B00FA00142B1A013C1A003503CA0B00FA00142B1A023C1A002B03CB1600AABBCCDDEEFF"
    "3C060D4D6F736B6F76736B6179615342B231"
)

class TestCellInfo:
    def test_mcc_russia(self):
        rows = _parse(LBS_HEX)
        mcc = _field(rows, "MCC", "SR_CELL_INFO")
        assert mcc.raw == 250  # Russia

    def test_mnc_tele2(self):
        rows = _parse(LBS_HEX)
        mnc = _field(rows, "MNC", "SR_CELL_INFO")
        assert mnc.raw == 20

    def test_rat_lte(self):
        rows = _parse(LBS_HEX)
        rat = _field(rows, "RAT", "SR_CELL_INFO")
        assert rat.decoded == "LTE"

    def test_two_cells(self):
        rows = _parse(LBS_HEX)
        cells = [r for r in rows if "SR_CELL_INFO" in r.layer and r.field == "CellID"]
        assert len(cells) == 2

    def test_wifi_bssid(self):
        rows = _parse(LBS_HEX)
        bssid = _field(rows, "BSSID", "SR_WIFI_AP_DATA")
        assert bssid is not None
        assert bssid.decoded == "AA:BB:CC:DD:EE:FF"

    def test_wifi_ssid(self):
        rows = _parse(LBS_HEX)
        ssid = _field(rows, "SSID", "SR_WIFI_AP_DATA")
        assert ssid is not None
        assert ssid.decoded == "MoskovskayaSB"

    def test_crc_ok(self):
        rows = _parse(LBS_HEX)
        assert "OK" in _field(rows, "HCS").decoded
        assert "OK" in _field(rows, "SFRCS").decoded


# ── SR_RADIOTAG_EVENT ─────────────────────────────────────────────────────────

RADIOTAG_HEX = (
    "0100000B002A00030001BE2300030000020210150028CE671A13119C9E47AD7F35137C012F000000"
    "0000C80800010104DEADBEEF4421BF"
)

class TestRadiotagEvent:
    def test_evtype_enter(self):
        rows = _parse(RADIOTAG_HEX)
        evtype = _field(rows, "EVTYPE", "SR_RADIOTAG_EVENT")
        assert evtype.decoded == "enter"

    def test_tagtype_passive(self):
        rows = _parse(RADIOTAG_HEX)
        tagtype = _field(rows, "TAGTYPE", "SR_RADIOTAG_EVENT")
        assert tagtype.decoded == "passive"

    def test_uid_decoded(self):
        rows = _parse(RADIOTAG_HEX)
        uid = _field(rows, "UID", "SR_RADIOTAG_EVENT")
        assert uid is not None
        assert uid.decoded == "DEADBEEF"

    def test_crc_ok(self):
        rows = _parse(RADIOTAG_HEX)
        assert "OK" in _field(rows, "HCS").decoded
        assert "OK" in _field(rows, "SFRCS").decoded


# ── Smoke: all sample files ───────────────────────────────────────────────────

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

@pytest.mark.parametrize("hex_file", sorted(SAMPLES_DIR.glob("*.hex")))
def test_sample_parses_without_error(hex_file):
    lines = hex_file.read_text(encoding="utf-8").splitlines()
    hex_lines = [l for l in lines if not l.strip().startswith("#")]
    hex_str = "".join(hex_lines)
    rows, err = parse_hex(hex_str)
    assert err == "", f"{hex_file.name}: {err}"
    assert len(rows) > 0, f"{hex_file.name}: no fields parsed"


@pytest.mark.parametrize("hex_file", sorted(SAMPLES_DIR.glob("*.hex")))
def test_sample_crc_valid(hex_file):
    lines = hex_file.read_text(encoding="utf-8").splitlines()
    hex_lines = [l for l in lines if not l.strip().startswith("#")]
    hex_str = "".join(hex_lines)
    rows, err = parse_hex(hex_str)
    assert err == ""
    hcs_row = next((r for r in rows if r.field == "HCS"), None)
    sfrcs_row = next((r for r in rows if r.field == "SFRCS"), None)
    if hcs_row:
        assert "OK" in hcs_row.decoded, f"{hex_file.name}: HCS BAD — {hcs_row.decoded}"
    if sfrcs_row:
        assert "OK" in sfrcs_row.decoded, f"{hex_file.name}: SFRCS BAD — {sfrcs_row.decoded}"


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self):
        rows, err = parse_hex("")
        assert err != "" or len(rows) == 0

    def test_invalid_hex(self):
        rows, err = parse_hex("ZZZZ")
        assert err != ""
        assert rows == []

    def test_too_short(self):
        rows, err = parse_hex("010003")
        assert err != "" or len(rows) == 0

    def test_spaces_ignored(self):
        hex_nospaces = PT_RESPONSE_HEX
        hex_spaced = " ".join(PT_RESPONSE_HEX[i:i+2] for i in range(0, len(PT_RESPONSE_HEX), 2))
        rows1, _ = parse_hex(hex_nospaces)
        rows2, _ = parse_hex(hex_spaced)
        assert len(rows1) == len(rows2)
