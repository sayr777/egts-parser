# EGTS Analyzer

Двунаправленный анализатор пакетов протокола **EGTS** (ERA-GLONASS Telematics System, ГОСТ Р 54619-2011) в Excel.

- **Декодирование**: вставьте hex-строку пакета → получите таблицу всех полей с расшифровкой
- **Кодирование**: измените значение поля → пересоберите hex-пакет с пересчётом CRC

---

## Структура проекта

```
egts-parser/
├── egts/                        # Python-пакет парсера
│   ├── __init__.py              # Экспортирует parse_hex, encode_packet, FieldRow
│   ├── parser.py                # Парсер/энкодер всех уровней EGTS
│   └── cli.py                   # CLI-логика (вызывается VBA через Shell)
├── excel/
│   └── create_workbook.py       # Генератор Excel-книги
├── docs/
│   ├── TZ_EGTS_iBeacon_extended_additive_v17.docx
│   └── TZ_EGTS_RTLS_v2.docx
├── egts_cli.py                  # Корневая точка входа для VBA
├── EGTSAnalyzer.bas             # VBA-модуль (импортируется в .xlsm)
├── EGTS_Analyzer.xlsx           # Готовая книга (генерируется)
└── requirements.txt
```

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install openpyxl
```

### 2. Генерация Excel-книги

```bash
python excel/create_workbook.py
```

Создаёт `EGTS_Analyzer.xlsx` и `EGTSAnalyzer.bas` в корне проекта.

### 3. Настройка Excel

1. Открыть `EGTS_Analyzer.xlsx`
2. Сохранить как **`.xlsm`** (с поддержкой макросов)
3. `Alt-F11` → File → Import File → выбрать `EGTSAnalyzer.bas`
4. Сохранить

### 4. Использование

| Действие | Как |
|----------|-----|
| Разобрать пакет | Вставить hex в ячейку B2 листа **Analyzer** → `Alt-F8` → `ParsePacket` → Run |
| Пересобрать пакет | Изменить синие ячейки колонки **Decoded** → `Alt-F8` → `BuildPacket` → Run |
| Готовые примеры | Листы `AUTH_RESPONSE`, `APPDATA_POS`, `APPDATA_EGTSPLUS`, `APPDATA_STATE`, `TERM_IDENTITY` |

---

## Python API

```python
from egts import parse_hex, encode_packet

# Разобрать пакет
rows, err = parse_hex("01 00 00 0B ...")
for r in rows:
    print(r.layer, r.field, r.offset, r.size, r.hex_val, r.decoded)

# Получить CSV через CLI
python egts_cli.py packet.txt output.csv
```

Каждый `FieldRow` содержит:

| Поле | Тип | Описание |
|------|-----|---------|
| `layer` | str | `"PACKET"`, `"SDR[0]"`, `"SDR[0] SR_POS_DATA"`, … |
| `field` | str | Имя поля: `NTM`, `LAT`, `SPD`, … |
| `offset` | int | Смещение в байтах от начала пакета |
| `size` | int | Размер в байтах |
| `hex_val` | str | Hex-представление: `"4F 5F E5 10"` |
| `raw` | Any | Сырое числовое значение |
| `decoded` | str | Расшифровка: `"2018-12-25 20:59:59 UTC"` |
| `editable` | bool | `True` — поле можно редактировать для пересборки |

---

## Структура пакета EGTS

```
┌─────────────────────────── PACKET ──────────────────────────────┐
│ PRV SKID FLAGS HL HE FDL PID PT [PRA RCA TTL] HCS               │
│                                                                  │
│  ┌──────────────── SFRD (ServiceDataSet) ────────────────────┐  │
│  │  ┌──── SDR[0] ────────────────────────────────────────┐   │  │
│  │  │ RL RN FLAGS [OID] [EVID] [TM] SST RST              │   │  │
│  │  │  ┌─ RecordData ─────────────────────────────────┐  │   │  │
│  │  │  │ SRT SRL │ SR_POS_DATA / SR_EXT_POS / ...    │  │   │  │
│  │  │  └──────────────────────────────────────────────┘  │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  │  ┌──── SDR[1] ──────────────────────────────────────┐     │  │
│  │  │ ...                                              │     │  │
│  │  └──────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────┘  │
│ SFRCS                                                            │
└──────────────────────────────────────────────────────────────────┘
```

### Типы подзаписей (реализованы)

| Код | Имя | Ключевые поля |
|-----|-----|---------------|
| 0  | SR_RECORD_RESPONSE  | CRN, RST |
| 1  | SR_TERM_IDENTITY    | TID, флаги, HDID / IMEI / IMSI |
| 9  | SR_RESULT_CODE      | RCD |
| 16 | SR_POS_DATA         | NTM, LAT, LONG, FLAGS, SPD, DIR, ODM, DIN, SRC, ALT |
| 17 | SR_EXT_POS_DATA     | VDOP, HDOP, PDOP, SAT, NS |
| 18 | SR_AD_SENSORS_DATA  | DIOE, DOUT, ASFE, ADIO×8, ANS×8 |
| 19 | SR_COUNTERS_DATA    | CFE, CN×8 (3-byte LE) |
| 20/21 | SR_STATE_DATA   | ST, MPSV, BBV, IBV, FLAGS |
| 24 | SR_ABS_AN_SENS_DATA | ASN, ASV |
| 25 | SR_ABS_CNTR_DATA    | CN, CNV |
| 27 | SR_LIQUID_LEVEL     | FLAGS, LLS |
| 5  | SR_DISPATCHER_IDENTITY | DT, DID |

### Кодирование значений

| Поле | Формула |
|------|---------|
| Время (NTM, TM) | секунды с 2010-01-01 00:00:00 UTC, uint32 LE |
| Широта (LAT) | `uint32 = degrees / 90 × 0xFFFFFFFF` |
| Долгота (LONG) | `uint32 = degrees / 180 × 0xFFFFFFFF` |
| Скорость (SPD) | биты 13:0 × 0.1 км/ч; бит15 = DIRH, бит14 = ALTS |
| Пробег (ODM) | 24-bit LE uint, км |
| CRC-8 заголовка | полином `0x31`, начальное `0xFF` |
| CRC-16 тела | полином `0x1021`, начальное `0xFFFF` |

---

## Дополнительные секции (в разработке)

Спецификации лежат в `docs/`:

- **iBeacon** — `TZ_EGTS_iBeacon_extended_additive_v17.docx`
- **RTLS** — `TZ_EGTS_RTLS_v2.docx`
- **EGTS_PLUS** (тип 15) — protobuf-схема в reference-парсере: `egts_sr_egtsplus_data.proto`

