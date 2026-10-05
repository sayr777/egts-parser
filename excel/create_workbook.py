"""
Creates EGTS_Analyzer.xlsx — bidirectional EGTS packet analyzer workbook.

Run from project root:  python excel/create_workbook.py
Requires: pip install openpyxl

Output files are written to the project root:
  EGTS_Analyzer.xlsx  — open in Excel, save as .xlsm, import EGTSAnalyzer.bas
  EGTSAnalyzer.bas    — VBA module for bidirectional editing (ParsePacket / BuildPacket)
"""

import os
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import (PatternFill, Font, Alignment, Border, Side,
                              numbers)
from openpyxl.utils import get_column_letter

# Project root is one level up from excel/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from egts.parser import parse_hex, FieldRow

# ── Colour palette ────────────────────────────────────────────────────────────
C_HEADER     = "1F497D"   # dark blue  – column headers
C_PACKET     = "DCE6F1"   # light blue – PACKET layer
C_SDR        = "EBF1DE"   # light green – SDR layer
C_SUBRECORD  = "FFF2CC"   # light yellow – subrecord layer
C_EDITABLE   = "FFFFFF"   # white – editable value cells
C_READONLY   = "F2F2F2"   # grey – readonly cells
C_HEX        = "E2EFDA"   # very light green – hex column
C_ERROR      = "FFC7CE"   # red – errors
C_TITLE      = "2E75B6"   # blue – title bar

LAYER_COLORS = {
    "PACKET":     C_PACKET,
    "PT_RESPONSE": "FFE6CC",
}

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)

def _border() -> Border:
    thin = Side(style="thin", color="BFBFBF")
    return Border(left=thin, right=thin, top=thin, bottom=thin)

def _hdr_font() -> Font:
    return Font(bold=True, color="FFFFFF", name="Calibri", size=10)

def _cell_font(bold=False) -> Font:
    return Font(bold=bold, name="Calibri", size=10)


# ── Load samples from samples/*.hex ──────────────────────────────────────────

def load_samples() -> list:
    """
    Returns [(sheet_name, hex_str), ...] from all *.hex files in samples/.
    File name (without extension) becomes the sheet name.
    Lines starting with # are stripped; remaining lines are concatenated.
    """
    samples_dir = PROJECT_ROOT / "samples"
    results = []
    for path in sorted(samples_dir.glob("*.hex")):
        lines = path.read_text(encoding="utf-8").splitlines()
        hex_lines = [l for l in lines if not l.startswith("#")]
        hex_str = "".join(hex_lines).replace(" ", "")
        if hex_str:
            name = path.stem.lstrip("0123456789_")  # strip leading "01_" etc.
            results.append((name, hex_str))
    return results


# ── Write a parsed packet to a sheet ─────────────────────────────────────────

COLS = ["Layer", "Field", "Offset", "Size", "Hex Bytes", "Raw Value", "Decoded", "Description", "Editable"]
COL_WIDTHS = [28, 10, 7, 5, 26, 16, 30, 45, 8]
# Column indices (1-based)
CI_LAYER  = 1
CI_FIELD  = 2
CI_OFFSET = 3
CI_SIZE   = 4
CI_HEX    = 5
CI_RAW    = 6
CI_DECODED= 7
CI_DESC   = 8
CI_EDIT   = 9

def write_packet_sheet(wb: Workbook, name: str, hex_str: str) -> None:
    ws = wb.create_sheet(title=name[:31])

    # Title row
    ws.merge_cells("A1:I1")
    title = ws["A1"]
    title.value = f"EGTS Packet: {name}"
    title.fill = _fill(C_TITLE)
    title.font = Font(bold=True, color="FFFFFF", name="Calibri", size=12)
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 20

    # Hex input row
    ws["A2"] = "RAW HEX:"
    ws["A2"].font = _cell_font(bold=True)
    clean_hex = hex_str.replace(" ", "").replace("\n", "").replace("\r", "")
    # write in B2 (merged B2:I2)
    ws.merge_cells("B2:I2")
    hex_cell = ws["B2"]
    hex_cell.value = clean_hex.upper()
    hex_cell.font = Font(name="Courier New", size=9)
    hex_cell.fill = _fill("FFFFD0")
    hex_cell.alignment = Alignment(wrap_text=True)
    ws.row_dimensions[2].height = 30

    # Column headers (row 3)
    for ci, (col_name, width) in enumerate(zip(COLS, COL_WIDTHS), start=1):
        cell = ws.cell(row=3, column=ci, value=col_name)
        cell.fill = _fill(C_HEADER)
        cell.font = _hdr_font()
        cell.alignment = Alignment(horizontal="center")
        cell.border = _border()
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.row_dimensions[3].height = 16
    ws.freeze_panes = "A4"

    # Parse
    rows, err = parse_hex(hex_str)
    if err:
        ws.cell(row=4, column=1, value=f"PARSE ERROR: {err}").fill = _fill(C_ERROR)
        return

    # Data rows
    for ri, r in enumerate(rows, start=4):
        # pick background by layer
        layer_key = r.layer.split("[")[0].strip()
        if "SR_" in r.layer or "SUBRECORD" in r.layer:
            bg = C_SUBRECORD
        elif layer_key in LAYER_COLORS:
            bg = LAYER_COLORS[layer_key]
        elif r.layer.startswith("SDR"):
            bg = C_SDR
        else:
            bg = C_PACKET

        vals = [r.layer, r.field, r.offset, r.size, r.hex_val,
                str(r.raw) if not isinstance(r.raw, str) else r.raw,
                r.decoded, r.desc, "Y" if r.editable else ""]

        for ci, val in enumerate(vals, start=1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.border = _border()
            cell.font = _cell_font()
            cell.alignment = Alignment(vertical="top")

            if ci == CI_HEX:
                cell.font = Font(name="Courier New", size=9)
                cell.fill = _fill(C_HEX)
            elif ci == CI_DECODED and r.editable:
                cell.fill = _fill(C_EDITABLE)
                cell.font = Font(name="Calibri", size=10, color="000080")
            elif ci == CI_LAYER:
                cell.fill = _fill(bg)
                cell.font = _cell_font(bold=True)
            else:
                cell.fill = _fill(bg if ci not in (CI_RAW, CI_DECODED) else C_READONLY if not r.editable else C_EDITABLE)

    # Auto-fit row heights roughly
    ws.sheet_properties.filterMode = False

    # Named range for VBA reference
    ws.print_title_rows = "3:3"


# ── Analyzer sheet (interactive) ──────────────────────────────────────────────

def write_analyzer_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet(title="Analyzer", index=0)

    ws.merge_cells("A1:I1")
    title = ws["A1"]
    title.value = "EGTS Packet Analyzer  —  paste HEX in B2, then press Parse"
    title.fill = _fill(C_TITLE)
    title.font = Font(bold=True, color="FFFFFF", name="Calibri", size=12)
    title.alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 22

    ws["A2"] = "RAW HEX:"
    ws["A2"].font = _cell_font(bold=True)
    ws.merge_cells("B2:I2")
    hex_in = ws["B2"]
    hex_in.value = "(paste EGTS hex bytes here)"
    hex_in.font = Font(name="Courier New", size=9, color="808080")
    hex_in.fill = _fill("FFFFD0")
    hex_in.alignment = Alignment(wrap_text=True)
    ws.row_dimensions[2].height = 40

    # Column headers
    for ci, (col_name, width) in enumerate(zip(COLS, COL_WIDTHS), start=1):
        cell = ws.cell(row=3, column=ci, value=col_name)
        cell.fill = _fill(C_HEADER)
        cell.font = _hdr_font()
        cell.alignment = Alignment(horizontal="center")
        cell.border = _border()
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.row_dimensions[3].height = 16
    ws.freeze_panes = "A4"

    # Placeholder row
    ws["A4"] = "← Enter HEX above and click Parse (Alt-F8 → ParsePacket)"
    ws["A4"].font = Font(italic=True, color="808080")
    ws.merge_cells("A4:I4")


# ── VBA module ────────────────────────────────────────────────────────────────

VBA_CODE = r'''
Attribute VB_Name = "EGTSAnalyzer"
' EGTS Analyzer VBA module
' Requires: egts_parser.py in the same folder as this workbook
' Usage:
'   ParsePacket  - read hex from Analyzer!B2, call Python, fill table
'   BuildPacket  - read Decoded column, rebuild hex (simple fields)
'   RunPython    - helper to call Python script

Option Explicit

Const PYTHON_SCRIPT = "egts_cli.py"
Const DATA_START_ROW = 4

' ---- Parse hex → fill Analyzer sheet ----------------------------------------

Sub ParsePacket()
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Analyzer")

    Dim hexStr As String
    hexStr = Trim(ws.Range("B2").Value)
    If hexStr = "" Or Left(hexStr, 1) = "(" Then
        MsgBox "Paste a HEX string in cell B2 first.", vbInformation
        Exit Sub
    End If

    ' Write hex to temp file, call Python, read result CSV back
    Dim tmpHex As String
    tmpHex = Environ("TEMP") & "\egts_input.txt"
    Dim tmpOut As String
    tmpOut = Environ("TEMP") & "\egts_output.csv"

    ' Write input
    Dim fNum As Integer
    fNum = FreeFile
    Open tmpHex For Output As #fNum
    Print #fNum, hexStr
    Close #fNum

    ' Find Python and script
    Dim scriptDir As String
    scriptDir = ThisWorkbook.Path
    Dim pyScript As String
    pyScript = scriptDir & "\" & PYTHON_SCRIPT

    Dim cmd As String
    cmd = "python """ & pyScript & """ """ & tmpHex & """ """ & tmpOut & """"

    Dim ret As Long
    ret = Shell("cmd /c " & cmd, vbHide, , True)

    ' Check output exists
    If Dir(tmpOut) = "" Then
        MsgBox "Python script not found or failed." & vbCrLf & _
               "Make sure egts_cli.py is in: " & scriptDir, vbCritical
        Exit Sub
    End If

    ' Clear old data
    ClearDataRows ws

    ' Read CSV and populate
    Dim csvLine As String
    Dim rowIdx As Long
    rowIdx = DATA_START_ROW

    fNum = FreeFile
    Open tmpOut For Input As #fNum
    Dim hdrRead As Boolean
    hdrRead = False
    Do While Not EOF(fNum)
        Line Input #fNum, csvLine
        If Not hdrRead Then
            hdrRead = True  ' skip header
        Else
            Dim parts() As String
            parts = SplitCSV(csvLine)
            If UBound(parts) >= 7 Then
                ws.Cells(rowIdx, 1).Value = parts(0)  ' Layer
                ws.Cells(rowIdx, 2).Value = parts(1)  ' Field
                ws.Cells(rowIdx, 3).Value = CLng(parts(2))  ' Offset
                ws.Cells(rowIdx, 4).Value = CLng(parts(3))  ' Size
                ws.Cells(rowIdx, 5).Value = parts(4)  ' Hex
                ws.Cells(rowIdx, 6).Value = parts(5)  ' Raw
                ws.Cells(rowIdx, 7).Value = parts(6)  ' Decoded
                ws.Cells(rowIdx, 8).Value = parts(7)  ' Desc
                If UBound(parts) >= 8 Then
                    ws.Cells(rowIdx, 9).Value = parts(8)  ' Editable
                End If
                ApplyRowFormatting ws, rowIdx, parts(0), parts(8) = "Y"
                rowIdx = rowIdx + 1
            End If
        End If
    Loop
    Close #fNum

    MsgBox "Parsed " & (rowIdx - DATA_START_ROW) & " fields.", vbInformation
End Sub

' ---- Rebuild packet hex from Decoded column ----------------------------------

Sub BuildPacket()
    ' Read the PACKET layer rows back and recompute CRCs
    ' For now outputs new HCS and SFRCS based on current hex bytes
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Analyzer")

    Dim hexStr As String
    hexStr = GetFullHex(ws)
    If hexStr = "" Then
        MsgBox "No packet data found.", vbInformation
        Exit Sub
    End If

    ws.Range("B2").Value = hexStr
    MsgBox "Packet hex updated in B2. Run Parse to verify.", vbInformation
End Sub

' ---- Helpers -----------------------------------------------------------------

Private Sub ClearDataRows(ws As Worksheet)
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If lastRow >= DATA_START_ROW Then
        ws.Rows(DATA_START_ROW & ":" & lastRow).ClearContents
        ws.Rows(DATA_START_ROW & ":" & lastRow).Interior.ColorIndex = xlNone
    End If
End Sub

Private Function GetFullHex(ws As Worksheet) As String
    ' Reconstruct full hex by concatenating hex bytes from column 5
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 5).End(xlUp).Row
    Dim result As String
    result = ""
    Dim r As Long
    For r = DATA_START_ROW To lastRow
        Dim layerVal As String
        layerVal = ws.Cells(r, 1).Value
        If layerVal = "PACKET" Or InStr(layerVal, "SDR") > 0 Or InStr(layerVal, "SR_") > 0 Or _
           layerVal = "PT_RESPONSE" Then
            result = result & Replace(ws.Cells(r, 5).Value, " ", "")
        End If
    Next r
    GetFullHex = result
End Function

Private Sub ApplyRowFormatting(ws As Worksheet, rowIdx As Long, layer As String, editable As Boolean)
    Dim bgColor As Long
    If InStr(layer, "SR_") > 0 Then
        bgColor = RGB(255, 242, 204)  ' yellow
    ElseIf Left(layer, 3) = "SDR" Then
        bgColor = RGB(235, 241, 222)  ' green
    ElseIf layer = "PT_RESPONSE" Then
        bgColor = RGB(255, 230, 204)  ' orange
    Else
        bgColor = RGB(220, 230, 241)  ' blue
    End If

    Dim ci As Integer
    For ci = 1 To 9
        With ws.Cells(rowIdx, ci).Interior
            If ci = 5 Then
                .Color = RGB(226, 239, 218)  ' hex column
            ElseIf ci = 7 And editable Then
                .Color = RGB(255, 255, 255)  ' editable decoded
            Else
                .Color = bgColor
            End If
        End With
        ws.Cells(rowIdx, ci).Font.Name = IIf(ci = 5, "Courier New", "Calibri")
        ws.Cells(rowIdx, ci).Font.Size = IIf(ci = 5, 9, 10)
    Next ci

    ' Highlight editable decoded values in blue
    If editable Then
        ws.Cells(rowIdx, 7).Font.Color = RGB(0, 0, 128)
    End If
End Sub

' Simple CSV splitter (handles quoted fields)
Private Function SplitCSV(line As String) As String()
    Dim result() As String
    ReDim result(0)
    Dim i As Long, fieldStart As Long, inQuotes As Boolean
    Dim fieldCount As Long
    fieldCount = 0
    inQuotes = False
    fieldStart = 1

    For i = 1 To Len(line)
        Dim c As String
        c = Mid(line, i, 1)
        If c = Chr(34) Then
            inQuotes = Not inQuotes
        ElseIf c = "," And Not inQuotes Then
            ReDim Preserve result(fieldCount)
            result(fieldCount) = StripQuotes(Mid(line, fieldStart, i - fieldStart))
            fieldCount = fieldCount + 1
            fieldStart = i + 1
        End If
    Next i
    ' Last field
    ReDim Preserve result(fieldCount)
    result(fieldCount) = StripQuotes(Mid(line, fieldStart))
    SplitCSV = result
End Function

Private Function StripQuotes(s As String) As String
    s = Trim(s)
    If Left(s, 1) = Chr(34) And Right(s, 1) = Chr(34) Then
        s = Mid(s, 2, Len(s) - 2)
    End If
    StripQuotes = s
End Function
'''

# The VBA above requires a CLI bridge script
# ── Legend sheet ──────────────────────────────────────────────────────────────

def write_legend_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet(title="Legend")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 50

    items = [
        ("PACKET layer",   C_PACKET,    "Top-level transport header fields"),
        ("SDR[n] layer",   C_SDR,       "Service Data Record — one logical record inside a packet"),
        ("Subrecord layer",C_SUBRECORD, "SR_xxx — typed payload (GPS, sensors, auth…)"),
        ("PT_RESPONSE",    "FFE6CC",    "Response packet body"),
        ("HEX column",     C_HEX,       "Raw bytes as hex (editable for manual tweaks)"),
        ("Decoded (blue)", C_EDITABLE,  "Human-readable value — editable fields shown in blue"),
        ("Read-only",      C_READONLY,  "Computed or structural fields (CRC, lengths)"),
    ]
    ws["A1"] = "Colour Legend"
    ws["A1"].font = Font(bold=True, size=12)
    for ri, (label, color, desc) in enumerate(items, start=2):
        ws.cell(ri, 1, label).fill = _fill(color)
        ws.cell(ri, 1).border = _border()
        ws.cell(ri, 2, desc)

    ws["A10"] = "Key fields"
    ws["A10"].font = Font(bold=True)
    fields = [
        ("PRV",  "Protocol version (always 0x01)"),
        ("FLAGS","Flags byte: PRF[7:6] RTE[5] ENA[4:3] CMP[2] PR[1:0]"),
        ("FDL",  "Frame Data Length — body byte count (auto-computed)"),
        ("PID",  "Packet Identifier — sequence number"),
        ("PT",   "Packet Type: 0=PT_RESPONSE, 1=PT_APPDATA"),
        ("HCS",  "Header CRC-8 (poly 0x31, init 0xFF)"),
        ("SFRCS","Body CRC-16 (poly 0x1021, init 0xFFFF)"),
        ("NTM",  "Navigation time: seconds since 2010-01-01 UTC"),
        ("LAT/LONG","Degrees × 0xFFFFFFFF / 90 (or 180) stored as uint32 LE"),
        ("SPD",  "14-bit speed (bits 13:0) × 0.1 km/h; bit15=DIRH, bit14=ALTS"),
        ("ODM",  "Odometer: 3-byte LE uint24 in km"),
    ]
    for ri, (f, d) in enumerate(fields, start=11):
        ws.cell(ri, 1, f).font = Font(bold=True)
        ws.cell(ri, 2, d)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    out_path = PROJECT_ROOT / "EGTS_Analyzer.xlsx"

    wb = Workbook()
    # Remove default sheet
    del wb["Sheet"]

    write_analyzer_sheet(wb)

    samples = load_samples()
    print(f"Parsing {len(samples)} sample packets from samples/...")
    for name, hex_str in samples:
        clean = hex_str.replace(" ", "")
        rows, err = parse_hex(clean)
        status = f"OK ({len(rows)} fields)" if not err else f"ERR: {err}"
        print(f"  {name}: {status}")
        write_packet_sheet(wb, name, clean)

    write_legend_sheet(wb)

    wb.save(str(out_path))
    print(f"\nSaved: {out_path}")

    # Write VBA module for manual import (to project root alongside the workbook)
    bas_path = PROJECT_ROOT / "EGTSAnalyzer.bas"
    bas_path.write_text(VBA_CODE, encoding="utf-8")
    print(f"Saved: {bas_path}  <- Import into VBA editor (Alt-F11 -> File -> Import)")
    print()
    print("Next steps:")
    print("  1. Open EGTS_Analyzer.xlsx in Excel, save as .xlsm (macro-enabled)")
    print("  2. Alt-F11 -> File -> Import File -> EGTSAnalyzer.bas")
    print("  3. In Analyzer sheet, paste hex in B2, then Alt-F8 -> ParsePacket -> Run")


if __name__ == "__main__":
    main()
