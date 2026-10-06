# EGTS Analyzer

Инструмент для разбора и сборки пакетов протокола **EGTS** (ГОСТ Р 54619-2011) прямо в Excel.

- Вставляете hex-строку пакета → получаете таблицу всех полей с расшифровкой
- Меняете значение поля → пересобираете пакет с пересчётом CRC

---

## Установка и запуск

**Требования:** Python 3.9+, Microsoft Excel (Windows)

```bash
# 1. Установить зависимости
pip install openpyxl pywin32

# 2. Сгенерировать EGTS_Analyzer.xlsm с готовыми макросами
python setup_xlsm.py
```

Откройте появившийся `EGTS_Analyzer.xlsm` — макросы уже встроены, ничего настраивать не нужно.

> **Ошибка «Programmatic access to VBA is not trusted»?**
> Excel → Файл → Параметры → Центр управления безопасностью → Параметры центра управления безопасностью
> → Параметры макросов → галка **«Доверять доступу к объектной модели проектов VBA»** → ОК
> Затем повторите `python setup_xlsm.py`

---

## Использование в Excel

Рабочий лист **Analyzer**:

| Задача | Действие |
|--------|----------|
| Разобрать пакет | Вставить hex в ячейку **B2** → `Alt+F8` → `ParsePacket` → **Run** |
| Изменить поле и пересобрать | Отредактировать синюю ячейку в колонке **Decoded** → `Alt+F8` → `BuildPacket` → **Run** |

Листы с примерами пакетов: `AUTH_RESPONSE`, `APPDATA_POS`, `APPDATA_STATE`, `TERM_IDENTITY`, `APPDATA_EGTSPLUS`.

---

## Поддерживаемые подзаписи

| Код | Подзапись | Ключевые поля |
|-----|-----------|---------------|
| 0 | SR_RECORD_RESPONSE | CRN, RST |
| 1 | SR_TERM_IDENTITY | TID, IMEI, IMSI, HDID |
| 5 | SR_DISPATCHER_IDENTITY | DT, DID |
| 9 | SR_RESULT_CODE | RCD |
| 16 | SR_POS_DATA | Время, LAT, LON, скорость, курс, пробег, высота |
| 17 | SR_EXT_POS_DATA | VDOP, HDOP, PDOP, кол-во спутников |
| 18 | SR_AD_SENSORS_DATA | Цифровые входы/выходы, АЦП ×8 |
| 19 | SR_COUNTERS_DATA | Счётчики ×8 |
| 20/21 | SR_STATE_DATA | Состояние, напряжение АКБ/бортсети |
| 24 | SR_ABS_AN_SENS_DATA | Абсолютный аналоговый датчик |
| 25 | SR_ABS_CNTR_DATA | Абсолютный счётчик |
| 27 | SR_LIQUID_LEVEL | Уровень жидкости |
| 200 | SR_RADIOTAG_EVENT | RFID-метка (UID, RSSI) |
| 201 | SR_IBEACON_EVENT | BLE iBeacon (UUID, Major, Minor, RSSI, TxPower) |
| 202 | SR_CELL_INFO | LBS-ячейка (MCC, MNC, LAC, CellID, RAT) |
| 203 | SR_WIFI_AP_DATA | Wi-Fi точка (BSSID, SSID, RSSI, канал) |

---

## Python API

```python
from egts import parse_hex

rows, err = parse_hex("01 00 00 0B 00 03 00 89 00 00 4A 15 38 00 33 E8")
for r in rows:
    print(f"{r.layer:20s} {r.field:12s} {r.decoded}")
```

```
PACKET               PRV          1
PACKET               FDL          3
PACKET               PID          0
...
```

Запуск из командной строки (используется макросом VBA):

```bash
python egts_cli.py packet.txt output.csv
```

Поля объекта `FieldRow`:

| Поле | Описание |
|------|----------|
| `layer` | Уровень: `PACKET`, `SDR[0]`, `SDR[0] SR_POS_DATA`, … |
| `field` | Имя поля: `NTM`, `LAT`, `SPD`, … |
| `offset` | Смещение в байтах от начала пакета |
| `size` | Размер в байтах |
| `hex_val` | Hex-представление: `"4F 5F E5 10"` |
| `raw` | Числовое значение |
| `decoded` | Расшифровка: `"2018-12-25 20:59:59 UTC"` |
| `editable` | `True` — поле доступно для редактирования |

---

## Справка по кодированию полей EGTS

| Поле | Формула |
|------|---------|
| Время (NTM, TM) | секунды с 2010-01-01 00:00:00 UTC, uint32 LE |
| Широта (LAT) | `uint32 = градусы / 90 × 0xFFFFFFFF` |
| Долгота (LONG) | `uint32 = градусы / 180 × 0xFFFFFFFF` |
| Скорость (SPD) | биты 13:0 × 0.1 км/ч; бит 15 = DIRH, бит 14 = ALTS |
| Пробег (ODM) | 24-bit LE uint, км |
| CRC-8 заголовка | полином `0x31`, начальное значение `0xFF` |
| CRC-16 тела | полином `0x1021`, начальное значение `0xFFFF` |

---

## Структура пакета EGTS

```
┌─────────────────────────── PACKET ──────────────────────────────┐
│ PRV SKID FLAGS HL HE FDL PID PT [PRA RCA TTL] HCS               │
│                                                                  │
│  ┌────────────────────── SFRD (тело пакета) ─────────────────┐  │
│  │  ┌──── SDR[0] ────────────────────────────────────────┐   │  │
│  │  │ RL RN FLAGS [OID] [EVID] [TM] SST RST              │   │  │
│  │  │  ┌── Подзапись ────────────────────────────────┐   │   │  │
│  │  │  │ SRT SRL │ данные (SR_POS_DATA / SR_EXT / …) │   │   │  │
│  │  │  └─────────────────────────────────────────────┘   │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│ SFRCS                                                            │
└──────────────────────────────────────────────────────────────────┘
```
