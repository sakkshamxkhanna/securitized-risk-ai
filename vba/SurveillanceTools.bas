Attribute VB_Name = "SurveillanceTools"
' =====================================================================
'  SurveillanceTools
'  VBA automation for the securitized products surveillance pack.
'
'  Four macros covering the repetitive parts of a monthly surveillance
'  cycle:
'     BuildStratification   - cuts the loan tape into a formatted tape
'     FlagExceptions        - marks loans breaching credit thresholds
'     RefreshAndStamp       - full recalculation with an audit stamp
'     ExportPackToPDF       - PDF of the review sheets for circulation
'
'  Written against the workbook produced by src/excel_export.py:
'     "Loan Tape"  header row 4, data from row 5
'                  A loan_id      B orig_balance   C current_balance
'                  D coupon       E fico           F ltv
'                  G dti          H seasoning_mo   I remaining_term_mo
'                  J state        K property_type  L originator
'                  M servicer
'     "Assumptions" B7 = LGD, B8 = escalation threshold
'
'  Stratifications are written as SUMIFS / SUMPRODUCT formulas rather
'  than values, so the output stays live against the tape.
' =====================================================================

Option Explicit

' --- exception thresholds -------------------------------------------
' Held as constants so every run applies the same test. Move these to
' the Assumptions sheet if the desk wants to tune them without opening
' the editor.
Private Const MAX_LTV As Double = 90#
Private Const MIN_FICO As Long = 620
Private Const MAX_DTI As Double = 45#

Private Const TAPE_SHEET As String = "Loan Tape"
Private Const STRAT_SHEET As String = "VBA Stratification"
Private Const FIRST_DATA_ROW As Long = 5

' The loan tape is a ListObject ending at column M. Writing the exception
' note in N would make Excel auto-expand the table over it, so it goes in
' P with a gap. AutoExpandListRange is also disabled while writing.
Private Const EXC_COL As Long = 16            ' column P

' Colour constants. VBA stores colours as R + G*256 + B*65536, so these
' are the decimal forms of the RGB values named in the comments.
Private Const CLR_NAVY As Long = 4005391      ' RGB(15, 30, 61)
Private Const CLR_FLAG As Long = 13551615     ' RGB(255, 199, 206)


' =====================================================================
'  Helpers
' =====================================================================

' Returns the worksheet if it exists, otherwise Nothing. Avoids relying
' on error trapping for ordinary control flow.
Private Function GetSheet(ByVal sheetName As String) As Worksheet
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Worksheets
        If StrComp(ws.Name, sheetName, vbTextCompare) = 0 Then
            Set GetSheet = ws
            Exit Function
        End If
    Next ws
    Set GetSheet = Nothing
End Function

' Last populated row of the loan tape, read from the loan_id column.
Private Function LastTapeRow(ByVal ws As Worksheet) As Long
    LastTapeRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
End Function

' Deletes a sheet without the confirmation prompt.
Private Sub DropSheet(ByVal sheetName As String)
    Dim ws As Worksheet
    Set ws = GetSheet(sheetName)
    If ws Is Nothing Then Exit Sub
    Application.DisplayAlerts = False
    ws.Delete
    Application.DisplayAlerts = True
End Sub

' Formats a header row: navy fill, white bold text, bordered.
Private Sub StyleHeader(ByVal rng As Range)
    With rng
        .Font.Bold = True
        .Font.Color = vbWhite
        .Font.Name = "Arial"
        .Font.Size = 10
        .Interior.Color = CLR_NAVY
        .HorizontalAlignment = xlCenter
        .Borders.LineStyle = xlContinuous
        .Borders.Color = RGB(191, 191, 191)
    End With
End Sub


' =====================================================================
'  1. BuildStratification
'     Cuts the loan tape into FICO and LTV bands on a fresh sheet.
'     Every cell is a formula against the tape, so editing a loan
'     updates the tape without re-running the macro.
' =====================================================================
Public Sub BuildStratification()
    Dim tape As Worksheet, out As Worksheet
    Dim lastRow As Long, i As Long, r As Long, startRow As Long
    Dim balRef As String, ficoRef As String, ltvRef As String, cpnRef As String
    Dim ficoLo As Variant, ficoHi As Variant, ficoLbl As Variant
    Dim ltvLo As Variant, ltvHi As Variant, ltvLbl As Variant

    Set tape = GetSheet(TAPE_SHEET)
    If tape Is Nothing Then
        MsgBox "Sheet '" & TAPE_SHEET & "' not found. Open the surveillance pack first.", _
               vbExclamation, "Stratification"
        Exit Sub
    End If

    lastRow = LastTapeRow(tape)
    If lastRow < FIRST_DATA_ROW Then
        MsgBox "The loan tape has no data rows.", vbExclamation, "Stratification"
        Exit Sub
    End If

    On Error GoTo CleanFail
    Application.ScreenUpdating = False

    DropSheet STRAT_SHEET
    Set out = ThisWorkbook.Worksheets.Add(After:=tape)
    out.Name = STRAT_SHEET

    ' Absolute references into the tape, built once and reused.
    balRef = "'" & TAPE_SHEET & "'!$C$" & FIRST_DATA_ROW & ":$C$" & lastRow
    ficoRef = "'" & TAPE_SHEET & "'!$E$" & FIRST_DATA_ROW & ":$E$" & lastRow
    ltvRef = "'" & TAPE_SHEET & "'!$F$" & FIRST_DATA_ROW & ":$F$" & lastRow
    cpnRef = "'" & TAPE_SHEET & "'!$D$" & FIRST_DATA_ROW & ":$D$" & lastRow

    out.Range("A1").Value = "Stratification (built by VBA)"
    With out.Range("A1").Font
        .Bold = True
        .Size = 13
        .Name = "Arial"
        .Color = CLR_NAVY
    End With
    out.Range("A2").Value = "Every figure is a live formula over '" & TAPE_SHEET & _
                            "'. Built " & Format$(Now, "dd-mmm-yyyy hh:nn") & "."
    out.Range("A2").Font.Italic = True
    out.Range("A2").Font.Size = 9

    ' ---- FICO bands
    ficoLbl = Array("<620", "620-659", "660-699", "700-739", "740-779", "780+")
    ficoLo = Array(0, 620, 660, 700, 740, 780)
    ficoHi = Array(620, 660, 700, 740, 780, 10000)

    out.Range("A4").Value = "By FICO"
    out.Range("A4").Font.Bold = True
    out.Range("A5:E5").Value = Array("Bucket", "Loans", "UPB", "% of pool", "WA coupon")
    StyleHeader out.Range("A5:E5")

    startRow = 6
    For i = LBound(ficoLbl) To UBound(ficoLbl)
        r = startRow + i
        out.Cells(r, 1).Value = ficoLbl(i)
        out.Cells(r, 2).Formula = "=COUNTIFS(" & ficoRef & ","">=" & ficoLo(i) & _
                                  """," & ficoRef & ",""<" & ficoHi(i) & """)"
        out.Cells(r, 3).Formula = "=SUMIFS(" & balRef & "," & ficoRef & ","">=" & ficoLo(i) & _
                                  """," & ficoRef & ",""<" & ficoHi(i) & """)"
        out.Cells(r, 4).Formula = "=IFERROR(C" & r & "/$C$" & startRow + UBound(ficoLbl) + 1 & ",0)"
        ' Balance-weighted coupon: SUMPRODUCT of the band mask, balance and coupon,
        ' divided by the band's balance.
        out.Cells(r, 5).Formula = "=IFERROR(SUMPRODUCT((" & ficoRef & ">=" & ficoLo(i) & _
                                  ")*(" & ficoRef & "<" & ficoHi(i) & ")*" & balRef & "*" & _
                                  cpnRef & ")/C" & r & ",0)"
    Next i
    WriteTotals out, startRow, UBound(ficoLbl) + 1, 5

    ' ---- LTV bands
    ltvLbl = Array("<60", "60-69", "70-79", "80-89", "90-99", "100+")
    ltvLo = Array(0, 60, 70, 80, 90, 100)
    ltvHi = Array(60, 70, 80, 90, 100, 1000)

    startRow = startRow + UBound(ficoLbl) + 4
    out.Cells(startRow - 2, 1).Value = "By LTV"
    out.Cells(startRow - 2, 1).Font.Bold = True
    out.Range(out.Cells(startRow - 1, 1), out.Cells(startRow - 1, 5)).Value = _
        Array("Bucket", "Loans", "UPB", "% of pool", "WA coupon")
    StyleHeader out.Range(out.Cells(startRow - 1, 1), out.Cells(startRow - 1, 5))

    For i = LBound(ltvLbl) To UBound(ltvLbl)
        r = startRow + i
        out.Cells(r, 1).Value = ltvLbl(i)
        out.Cells(r, 2).Formula = "=COUNTIFS(" & ltvRef & ","">=" & ltvLo(i) & _
                                  """," & ltvRef & ",""<" & ltvHi(i) & """)"
        out.Cells(r, 3).Formula = "=SUMIFS(" & balRef & "," & ltvRef & ","">=" & ltvLo(i) & _
                                  """," & ltvRef & ",""<" & ltvHi(i) & """)"
        out.Cells(r, 4).Formula = "=IFERROR(C" & r & "/$C$" & startRow + UBound(ltvLbl) + 1 & ",0)"
        out.Cells(r, 5).Formula = "=IFERROR(SUMPRODUCT((" & ltvRef & ">=" & ltvLo(i) & _
                                  ")*(" & ltvRef & "<" & ltvHi(i) & ")*" & balRef & "*" & _
                                  cpnRef & ")/C" & r & ",0)"
    Next i
    WriteTotals out, startRow, UBound(ltvLbl) + 1, 5

    ' ---- formats
    out.Columns("A").ColumnWidth = 14
    out.Columns("B").ColumnWidth = 11
    out.Columns("C").ColumnWidth = 18
    out.Columns("D").ColumnWidth = 12
    out.Columns("E").ColumnWidth = 12
    out.Columns("B").NumberFormat = "#,##0"
    out.Columns("C").NumberFormat = "$#,##0;($#,##0);-"
    out.Columns("D").NumberFormat = "0.00%"
    out.Columns("E").NumberFormat = "0.000"

    Application.ScreenUpdating = True
    MsgBox "Stratification built on '" & STRAT_SHEET & "' from " & _
           Format$(lastRow - FIRST_DATA_ROW + 1, "#,##0") & " loans.", _
           vbInformation, "Stratification"
    Exit Sub

CleanFail:
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    MsgBox "BuildStratification failed: " & Err.Description, vbCritical, "Stratification"
End Sub

' Writes a bold total row beneath a band block and borders the whole table.
Private Sub WriteTotals(ByVal ws As Worksheet, ByVal firstRow As Long, _
                        ByVal bandCount As Long, ByVal lastCol As Long)
    Dim totalRow As Long
    totalRow = firstRow + bandCount

    ws.Cells(totalRow, 1).Value = "Total"
    ws.Cells(totalRow, 2).Formula = "=SUM(B" & firstRow & ":B" & totalRow - 1 & ")"
    ws.Cells(totalRow, 3).Formula = "=SUM(C" & firstRow & ":C" & totalRow - 1 & ")"
    ws.Cells(totalRow, 4).Formula = "=SUM(D" & firstRow & ":D" & totalRow - 1 & ")"

    With ws.Range(ws.Cells(totalRow, 1), ws.Cells(totalRow, lastCol)).Font
        .Bold = True
        .Name = "Arial"
    End With
    With ws.Range(ws.Cells(firstRow, 1), ws.Cells(totalRow, lastCol)).Borders
        .LineStyle = xlContinuous
        .Color = RGB(191, 191, 191)
    End With
End Sub


' =====================================================================
'  2. FlagExceptions
'     Highlights loans breaching the credit thresholds and reports the
'     count and balance at risk. This is the eyeball pass an analyst
'     does on every new tape.
' =====================================================================
Public Sub FlagExceptions()
    Dim tape As Worksheet
    Dim lastRow As Long, r As Long
    Dim flagged As Long
    Dim flaggedUPB As Double
    Dim isException As Boolean

    Set tape = GetSheet(TAPE_SHEET)
    If tape Is Nothing Then
        MsgBox "Sheet '" & TAPE_SHEET & "' not found.", vbExclamation, "Exceptions"
        Exit Sub
    End If

    lastRow = LastTapeRow(tape)
    If lastRow < FIRST_DATA_ROW Then Exit Sub

    On Error GoTo CleanFail
    Application.ScreenUpdating = False
    ' Stop Excel swallowing the exception column into the loan tape's table.
    Application.AutoCorrect.AutoExpandListRange = False

    ' Clear any previous pass so re-running does not accumulate marks.
    With tape.Range(tape.Cells(FIRST_DATA_ROW, 1), tape.Cells(lastRow, 13))
        .Interior.Pattern = xlNone
    End With
    tape.Range(tape.Cells(FIRST_DATA_ROW, EXC_COL), tape.Cells(lastRow, EXC_COL)).ClearContents

    tape.Cells(4, EXC_COL).Value = "Exception"
    StyleHeader tape.Cells(4, EXC_COL)

    For r = FIRST_DATA_ROW To lastRow
        ' A blank cell compares as Empty, and Empty < 620 is True — without
        ' the numeric guard an empty row would be flagged as a credit
        ' exception.
        isException = False
        If IsNumeric(tape.Cells(r, 6).Value) Then
            If tape.Cells(r, 6).Value > MAX_LTV Then isException = True
        End If
        If IsNumeric(tape.Cells(r, 5).Value) Then
            If tape.Cells(r, 5).Value < MIN_FICO Then isException = True
        End If
        If IsNumeric(tape.Cells(r, 7).Value) Then
            If tape.Cells(r, 7).Value > MAX_DTI Then isException = True
        End If

        If isException Then
            tape.Range(tape.Cells(r, 1), tape.Cells(r, 13)).Interior.Color = CLR_FLAG
            tape.Cells(r, EXC_COL).Value = ExceptionReason(tape, r)
            flagged = flagged + 1
            flaggedUPB = flaggedUPB + tape.Cells(r, 3).Value
        End If
    Next r

    tape.Columns(EXC_COL).ColumnWidth = 34
    Application.AutoCorrect.AutoExpandListRange = True
    Application.ScreenUpdating = True

    MsgBox flagged & " of " & Format$(lastRow - FIRST_DATA_ROW + 1, "#,##0") & _
           " loans flagged." & vbCrLf & _
           "Balance at risk: " & Format$(flaggedUPB, "$#,##0") & vbCrLf & vbCrLf & _
           "Tests: LTV > " & MAX_LTV & ", FICO < " & MIN_FICO & ", DTI > " & MAX_DTI, _
           vbInformation, "Exceptions"
    Exit Sub

CleanFail:
    Application.AutoCorrect.AutoExpandListRange = True
    Application.ScreenUpdating = True
    MsgBox "FlagExceptions failed: " & Err.Description, vbCritical, "Exceptions"
End Sub

' Builds the reason text so a reviewer sees why a loan was marked, not
' just that it was.
Private Function ExceptionReason(ByVal ws As Worksheet, ByVal r As Long) As String
    Dim parts As String

    If IsNumeric(ws.Cells(r, 6).Value) Then
        If ws.Cells(r, 6).Value > MAX_LTV Then
            parts = "LTV " & Format$(ws.Cells(r, 6).Value, "0.0")
        End If
    End If
    If IsNumeric(ws.Cells(r, 5).Value) Then
        If ws.Cells(r, 5).Value < MIN_FICO Then
            If Len(parts) > 0 Then parts = parts & "; "
            parts = parts & "FICO " & ws.Cells(r, 5).Value
        End If
    End If
    If IsNumeric(ws.Cells(r, 7).Value) Then
        If ws.Cells(r, 7).Value > MAX_DTI Then
            If Len(parts) > 0 Then parts = parts & "; "
            parts = parts & "DTI " & Format$(ws.Cells(r, 7).Value, "0.0")
        End If
    End If

    ExceptionReason = parts
End Function


' =====================================================================
'  3. RefreshAndStamp
'     Forces a full recalculation and records who refreshed the pack
'     and when. Surveillance output carries a P&L impact, so an audit
'     stamp is not decoration.
' =====================================================================
Public Sub RefreshAndStamp()
    Dim summary As Worksheet

    On Error GoTo CleanFail
    Application.ScreenUpdating = False

    Application.CalculateFullRebuild

    Set summary = GetSheet("Summary")
    If Not summary Is Nothing Then
        summary.Range("D1").Value = "Last refreshed " & _
            Format$(Now, "dd-mmm-yyyy hh:nn") & " by " & Application.UserName
        With summary.Range("D1").Font
            .Italic = True
            .Size = 9
            .Color = RGB(89, 89, 89)
        End With
    End If

    Application.ScreenUpdating = True
    MsgBox "Workbook fully recalculated and stamped.", vbInformation, "Refresh"
    Exit Sub

CleanFail:
    Application.ScreenUpdating = True
    MsgBox "RefreshAndStamp failed: " & Err.Description, vbCritical, "Refresh"
End Sub


' =====================================================================
'  4. ExportPackToPDF
'     Exports the review sheets to a single PDF next to the workbook,
'     which is how the pack actually gets circulated.
' =====================================================================
Public Sub ExportPackToPDF()
    Dim names As Variant, keep As Variant
    Dim i As Long, n As Long
    Dim ws As Worksheet
    Dim outPath As String

    names = Array("Summary", "Assumptions", "Stratification", _
                  "Exposure & RWA", "Scenario Stress")

    ' Only include sheets that are actually present.
    ReDim keep(0 To UBound(names))
    For i = LBound(names) To UBound(names)
        Set ws = GetSheet(CStr(names(i)))
        If Not ws Is Nothing Then
            keep(n) = ws.Name
            n = n + 1
        End If
    Next i

    If n = 0 Then
        MsgBox "None of the expected review sheets were found.", vbExclamation, "Export"
        Exit Sub
    End If
    ReDim Preserve keep(0 To n - 1)

    If ThisWorkbook.Path = "" Then
        MsgBox "Save the workbook once before exporting to PDF.", vbExclamation, "Export"
        Exit Sub
    End If

    On Error GoTo CleanFail
    outPath = ThisWorkbook.Path & Application.PathSeparator & _
              "surveillance_pack_" & Format$(Now, "yyyymmdd") & ".pdf"

    ThisWorkbook.Worksheets(keep).Select
    ActiveSheet.ExportAsFixedFormat Type:=xlTypePDF, Filename:=outPath, _
                                    Quality:=xlQualityStandard, _
                                    IgnorePrintAreas:=False, OpenAfterPublish:=False
    ThisWorkbook.Worksheets(1).Select

    MsgBox "Exported " & n & " sheets to:" & vbCrLf & outPath, vbInformation, "Export"
    Exit Sub

CleanFail:
    On Error Resume Next
    ThisWorkbook.Worksheets(1).Select
    MsgBox "ExportPackToPDF failed: " & Err.Description, vbCritical, "Export"
End Sub
