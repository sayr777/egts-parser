# EGTS Sample Packets

Каждый файл `.hex` содержит один реальный EGTS-пакет в текстовом hex-формате.

## Формат файла

```
# EGTS Sample: <NAME>
# ────────────────────────
# Description: ...
# Packet type : PT_APPDATA (1)
# SDR count   : 1
# Services    : TELEDATA
# Subrecords  : SR_POS_DATA, SR_EXT_POS_DATA, ...
# Total bytes : 190
# Source      : egts_packages.csv:2
# ────────────────────────
#
01 00 00 0B  00 B1 00 E8  04 01 4E A6 ...
```

Строки с `#` — комментарии, игнорируются парсером.  
Пробелы между байтами не важны.

## Использование

**Python:**
```python
from egts import parse_hex
hex_str = open("samples/03_appdata_pos_telemetry.hex").read()
rows, err = parse_hex(hex_str)
```

**Excel:**  
Скопировать hex-строки (без `#`-комментариев) в ячейку `B2` листа **Analyzer** → `Alt-F8` → `ParsePacket`.

**CLI:**
```bash
python egts_cli.py samples/03_appdata_pos_telemetry.hex output.csv
```

## Список пакетов

| Файл | Тип | Байт | Подзаписи |
|------|-----|------|-----------|
| `01_pt_response.hex` | PT_RESPONSE | 16 | — |
| `02_term_identity.hex` | PT_APPDATA / AUTH | 85 | SR_TERM_IDENTITY |
| `03_appdata_pos_telemetry.hex` | PT_APPDATA / TELEDATA | 190 | SR_POS_DATA, SR_EXT_POS_DATA, SR_AD_SENSORS_DATA, SR_COUNTERS_DATA, SR_STATE_DATA |
| `04_appdata_with_egtsplus.hex` | PT_APPDATA / TELEDATA | 217 | SR_POS_DATA, SR_AD_SENSORS_DATA, SR_COUNTERS_DATA, SR_STATE_DATA, SR_EGTSPLUS_DATA |
| `05_appdata_two_sdrs.hex` | PT_APPDATA / TELEDATA | 363 | 2 × SDR с полной телематикой |
| `06_auth_with_sensors.hex` | PT_APPDATA / AUTH | 148 | SR_TERM_IDENTITY, SR_COUNTERS_DATA, SR_ABS_AN_SENS_DATA |

## Добавление нового пакета

1. Создать файл `NN_название.hex` с комментариями-метаданными
2. Запустить `python samples/generate.py` для пересоздания (если добавляете через скрипт)
3. Запустить `python excel/create_workbook.py` — новый лист появится в Excel автоматически

Нумерация файлов `01_`, `02_`, ... задаёт порядок листов в книге.
