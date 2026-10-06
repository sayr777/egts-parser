"""
setup_xlsm.py — generates EGTS_Analyzer.xlsm with VBA already embedded.

Usage:
    pip install pywin32
    python setup_xlsm.py

Requirements:
    - Windows
    - Microsoft Excel installed
    - pywin32 (pip install pywin32)

If you get "Programmatic access to VBA is not trusted":
    Excel → File → Options → Trust Center → Trust Center Settings
    → Macro Settings → check "Trust access to the VBA project object model"
"""

import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    # 1. Generate .xlsx + .bas via existing script
    print("Generating EGTS_Analyzer.xlsx and EGTSAnalyzer.bas ...")
    subprocess.run(
        [sys.executable, str(ROOT / "excel" / "create_workbook.py")],
        check=True,
    )

    xlsx_path = ROOT / "EGTS_Analyzer.xlsx"
    bas_path  = ROOT / "EGTSAnalyzer.bas"
    xlsm_path = ROOT / "EGTS_Analyzer.xlsm"

    for p in (xlsx_path, bas_path):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found after generate step")

    # 2. Open Excel via COM, import VBA, save as .xlsm
    try:
        import win32com.client
    except ImportError:
        sys.exit("ERROR: pywin32 not installed.\nRun: pip install pywin32")

    print("Opening Excel via COM ...")
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    try:
        wb = xl.Workbooks.Open(str(xlsx_path.resolve()))

        try:
            print(f"Importing {bas_path.name} ...")
            wb.VBProject.VBComponents.Import(str(bas_path.resolve()))
        except Exception as e:
            if "Programmatic access" in str(e) or "-2147352567" in str(e):
                sys.exit(
                    "\nERROR: Excel does not allow programmatic VBA access.\n"
                    "Fix in Excel:\n"
                    "  File → Options → Trust Center → Trust Center Settings\n"
                    "  → Macro Settings → check\n"
                    "  'Trust access to the VBA project object model'\n"
                    "Then re-run this script."
                )
            raise

        # 52 = xlOpenXMLWorkbookMacroEnabled (.xlsm)
        if xlsm_path.exists():
            xlsm_path.unlink()
        wb.SaveAs(str(xlsm_path.resolve()), FileFormat=52)
        wb.Close(False)
        print(f"\nDone: {xlsm_path}")
        print("Open EGTS_Analyzer.xlsm in Excel — macros are already embedded.")

    finally:
        xl.Quit()


if __name__ == "__main__":
    main()
