"""
Generate annotated .hex sample files in samples/.

Run from project root:
    python samples/generate.py

Each file is a self-describing hex packet with metadata comments
that can be pasted directly into the Excel analyzer.
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from egts import parse_hex
from egts.parser import PT_NAMES, SR_NAMES, SERVICE_NAMES

SAMPLES_DIR = Path(__file__).parent


def fmt_hex(hex_str: str, bytes_per_group: int = 4, groups_per_line: int = 4) -> str:
    """Format hex string as 'XX XX XX XX  XX XX XX XX' with newlines."""
    raw = bytes.fromhex(hex_str.replace(" ", ""))
    bpl = bytes_per_group * groups_per_line
    lines = []
    for i in range(0, len(raw), bpl):
        chunk = raw[i:i+bpl]
        groups = [" ".join(f"{b:02X}" for b in chunk[j:j+bytes_per_group])
                  for j in range(0, len(chunk), bytes_per_group)]
        lines.append("  ".join(groups))
    return "\n".join(lines)


def collect_meta(rows) -> dict:
    """Extract summary metadata from parsed FieldRows."""
    meta = {"pt": None, "services": set(), "subrecords": [], "sdrs": 0}
    sdr_seen = set()
    for r in rows:
        if r.layer == "PACKET":
            if r.field == "PT":
                meta["pt"] = r.decoded
        if r.layer.startswith("SDR[") and r.field == "SST":
            meta["services"].add(r.decoded)
        if r.field == "SRT":
            sr_name = SR_NAMES.get(r.raw, f"SR_{r.raw}")
            if sr_name not in meta["subrecords"]:
                meta["subrecords"].append(sr_name)
        # count distinct SDR indices
        if r.layer.startswith("SDR[") and r.field == "RL":
            idx = r.layer.split("[")[1].rstrip("]")
            sdr_seen.add(idx)
    meta["sdrs"] = len(sdr_seen)
    return meta


def write_hex_file(filename: str, hex_str: str, name: str, description: str, source: str = "test CSV"):
    clean = hex_str.replace(" ", "").upper()
    rows, err = parse_hex(clean)
    if err:
        print(f"  ERROR parsing {name}: {err}")
        return False

    meta = collect_meta(rows)
    total_bytes = len(clean) // 2

    svc_str = ", ".join(sorted(meta["services"])) or "—"
    sr_str = ", ".join(meta["subrecords"]) or "—"
    sdr_str = str(meta["sdrs"])

    sep = "# " + "─" * 68

    lines = [
        f"# EGTS Sample: {name}",
        sep,
        f"# {description}",
        "#",
        f"# Packet type : {meta['pt'] or '—'}",
        f"# SDR count   : {sdr_str}",
        f"# Services    : {svc_str}",
        f"# Subrecords  : {sr_str}",
        f"# Total bytes : {total_bytes}",
        f"# Source      : {source}",
        sep,
        "# Paste into EGTS_Analyzer.xlsx cell B2, then run ParsePacket (Alt-F8)",
        "#",
        fmt_hex(clean),
    ]

    path = SAMPLES_DIR / filename
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {path.name}  ({total_bytes} bytes, {len(rows)} fields)")
    return True


# ── Sample data ───────────────────────────────────────────────────────────────

PACKETS = [
    # filename, hex, name, description, source
    (
        "01_pt_response.hex",
        "0100030B0003008900004A15380033E8",
        "PT_RESPONSE",
        "Минимальный пакет PT_RESPONSE — подтверждение авторизации терминала.\n"
        "# Нет тела SFRD; CRC заголовка = 4A; SFRCS = E833.",
        "README example",
    ),
    (
        "02_term_identity.hex",
        "0100000B004800C0AD01423900143485860500004F5FE51002021015000F5EE510"
        "20181B9EB4DFDA341920825F0000000001110A001F0700060000001303001B0700"
        "010800C30600001B070002090003000000D82A",
        "TERM_IDENTITY",
        "PT_APPDATA, AUTH_SERVICE — запрос авторизации терминала.\n"
        "# Содержит SR_TERM_IDENTITY (TID, флаги) + дополнительные данные.",
        "egts_packages.csv:21",
    ),
    (
        "03_appdata_pos_telemetry.hex",
        "0100000B00B100E804014EA600A10A8134F6E9010202101A004F5FE51000BECD9E"
        "807F8B35939B802FF98002010092000000001106000E460000000C121C00010FFF"
        "01446D00B800000B010000000000000000000000000000000014050002FF002904"
        "1B070000FF00000000001B0700020000000000001B07000301005A0800001B0700"
        "0402000000000019040064772A04190400650000001904006601000019040067772A"
        "0419040068772A04190400694F9A221904006E772A0441F6",
        "APPDATA_TELEMETRY",
        "PT_APPDATA, TELEDATA_SERVICE — полная телематика с одним SDR.\n"
        "# Подзаписи: SR_POS_DATA (GPS), SR_EXT_POS_DATA (DOP/спутники),\n"
        "# SR_AD_SENSORS_DATA (цифр./аналог. входы), SR_COUNTERS_DATA,\n"
        "# SR_STATE_DATA (напряжения).",
        "egts_packages.csv:2",
    ),
    (
        "04_appdata_with_egtsplus.hex",
        "0100000B00CC0016000177C1003C00811108D1010202101A004E5FE51000BEC59E"
        "402FA0359355804F923C000100A7000000001106000E640000000C121C00010FFF"
        "0126340000000000000000000000000000000000000000000014050002870029041B"
        "070000FF00000000001B0700020000000000001B0700030100340300001B07000402"
        "0000000000190400646C62011904006500000019040066010000190400676C620119"
        "0400686C6201190400694E9A221904006E6C62010F180008ECC405154E9A225C2500"
        "00000082010208018A0102080176A6",
        "APPDATA_EGTSPLUS",
        "PT_APPDATA, TELEDATA_SERVICE — телематика + расширенные данные.\n"
        "# Подзаписи: SR_POS_DATA, SR_AD_SENSORS_DATA, SR_COUNTERS_DATA,\n"
        "# SR_STATE_DATA, SR_EGTSPLUS_DATA (тип 15, protobuf).\n"
        "# ПРИМЕЧАНИЕ: SR_EGTSPLUS_DATA отображается как RAW — protobuf не декодируется.",
        "egts_packages.csv:6",
    ),
    (
        "05_appdata_two_sdrs.hex",
        # CSV line 19 verbatim — DO NOT split across Python string lines
        "0100000B005E0179140163A4000200817F7206020202101A00335FE51008A92A9E7D7F88358300002F6833060000AD000000001104000A05000C121C00010FFF0000000000000000000000000000000000000000000000000014050002FF0029041B070000FF00000000001B0700020000000000001B07000301003B0200001B07000402000000000019040064FA9715190400650000001904006644850119040067FA971519040068FA971519040069339A221904006EFA9715A4000300817F7206020202101A00155FE51008A92A9E7D7F88358B00002F6833060000AD000000001104000A05000C121C00010FFF0000000000000000000000000000000000000000000000000014050002FF0029041B070000FF00000000001B0700020000000000001B07000301003B0200001B07000402000000000019040064F99715190400650100001904006644850119040067FA971519040068FA971519040069159A221904006EF99715E86E",
        "APPDATA_TWO_SDRS",
        "PT_APPDATA, TELEDATA_SERVICE — два SDR в одном пакете.\n"
        "# Одинаковые подзаписи, разные OID/RN — пример пакетной буферизации.",
        "egts_packages.csv:19",
    ),
    (
        "07_ibeacon_event.hex",
        "0100000B0053000100019A4C00010000020210150028CE671A13119C9E47AD7F35137C012F000000"
        "0000C91700010A002A003F45550E8400E29B41D4A716446655440000C91700030B002B00384555"
        "0E8400E29B41D4A716446655440000E8F2",
        "IBEACON_EVENT",
        "PT_APPDATA, TELEDATA_SERVICE — GPS-пакет с BLE iBeacon-событиями.\n"
        "# Подзаписи: SR_POS_DATA (v=38 км/ч), SR_IBEACON_EVENT×2 (вход+обновление).\n"
        "# Москва, остановка #42 и #43, UUID 550e8400-e29b-41d4-a716-446655440000.",
        "synthetic",
    ),
    (
        "08_lbs_cell_info.hex",
        "0100000B0054000200010B4D00020000020210150028CE671A13119C9E47AD7F35137C012F000000"
        "0000CA0B00FA00142B1A013C1A003503CA0B00FA00142B1A023C1A002B03CB1600AABBCCDDEEFF"
        "3C060D4D6F736B6F76736B6179615342B231",
        "LBS_CELL_INFO",
        "PT_APPDATA, TELEDATA_SERVICE — GPS + LBS + WiFi.\n"
        "# Подзаписи: SR_POS_DATA, SR_CELL_INFO×2 (обслуживающая+соседняя LTE сота),\n"
        "# SR_WIFI_AP_DATA (SSID=MoskovskayaSB, BSSID=AA:BB:CC:DD:EE:FF).\n"
        "# MCC=250 (Россия), MNC=20 (Tele2), LTE.",
        "synthetic",
    ),
    (
        "09_radiotag_event.hex",
        "0100000B002A00030001BE2300030000020210150028CE671A13119C9E47AD7F35137C012F000000"
        "0000C80800010104DEADBEEF4421BF",
        "RADIOTAG_EVENT",
        "PT_APPDATA, TELEDATA_SERVICE — GPS + событие пассивной радиометки.\n"
        "# Подзаписи: SR_POS_DATA, SR_RADIOTAG_EVENT (EVTYPE=enter, TAGTYPE=passive,\n"
        "# UID=DEADBEEF, RSSI=-68 dBm).",
        "synthetic",
    ),
    (
        "06_auth_with_sensors.hex",
        "0100000B008700DB920142780065C285000D00004F5FE51002021015004E5FE510"
        "E65F6B9E7730B23519ED800500000000011904006E8A06671904006F000000190400"
        "649207671904006500000019040066445C00190400678A0667190400689D176519"
        "040069 1D45151904006A1D4515110A001F0800070000000F03001B07000108000B"
        "0600001B070002090003000000B21A",
        "AUTH_WITH_SENSORS",
        "PT_APPDATA, AUTH_SERVICE — авторизация со счётчиками и ABS-сенсорами.\n"
        "# Подзаписи: SR_TERM_IDENTITY, SR_COUNTERS_DATA (ABS),\n"
        "# SR_ABS_AN_SENS_DATA, SR_ABS_CNTR_DATA.",
        "egts_packages.csv:24",
    ),
]


def main():
    print(f"Writing sample .hex files to {SAMPLES_DIR}/")
    ok = 0
    for args in PACKETS:
        if write_hex_file(*args):
            ok += 1
    print(f"\nDone: {ok}/{len(PACKETS)} samples written.")


if __name__ == "__main__":
    main()
