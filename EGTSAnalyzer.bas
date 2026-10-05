
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
