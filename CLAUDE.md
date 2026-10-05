# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**EGTS Analyzer** — bidirectional Excel analyzer for the EGTS protocol (GOST R 54619-2011).  
Reference Go parser: `C:\Users\sayr\Yandex.Disk\EGTS\egts-protocol`

## Commands

```bash
pip install openpyxl                    # install deps

python excel/create_workbook.py         # regenerate EGTS_Analyzer.xlsx + EGTSAnalyzer.bas
python egts_cli.py packet.txt out.csv   # parse hex file → CSV (called by VBA)
python -c "from egts import parse_hex; rows, err = parse_hex('01 00 ...')"
```

## Architecture

```
egts/                  Python package
  __init__.py          exports: parse_hex, encode_packet, FieldRow, crc8, crc16
  parser.py            all EGTS parsing/encoding logic
  cli.py               CLI logic (stdin/stdout bridge for VBA)

excel/
  create_workbook.py   generates EGTS_Analyzer.xlsx (5 sample sheets + Analyzer + Legend)

docs/
  TZ_EGTS_iBeacon_extended_additive_v17.docx   iBeacon subrecord spec
  TZ_EGTS_RTLS_v2.docx                          RTLS subrecord spec

egts_cli.py            root entry point: called by VBA via Shell(), delegates to egts.cli
EGTSAnalyzer.bas       VBA module (import into .xlsm via Alt-F11 → File → Import)
EGTS_Analyzer.xlsx     generated workbook (gitignored — run create_workbook.py to rebuild)
```

## EGTS Packet Layers

1. **PACKET** header: `PRV SKID FLAGS HL HE FDL PID PT [PRA RCA TTL] HCS`
2. **ServiceDataRecord** (SDR): `RL RN FLAGS [OID] [EVID] [TM] SST RST | RecordDataSet`
3. **RecordData** subrecord: `SRT SRL | SRD` — typed payload

## Encoding rules

- Time fields: seconds since 2010-01-01 UTC (uint32 LE)
- LAT: `uint32 = deg/90 × 0xFFFFFFFF`
- LONG: `uint32 = deg/180 × 0xFFFFFFFF`
- SPD: bits 13:0 = speed×10 (0.1 km/h), bit15=DIRH, bit14=ALTS
- ODM: 3-byte (24-bit) LE uint, km
- CRC-8 header: poly `0x31`, init `0xFF`
- CRC-16 body: poly `0x1021`, init `0xFFFF`

## Implemented subrecords (egts/parser.py)

Types 0, 1, 5, 9, 16, 17, 18, 19, 20/21, 24, 25, 27 — see README for full table.

**TODO**: decoders for iBeacon, RTLS (see `docs/`), and full SR_EGTSPLUS_DATA (type 15, see reference `egts_sr_egtsplus_data.go` + `egts_sr_egtsplus_data.proto`).
