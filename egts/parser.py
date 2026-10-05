"""EGTS protocol parser/encoder — Python port of github.com/kuznetsovin/egts-protocol"""

import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Any, Tuple

EGTS_EPOCH = datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp()

PT_RESPONSE  = 0
PT_APPDATA   = 1
AUTH_SERVICE    = 1
TELEDATA_SERVICE = 2

SR_RECORD_RESPONSE    = 0
SR_TERM_IDENTITY      = 1
SR_MODULE_DATA        = 2
SR_DISPATCHER_IDENTITY = 5
SR_AUTH_INFO          = 7
SR_RESULT_CODE        = 9
SR_EGTSPLUS_DATA      = 15
SR_POS_DATA           = 16
SR_EXT_POS_DATA       = 17
SR_AD_SENSORS_DATA    = 18
SR_COUNTERS_DATA      = 19
SR_STATE_DATA_TYPE20  = 20   # len=5 → STATE, else ACCEL (not decoded)
SR_STATE_DATA         = 21
SR_LOOPIN_DATA        = 22
SR_ABS_DIG_SENS_DATA  = 23
SR_ABS_AN_SENS_DATA   = 24
SR_ABS_CNTR_DATA      = 25
SR_ABS_LOOPIN_DATA    = 26
SR_LIQUID_LEVEL       = 27
SR_PASSENGERS         = 28
SR_RADIOTAG_EVENT     = 200
SR_IBEACON_EVENT      = 201
SR_CELL_INFO          = 202
SR_WIFI_AP_DATA       = 203

SR_NAMES = {
    0: "SR_RECORD_RESPONSE", 1: "SR_TERM_IDENTITY", 2: "SR_MODULE_DATA",
    5: "SR_DISPATCHER_IDENTITY", 7: "SR_AUTH_INFO", 9: "SR_RESULT_CODE",
    15: "SR_EGTSPLUS_DATA", 16: "SR_POS_DATA", 17: "SR_EXT_POS_DATA",
    18: "SR_AD_SENSORS_DATA", 19: "SR_COUNTERS_DATA", 20: "SR_STATE/ACCEL",
    21: "SR_STATE_DATA", 22: "SR_LOOPIN_DATA", 23: "SR_ABS_DIG_SENS",
    24: "SR_ABS_AN_SENS", 25: "SR_ABS_CNTR_DATA", 26: "SR_ABS_LOOPIN",
    27: "SR_LIQUID_LEVEL", 28: "SR_PASSENGERS",
    200: "SR_RADIOTAG_EVENT", 201: "SR_IBEACON_EVENT",
    202: "SR_CELL_INFO", 203: "SR_WIFI_AP_DATA",
}

SERVICE_NAMES = {1: "AUTH", 2: "TELEDATA"}
PT_NAMES = {0: "PT_RESPONSE", 1: "PT_APPDATA"}


# ── CRC ──────────────────────────────────────────────────────────────────────

def crc8(data: bytes) -> int:
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc

def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


# ── Field row (one row in the Excel table) ───────────────────────────────────

@dataclass
class FieldRow:
    layer: str          # e.g. "PACKET", "SDR[0]", "SDR[0] SR_POS_DATA"
    field: str          # field name
    offset: int         # byte offset in full packet
    size: int           # byte count
    hex_val: str        # uppercase hex, e.g. "01 00"
    raw: Any            # numeric / string raw value
    decoded: str        # human-readable decoded value
    desc: str           # description
    editable: bool = True


def _hex(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


# ── Subrecord decoders ────────────────────────────────────────────────────────

def _decode_pos_data(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    off = base
    if len(data) < 20:
        rows.append(FieldRow(layer, "RAW", off, len(data), _hex(data), data, "(too short)", False))
        return rows

    ntm_raw = struct.unpack_from("<I", data, 0)[0]
    ntm = datetime.fromtimestamp(EGTS_EPOCH + ntm_raw, tz=timezone.utc)
    rows.append(FieldRow(layer, "NTM", off,   4, _hex(data[0:4]),  ntm_raw, ntm.strftime("%Y-%m-%d %H:%M:%S UTC"), True))
    off += 4

    lat_raw = struct.unpack_from("<I", data, 4)[0]
    lat = lat_raw * 90 / 0xFFFFFFFF
    rows.append(FieldRow(layer, "LAT", off,   4, _hex(data[4:8]),  lat_raw, f"{lat:.7f}°", True))
    off += 4

    lon_raw = struct.unpack_from("<I", data, 8)[0]
    lon = lon_raw * 180 / 0xFFFFFFFF
    rows.append(FieldRow(layer, "LONG", off,  4, _hex(data[8:12]), lon_raw, f"{lon:.7f}°", True))
    off += 4

    flags = data[12]
    fb = f"{flags:08b}"
    alte  = fb[0]; lohs = fb[1]; lahs = fb[2]; mv = fb[3]
    bb    = fb[4]; cs   = fb[5]; fix  = fb[6]; vld = fb[7]
    lat_dir = "S" if lahs == "1" else "N"
    lon_dir = "W" if lohs == "1" else "E"
    rows.append(FieldRow(layer, "FLAGS", off, 1, _hex(data[12:13]), flags,
        f"ALTE={alte} LOHS={lohs}({lon_dir}) LAHS={lahs}({lat_dir}) MV={mv} BB={bb} CS={cs} FIX={fix} VLD={vld}", True))
    off += 1

    spd_raw = struct.unpack_from("<H", data, 13)[0]
    dirh = (spd_raw >> 15) & 1
    alts = (spd_raw >> 14) & 1
    speed_01 = spd_raw & 0x3FFF
    speed_kmh = speed_01 / 10.0
    rows.append(FieldRow(layer, "SPD", off,   2, _hex(data[13:15]), spd_raw,
        f"{speed_kmh:.1f} km/h  DIRH={dirh} ALTS={alts}", True))
    off += 2

    dir_raw = data[15]
    direction = dir_raw | (dirh << 7)
    rows.append(FieldRow(layer, "DIR", off,   1, _hex(data[15:16]), dir_raw, f"{direction}°", True))
    off += 1

    odm_bytes = data[16:19] + b"\x00"
    odm = struct.unpack_from("<I", odm_bytes)[0]
    rows.append(FieldRow(layer, "ODM", off,   3, _hex(data[16:19]), odm, f"{odm} km", True))
    off += 3

    din = data[19]
    rows.append(FieldRow(layer, "DIN", off,   1, _hex(data[19:20]), din, f"{din:08b}", True))
    off += 1

    src = data[20]
    rows.append(FieldRow(layer, "SRC", off,   1, _hex(data[20:21]), src, str(src), True))
    off += 1

    if alte == "1" and len(data) >= 24:
        alt_bytes = data[21:24] + b"\x00"
        alt = struct.unpack_from("<I", alt_bytes)[0]
        alt_sign = "+" if alts == 0 else "-"
        rows.append(FieldRow(layer, "ALT", off, 3, _hex(data[21:24]), alt, f"{alt_sign}{alt} m", True))

    return rows


def _decode_ext_pos_data(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    off = base
    if not data:
        return rows
    flags = data[0]
    fb = f"{flags:08b}"
    nsfe = fb[3]; sfe = fb[4]; pfe = fb[5]; hfe = fb[6]; vfe = fb[7]
    rows.append(FieldRow(layer, "FLAGS", off, 1, _hex(data[0:1]), flags,
        f"NSFE={nsfe} SFE={sfe} PFE={pfe} HFE={hfe} VFE={vfe}", True))
    off += 1; pos = 1

    if vfe == "1" and len(data) >= pos + 2:
        v = struct.unpack_from("<H", data, pos)[0]
        rows.append(FieldRow(layer, "VDOP", off, 2, _hex(data[pos:pos+2]), v, str(v), True))
        off += 2; pos += 2
    if hfe == "1" and len(data) >= pos + 2:
        v = struct.unpack_from("<H", data, pos)[0]
        rows.append(FieldRow(layer, "HDOP", off, 2, _hex(data[pos:pos+2]), v, str(v), True))
        off += 2; pos += 2
    if pfe == "1" and len(data) >= pos + 2:
        v = struct.unpack_from("<H", data, pos)[0]
        rows.append(FieldRow(layer, "PDOP", off, 2, _hex(data[pos:pos+2]), v, str(v), True))
        off += 2; pos += 2
    if sfe == "1" and len(data) >= pos + 1:
        v = data[pos]
        rows.append(FieldRow(layer, "SAT", off, 1, _hex(data[pos:pos+1]), v, f"{v} satellites", True))
        off += 1; pos += 1
    if nsfe == "1" and len(data) >= pos + 2:
        v = struct.unpack_from("<H", data, pos)[0]
        ns_str = ""
        if v & 0x0001: ns_str += "GLONASS "
        if v & 0x0002: ns_str += "GPS "
        if v & 0x0004: ns_str += "GALILEO "
        rows.append(FieldRow(layer, "NS", off, 2, _hex(data[pos:pos+2]), v, ns_str.strip() or str(v), True))
    return rows


def _decode_state_data(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 5:
        return rows
    off = base
    rows.append(FieldRow(layer, "ST",   off, 1, _hex(data[0:1]), data[0], f"state={data[0]}", True)); off+=1
    rows.append(FieldRow(layer, "MPSV", off, 1, _hex(data[1:2]), data[1], f"{data[1]*0.1:.1f} V", True)); off+=1
    rows.append(FieldRow(layer, "BBV",  off, 1, _hex(data[2:3]), data[2], f"{data[2]*0.1:.1f} V", True)); off+=1
    rows.append(FieldRow(layer, "IBV",  off, 1, _hex(data[3:4]), data[3], f"{data[3]*0.1:.1f} V", True)); off+=1
    flags = data[4]
    fb = f"{flags:08b}"
    rows.append(FieldRow(layer, "FLAGS", off, 1, _hex(data[4:5]), flags,
        f"NMS={fb[5]} IBU={fb[6]} BBU={fb[7]}", True))
    return rows


def _decode_ad_sensors(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 3:
        return rows
    off = base
    dioe = data[0]
    fb = f"{dioe:08b}"
    rows.append(FieldRow(layer, "DIOE", off, 1, _hex(data[0:1]), dioe,
        f"DIO exists (bits 8..1): {fb}", True)); off += 1

    dout = data[1]
    rows.append(FieldRow(layer, "DOUT", off, 1, _hex(data[1:2]), dout, f"{dout:08b}", True)); off += 1

    asfe = data[2]
    fb2 = f"{asfe:08b}"
    rows.append(FieldRow(layer, "ASFE", off, 1, _hex(data[2:3]), asfe,
        f"ANS exists (bits 8..1): {fb2}", True)); off += 1

    pos = 3
    for i in range(8):
        if (dioe >> i) & 1:
            if pos < len(data):
                v = data[pos]
                rows.append(FieldRow(layer, f"ADIO{i+1}", off, 1, _hex(data[pos:pos+1]), v, f"{v:08b}", True))
                off += 1; pos += 1

    for i in range(8):
        if (asfe >> i) & 1:
            if pos + 3 <= len(data):
                raw = data[pos:pos+3] + b"\x00"
                v = struct.unpack_from("<I", raw)[0]
                rows.append(FieldRow(layer, f"ANS{i+1}", off, 3, _hex(data[pos:pos+3]), v, str(v), True))
                off += 3; pos += 3
    return rows


def _decode_counters(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if not data:
        return rows
    off = base
    cfe = data[0]
    fb = f"{cfe:08b}"
    rows.append(FieldRow(layer, "CFE", off, 1, _hex(data[0:1]), cfe,
        f"Counter exists (bits 8..1): {fb}", True)); off += 1
    pos = 1
    for i in range(8):
        if (cfe >> i) & 1:
            if pos + 3 <= len(data):
                raw = data[pos:pos+3] + b"\x00"
                v = struct.unpack_from("<I", raw)[0]
                rows.append(FieldRow(layer, f"CN{i+1}", off, 3, _hex(data[pos:pos+3]), v, str(v), True))
                off += 3; pos += 3
    return rows


def _decode_liquid_level(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 1:
        return rows
    off = base
    flags = data[0]
    fb = f"{flags:08b}"
    mlcd = int(fb[5:8], 2)
    rows.append(FieldRow(layer, "FLAGS", off, 1, _hex(data[0:1]), flags,
        f"RLS={fb[0]} IVE={fb[1]} LLE={fb[2]} RLT={fb[3]} MTSF={fb[4]} MCLS={mlcd}", True)); off += 1

    if len(data) >= 5:
        v = struct.unpack_from("<I", data, 1)[0]
        rows.append(FieldRow(layer, "LLS", off, 4, _hex(data[1:5]), v, str(v), True))
    return rows


def _decode_term_identity(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 5:
        return rows
    off = base
    tid = struct.unpack_from("<I", data, 0)[0]
    rows.append(FieldRow(layer, "TID", off, 4, _hex(data[0:4]), tid, str(tid), True)); off += 4
    flags = data[4]
    fb = f"{flags:08b}"
    rows.append(FieldRow(layer, "FLAGS", off, 1, _hex(data[4:5]), flags,
        f"MNE={fb[0]} BSE={fb[1]} NIDE={fb[2]} SSRA={fb[3]} LNGCE={fb[4]} IMSIE={fb[5]} IMEIE={fb[6]} HDIDE={fb[7]}", True))
    off += 1; pos = 5
    # Optional fields
    if fb[7] == "1" and pos + 2 <= len(data):
        v = struct.unpack_from("<H", data, pos)[0]
        rows.append(FieldRow(layer, "HDID", off, 2, _hex(data[pos:pos+2]), v, str(v), True))
        off += 2; pos += 2
    if fb[6] == "1" and pos + 15 <= len(data):
        v = data[pos:pos+15].decode("latin-1", errors="replace")
        rows.append(FieldRow(layer, "IMEI", off, 15, _hex(data[pos:pos+15]), v, v, True))
        off += 15; pos += 15
    if fb[5] == "1" and pos + 16 <= len(data):
        v = data[pos:pos+16].decode("latin-1", errors="replace")
        rows.append(FieldRow(layer, "IMSI", off, 16, _hex(data[pos:pos+16]), v, v, True))
        off += 16; pos += 16
    return rows


def _decode_result_code(data: bytes, base: int, layer: str) -> List[FieldRow]:
    if not data:
        return []
    codes = {0:"EGTS_PC_OK", 128:"EGTS_PC_UNS_PROTOCOL", 138:"EGTS_PC_HEADERCRC_ERROR",
             139:"EGTS_PC_DATACRC_ERROR", 150:"EGTS_PC_INVDATALEN",
             163:"EGTS_PC_ALREADY_EXISTS", 165:"EGTS_PC_ID_NFOUND"}
    v = data[0]
    return [FieldRow(layer, "RCD", base, 1, _hex(data[0:1]), v,
                     codes.get(v, f"code={v}"), True)]


def _decode_sr_response(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 3:
        return rows
    off = base
    crn = struct.unpack_from("<H", data, 0)[0]
    rows.append(FieldRow(layer, "CRN", off, 2, _hex(data[0:2]), crn, f"confirms record #{crn}", True)); off += 2
    rst = data[2]
    rows.append(FieldRow(layer, "RST", off, 1, _hex(data[2:3]), rst,
        {0:"OK"}.get(rst, f"code={rst}"), True))
    return rows


def _decode_abs_an_sens(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 4:
        return rows
    off = base
    n = data[0]
    rows.append(FieldRow(layer, "ASN", off, 1, _hex(data[0:1]), n, f"sensor #{n}", True)); off += 1
    v = struct.unpack_from("<I", data[1:4] + b"\x00")[0]
    rows.append(FieldRow(layer, "ASV", off, 3, _hex(data[1:4]), v, str(v), True))
    return rows


def _decode_abs_cntr(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 4:
        return rows
    off = base
    n = data[0]
    rows.append(FieldRow(layer, "CN", off, 1, _hex(data[0:1]), n, f"counter #{n}", True)); off += 1
    v = struct.unpack_from("<I", data[1:4] + b"\x00")[0]
    rows.append(FieldRow(layer, "CNV", off, 3, _hex(data[1:4]), v, str(v), True))
    return rows


def _decode_dispatcher_identity(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 5:
        return rows
    off = base
    dt = data[0]
    rows.append(FieldRow(layer, "DT", off, 1, _hex(data[0:1]), dt, str(dt), True)); off += 1
    did = struct.unpack_from("<I", data, 1)[0]
    rows.append(FieldRow(layer, "DID", off, 4, _hex(data[1:5]), did, str(did), True))
    return rows


_EVTYPE_NAMES = {1: "enter", 2: "exit", 3: "periodic"}
_RAT_NAMES    = {1: "GSM", 2: "UMTS", 3: "LTE", 4: "NR"}
_TAGTYPE_NAMES = {1: "passive", 2: "active"}


def _decode_ibeacon_event(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 23:
        return [FieldRow(layer, "RAW", base, len(data), _hex(data), data, "(too short)", False)]
    evtype = data[0]
    rows.append(FieldRow(layer, "EVTYPE", base,   1, _hex(data[0:1]), evtype,
        _EVTYPE_NAMES.get(evtype, str(evtype)), True))
    major = struct.unpack_from("<H", data, 1)[0]
    rows.append(FieldRow(layer, "MAJOR", base+1,  2, _hex(data[1:3]), major, str(major), True))
    minor = struct.unpack_from("<H", data, 3)[0]
    rows.append(FieldRow(layer, "MINOR", base+3,  2, _hex(data[3:5]), minor, str(minor), True))
    rssi = data[5] - 128
    rows.append(FieldRow(layer, "RSSI",  base+5,  1, _hex(data[5:6]), data[5], f"{rssi} dBm", True))
    txpwr = data[6] - 128
    rows.append(FieldRow(layer, "TXPWR", base+6,  1, _hex(data[6:7]), data[6], f"{txpwr} dBm", True))
    uuid_hex = data[7:23].hex().upper()
    uuid_str = (f"{uuid_hex[0:8]}-{uuid_hex[8:12]}-{uuid_hex[12:16]}"
                f"-{uuid_hex[16:20]}-{uuid_hex[20:32]}")
    rows.append(FieldRow(layer, "UUID",  base+7, 16, _hex(data[7:23]), uuid_hex, uuid_str, True))
    return rows


def _decode_radiotag_event(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 4:
        return [FieldRow(layer, "RAW", base, len(data), _hex(data), data, "(too short)", False)]
    evtype = data[0]
    rows.append(FieldRow(layer, "EVTYPE",  base,   1, _hex(data[0:1]), evtype,
        _EVTYPE_NAMES.get(evtype, str(evtype)), True))
    tagtype = data[1]
    rows.append(FieldRow(layer, "TAGTYPE", base+1, 1, _hex(data[1:2]), tagtype,
        _TAGTYPE_NAMES.get(tagtype, str(tagtype)), True))
    uidlen = data[2]
    rows.append(FieldRow(layer, "UIDLEN",  base+2, 1, _hex(data[2:3]), uidlen, str(uidlen), False))
    uid = data[3:3+uidlen]
    rows.append(FieldRow(layer, "UID",     base+3, uidlen, _hex(uid), uid.hex().upper(),
        uid.hex().upper(), True))
    if len(data) >= 3 + uidlen + 1:
        rssi = data[3+uidlen] - 128
        rows.append(FieldRow(layer, "RSSI", base+3+uidlen, 1,
            _hex(data[3+uidlen:4+uidlen]), data[3+uidlen], f"{rssi} dBm", True))
    return rows


def _decode_cell_info(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 11:
        return [FieldRow(layer, "RAW", base, len(data), _hex(data), data, "(too short)", False)]
    mcc = struct.unpack_from("<H", data, 0)[0]
    rows.append(FieldRow(layer, "MCC",    base,    2, _hex(data[0:2]), mcc, str(mcc), True))
    mnc = data[2]
    rows.append(FieldRow(layer, "MNC",    base+2,  1, _hex(data[2:3]), mnc, str(mnc), True))
    lac = struct.unpack_from("<H", data, 3)[0]
    rows.append(FieldRow(layer, "LAC",    base+3,  2, _hex(data[3:5]), lac, f"0x{lac:04X}", True))
    cell_id = struct.unpack_from("<I", data, 5)[0]
    rows.append(FieldRow(layer, "CellID", base+5,  4, _hex(data[5:9]), cell_id,
        f"0x{cell_id:08X}", True))
    rssi = data[9] - 128
    rows.append(FieldRow(layer, "RSSI",   base+9,  1, _hex(data[9:10]), data[9],
        f"{rssi} dBm", True))
    rat = data[10]
    rows.append(FieldRow(layer, "RAT",    base+10, 1, _hex(data[10:11]), rat,
        _RAT_NAMES.get(rat, str(rat)), True))
    return rows


def _decode_wifi_ap_data(data: bytes, base: int, layer: str) -> List[FieldRow]:
    rows = []
    if len(data) < 9:
        return [FieldRow(layer, "RAW", base, len(data), _hex(data), data, "(too short)", False)]
    bssid = data[0:6]
    bssid_str = ":".join(f"{b:02X}" for b in bssid)
    rows.append(FieldRow(layer, "BSSID",   base,   6, _hex(bssid), bssid.hex().upper(),
        bssid_str, True))
    rssi = data[6] - 128
    rows.append(FieldRow(layer, "RSSI",    base+6, 1, _hex(data[6:7]), data[6],
        f"{rssi} dBm", True))
    channel = data[7]
    rows.append(FieldRow(layer, "CHANNEL", base+7, 1, _hex(data[7:8]), channel,
        str(channel) if channel else "N/A", True))
    ssidlen = data[8]
    rows.append(FieldRow(layer, "SSIDLEN", base+8, 1, _hex(data[8:9]), ssidlen,
        str(ssidlen), False))
    if ssidlen and len(data) >= 9 + ssidlen:
        ssid_bytes = data[9:9+ssidlen]
        ssid_str = ssid_bytes.decode("utf-8", errors="replace")
        rows.append(FieldRow(layer, "SSID",  base+9, ssidlen, _hex(ssid_bytes),
            ssid_str, ssid_str, True))
    return rows


def _decode_subrecord_raw(data: bytes, base: int, layer: str) -> List[FieldRow]:
    return [FieldRow(layer, "RAW", base, len(data), _hex(data), data.hex().upper(), "(not decoded)", False)]


# ── PT_RESPONSE decoder ───────────────────────────────────────────────────────

def _decode_pt_response(data: bytes, base: int) -> List[FieldRow]:
    rows = []
    layer = "PT_RESPONSE"
    if len(data) < 3:
        return rows
    off = base
    rpid = struct.unpack_from("<H", data, 0)[0]
    rows.append(FieldRow(layer, "RPID", off, 2, _hex(data[0:2]), rpid,
        f"response to packet #{rpid}", True)); off += 2
    pr = data[2]
    rows.append(FieldRow(layer, "PR", off, 1, _hex(data[2:3]), pr,
        {0:"EGTS_PC_OK"}.get(pr, f"code={pr}"), True)); off += 3 - 2  # off already advanced by 2
    off = base + 3
    # optional SDR
    if len(data) > 3:
        rows += _decode_service_data_set(data[3:], off)
    return rows


# ── Service Data Set decoder ──────────────────────────────────────────────────

def _decode_service_data_set(data: bytes, base: int) -> List[FieldRow]:
    rows = []
    pos = 0
    sdr_idx = 0
    while pos < len(data):
        if pos + 5 > len(data):
            break
        rl = struct.unpack_from("<H", data, pos)[0]
        rn = struct.unpack_from("<H", data, pos + 2)[0]
        flags = data[pos + 4]
        fb = f"{flags:08b}"
        ssod = fb[0]; rsod = fb[1]; grp = fb[2]; rpp = fb[3:5]
        tmfe = fb[5]; evfe = fb[6]; obfe = fb[7]

        layer = f"SDR[{sdr_idx}]"
        off = base + pos

        rows.append(FieldRow(layer, "RL",    off,   2, _hex(data[pos:pos+2]),     rl, f"{rl} bytes", False))
        rows.append(FieldRow(layer, "RN",    off+2, 2, _hex(data[pos+2:pos+4]),   rn, f"record #{rn}", True))
        rows.append(FieldRow(layer, "FLAGS", off+4, 1, _hex(data[pos+4:pos+5]), flags,
            f"SSOD={ssod} RSOD={rsod} GRP={grp} RPP={rpp} TMFE={tmfe} EVFE={evfe} OBFE={obfe}", True))
        pos += 5; off += 5

        if obfe == "1":
            if pos + 4 > len(data): break
            oid = struct.unpack_from("<I", data, pos)[0]
            rows.append(FieldRow(layer, "OID", off, 4, _hex(data[pos:pos+4]), oid, str(oid), True))
            pos += 4; off += 4

        if evfe == "1":
            if pos + 4 > len(data): break
            evid = struct.unpack_from("<I", data, pos)[0]
            rows.append(FieldRow(layer, "EVID", off, 4, _hex(data[pos:pos+4]), evid, str(evid), True))
            pos += 4; off += 4

        if tmfe == "1":
            if pos + 4 > len(data): break
            tm_raw = struct.unpack_from("<I", data, pos)[0]
            tm = datetime.fromtimestamp(EGTS_EPOCH + tm_raw, tz=timezone.utc)
            rows.append(FieldRow(layer, "TM", off, 4, _hex(data[pos:pos+4]), tm_raw,
                tm.strftime("%Y-%m-%d %H:%M:%S UTC"), True))
            pos += 4; off += 4

        if pos + 2 > len(data): break
        sst = data[pos]; rst = data[pos+1]
        rows.append(FieldRow(layer, "SST", off,   1, _hex(data[pos:pos+1]),   sst,
            SERVICE_NAMES.get(sst, str(sst)), True))
        rows.append(FieldRow(layer, "RST", off+1, 1, _hex(data[pos+1:pos+2]), rst,
            SERVICE_NAMES.get(rst, str(rst)), True))
        pos += 2; off += 2

        # Record data set
        rd_end = pos + rl
        while pos < rd_end and pos + 3 <= len(data):
            srt = data[pos]
            srl = struct.unpack_from("<H", data, pos+1)[0]
            sr_layer = f"SDR[{sdr_idx}] {SR_NAMES.get(srt, f'SR_{srt}')}"
            rows.append(FieldRow(sr_layer, "SRT", off, 1, _hex(data[pos:pos+1]), srt,
                SR_NAMES.get(srt, f"type {srt}"), False))
            rows.append(FieldRow(sr_layer, "SRL", off+1, 2, _hex(data[pos+1:pos+3]), srl,
                f"{srl} bytes", False))
            pos += 3; off += 3
            sr_data = data[pos:pos+srl]

            if srt == SR_POS_DATA:
                rows += _decode_pos_data(sr_data, off, sr_layer)
            elif srt == SR_EXT_POS_DATA:
                rows += _decode_ext_pos_data(sr_data, off, sr_layer)
            elif srt == SR_STATE_DATA or (srt == SR_STATE_DATA_TYPE20 and srl == 5):
                rows += _decode_state_data(sr_data, off, sr_layer)
            elif srt == SR_AD_SENSORS_DATA:
                rows += _decode_ad_sensors(sr_data, off, sr_layer)
            elif srt == SR_COUNTERS_DATA:
                rows += _decode_counters(sr_data, off, sr_layer)
            elif srt == SR_LIQUID_LEVEL:
                rows += _decode_liquid_level(sr_data, off, sr_layer)
            elif srt == SR_TERM_IDENTITY:
                rows += _decode_term_identity(sr_data, off, sr_layer)
            elif srt == SR_RESULT_CODE:
                rows += _decode_result_code(sr_data, off, sr_layer)
            elif srt == SR_RECORD_RESPONSE:
                rows += _decode_sr_response(sr_data, off, sr_layer)
            elif srt == SR_ABS_AN_SENS_DATA:
                rows += _decode_abs_an_sens(sr_data, off, sr_layer)
            elif srt == SR_ABS_CNTR_DATA:
                rows += _decode_abs_cntr(sr_data, off, sr_layer)
            elif srt == SR_DISPATCHER_IDENTITY:
                rows += _decode_dispatcher_identity(sr_data, off, sr_layer)
            elif srt == SR_IBEACON_EVENT:
                rows += _decode_ibeacon_event(sr_data, off, sr_layer)
            elif srt == SR_RADIOTAG_EVENT:
                rows += _decode_radiotag_event(sr_data, off, sr_layer)
            elif srt == SR_CELL_INFO:
                rows += _decode_cell_info(sr_data, off, sr_layer)
            elif srt == SR_WIFI_AP_DATA:
                rows += _decode_wifi_ap_data(sr_data, off, sr_layer)
            else:
                rows += _decode_subrecord_raw(sr_data, off, sr_layer)

            pos += srl; off += srl

        sdr_idx += 1

    return rows


# ── Main packet decoder ───────────────────────────────────────────────────────

def decode_packet(raw: bytes) -> Tuple[List[FieldRow], str]:
    """Returns (field_rows, error_message). error_message is "" on success."""
    rows: List[FieldRow] = []

    if len(raw) < 11:
        return rows, "Packet too short (< 11 bytes)"

    layer = "PACKET"
    off = 0

    prv = raw[0]
    rows.append(FieldRow(layer, "PRV",  0, 1, _hex(raw[0:1]),  prv, f"version {prv}", True))

    skid = raw[1]
    rows.append(FieldRow(layer, "SKID", 1, 1, _hex(raw[1:2]), skid, str(skid), True))

    flags = raw[2]
    fb = f"{flags:08b}"
    prf = fb[0:2]; rte = fb[2]; ena = fb[3:5]; cmp = fb[5]; pr = fb[6:8]
    rows.append(FieldRow(layer, "FLAGS", 2, 1, _hex(raw[2:3]), flags,
        f"PRF={prf} RTE={rte} ENA={ena} CMP={cmp} PR={pr}", True))

    hl = raw[3]
    rows.append(FieldRow(layer, "HL",  3, 1, _hex(raw[3:4]), hl, f"{hl} bytes", False))

    he = raw[4]
    rows.append(FieldRow(layer, "HE",  4, 1, _hex(raw[4:5]), he, str(he), True))

    fdl = struct.unpack_from("<H", raw, 5)[0]
    rows.append(FieldRow(layer, "FDL", 5, 2, _hex(raw[5:7]), fdl, f"{fdl} bytes", False))

    pid = struct.unpack_from("<H", raw, 7)[0]
    rows.append(FieldRow(layer, "PID", 7, 2, _hex(raw[7:9]), pid, f"packet #{pid}", True))

    pt = raw[9]
    rows.append(FieldRow(layer, "PT",  9, 1, _hex(raw[9:10]), pt,
        PT_NAMES.get(pt, f"unknown {pt}"), True))

    off = 10
    if rte == "1":
        if hl < 16 or len(raw) < 16:
            return rows, "Route flag set but packet too short for PRA/RCA/TTL"
        pra = struct.unpack_from("<H", raw, 10)[0]
        rca = struct.unpack_from("<H", raw, 12)[0]
        ttl = raw[14]
        rows.append(FieldRow(layer, "PRA", 10, 2, _hex(raw[10:12]), pra, str(pra), True))
        rows.append(FieldRow(layer, "RCA", 12, 2, _hex(raw[12:14]), rca, str(rca), True))
        rows.append(FieldRow(layer, "TTL", 14, 1, _hex(raw[14:15]), ttl, str(ttl), True))
        off = 15

    hcs = raw[off]
    expected_hcs = crc8(raw[:off])
    hcs_ok = "OK" if hcs == expected_hcs else f"BAD (expected {expected_hcs:02X})"
    rows.append(FieldRow(layer, "HCS", off, 1, _hex(raw[off:off+1]), hcs,
        f"{hcs:02X} [{hcs_ok}]", False))
    off += 1  # now off == hl

    if fdl == 0:
        return rows, ""

    sfrd_start = hl
    sfrd_end = hl + fdl
    if len(raw) < sfrd_end + 2:
        return rows, f"Packet truncated: need {sfrd_end+2} bytes, have {len(raw)}"

    sfrd = raw[sfrd_start:sfrd_end]
    sfrcs = struct.unpack_from("<H", raw, sfrd_end)[0]
    expected_sfrcs = crc16(sfrd)
    sfrcs_ok = "OK" if sfrcs == expected_sfrcs else f"BAD (expected {expected_sfrcs:04X})"
    rows.append(FieldRow(layer, "SFRCS", sfrd_end, 2, _hex(raw[sfrd_end:sfrd_end+2]),
        sfrcs, f"{sfrcs:04X} [{sfrcs_ok}]", False))

    if pt == PT_RESPONSE:
        rows += _decode_pt_response(sfrd, sfrd_start)
    elif pt == PT_APPDATA:
        rows += _decode_service_data_set(sfrd, sfrd_start)
    else:
        rows.append(FieldRow("SFRD", "RAW", sfrd_start, fdl, _hex(sfrd),
            sfrd.hex().upper(), f"unknown packet type {pt}", False))

    return rows, ""


def parse_hex(hex_str: str) -> Tuple[List[FieldRow], str]:
    """Parse a hex string (spaces optional) into field rows."""
    cleaned = hex_str.replace(" ", "").replace("\n", "").replace("\r", "")
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as e:
        return [], f"Invalid hex: {e}"
    return decode_packet(raw)


# ── Encoder (fields → bytes) ──────────────────────────────────────────────────

def encode_packet(fields: dict) -> Tuple[bytes, str]:
    """
    Encode a packet from a flat dict of overridden field values.
    fields keys match FieldRow.field at the PACKET layer.
    Returns (raw_bytes, error). This rebuilds a packet from its
    top-level header fields only; SFRD is passed as-is from fields["SFRD_RAW"].
    """
    try:
        prv  = int(fields.get("PRV", 1))
        skid = int(fields.get("SKID", 0))
        pid  = int(fields.get("PID", 0))
        pt   = int(fields.get("PT", 1))

        flags_val = int(fields.get("FLAGS_raw", 0))
        rte = (flags_val >> 5) & 1

        sfrd_hex = fields.get("SFRD_RAW", "")
        sfrd = bytes.fromhex(sfrd_hex.replace(" ", "")) if sfrd_hex else b""

        hl = 16 if rte else 11
        buf = bytearray()
        buf += bytes([prv, skid, flags_val, hl, 0])
        buf += struct.pack("<H", len(sfrd))
        buf += struct.pack("<H", pid)
        buf += bytes([pt])
        if rte:
            pra = int(fields.get("PRA", 0))
            rca = int(fields.get("RCA", 0))
            ttl = int(fields.get("TTL", 0))
            buf += struct.pack("<H", pra)
            buf += struct.pack("<H", rca)
            buf += bytes([ttl])
        buf += bytes([crc8(bytes(buf))])
        buf += sfrd
        if sfrd:
            buf += struct.pack("<H", crc16(sfrd))
        return bytes(buf), ""
    except Exception as e:
        return b"", str(e)


if __name__ == "__main__":
    import sys
    hex_input = sys.argv[1] if len(sys.argv) > 1 else \
        "0100000B00B100E80401" \
        "4EA600A10A8134F6E9010202101A004F5FE51000BECD9E" \
        "807F8B35939B802FF98002010092000000001106000E460000000C121C00010FFF01446D00B800" \
        "000B010000000000000000000000000000000014050002FF0029041B070000FF00000000001B07" \
        "00020000000000001B07000301005A0800001B07000402000000000019040064772A0419040065" \
        "0000001904006601000019040067772A0419040068772A04190400694F9A221904006E772A0441F6"

    rows, err = parse_hex(hex_input)
    if err:
        print(f"Error: {err}")
        sys.exit(1)
    print(f"{'Layer':<35} {'Field':<8} {'Off':>4} {'Sz':>3}  {'Hex':<24}  {'Decoded'}")
    print("-" * 100)
    for r in rows:
        print(f"{r.layer:<35} {r.field:<8} {r.offset:>4}  {r.size:>2}  {r.hex_val:<24}  {r.decoded}")
