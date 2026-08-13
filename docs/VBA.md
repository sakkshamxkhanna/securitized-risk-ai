# VBA automation — `vba/SurveillanceTools.bas`

Four macros covering the repetitive parts of a monthly surveillance cycle on the workbook
produced by `src/excel_export.py`.

| Macro | What it does |
|---|---|
| `BuildStratification` | Cuts the loan tape into FICO and LTV bands on a fresh sheet, written as **live SUMIFS / SUMPRODUCT formulas** rather than pasted values |
| `FlagExceptions` | Highlights loans breaching credit thresholds (LTV > 90, FICO < 620, DTI > 45) and reports count plus balance at risk |
| `RefreshAndStamp` | Full recalculation, then stamps who refreshed the pack and when |
| `ExportPackToPDF` | Exports the review sheets to a dated PDF beside the workbook |

---

## You need real Excel

**Excel on the web and Google Sheets cannot run VBA.** Neither can LibreOffice — its Basic
dialect has a different object model. You need the Excel desktop app (Windows or Mac).

Check whether SVKM/NM College gives you a **Microsoft 365 education licence** with your
college email — most Indian universities do, and it includes desktop Excel at no cost.
Otherwise Microsoft offers a one-month free trial.

---

## Importing the module

1. Generate the workbook: `./export_pack.sh` → `output/surveillance_pack.xlsx`
2. Open it in Excel and **save as `.xlsm`** (Excel Macro-Enabled Workbook). A `.xlsx` cannot
   store macros — this is the step people miss.
3. Open the editor: **Windows** `Alt + F11` · **Mac** Tools → Macro → Visual Basic Editor
4. **File → Import File…** and choose `vba/SurveillanceTools.bas`
5. Run a macro: **Windows** `Alt + F8` · **Mac** Tools → Macro → Macros…, pick one, Run

On Mac you may be prompted to grant file access the first time `ExportPackToPDF` writes a PDF.

---

## Testing it

Run in this order and check each result:

1. **`BuildStratification`** → a `VBA Stratification` sheet appears. Click any UPB cell: the
   formula bar shows a `SUMIFS` against `'Loan Tape'`, not a number. Confirm the FICO block's
   `% of pool` totals to 100%.
2. **`FlagExceptions`** → rows highlight red, column P gives the reason, and a message box
   reports the count and balance at risk. **Run it twice** — the count must be identical, which
   proves the clear-down at the top of the macro works.
3. Change a FICO on the Loan Tape to `500` and re-run `FlagExceptions` → count rises by one.
4. **`RefreshAndStamp`** → Summary cell D1 shows the timestamp and your username.
5. **`ExportPackToPDF`** → a dated PDF appears next to the workbook.

If a macro fails, the message box names the procedure and the error — read it before changing
anything.

---

## What to be able to explain

Anything on your CV is fair game. For this module, be ready for:

**"Why write formulas instead of values?"**
A stratification of pasted numbers is a snapshot — it goes stale the moment the tape is
restated, and a restated tape is routine when a servicer corrects a remittance. Formulas mean
the cut stays live and a reviewer can trace any figure back to the loans behind it.

**"Walk me through the weighted-average coupon."**
`SUMPRODUCT((fico>=lo)*(fico<hi)*balance*coupon)/balance_in_band`. The two comparisons produce
arrays of TRUE/FALSE that coerce to 1/0, so multiplying them masks the band; multiplying by
balance and coupon sums the balance-weighted coupon, and dividing by the band's balance gives
the average. It is balance-weighted, not a simple mean — a simple mean would let a £50k loan
count the same as a £2mm one.

**"What does `Option Explicit` do?"**
Forces every variable to be declared. Without it a typo silently creates a new empty variable,
which in a spreadsheet macro means a wrong number rather than a crash.

**"Why disable `AutoExpandListRange`?"**
The loan tape is an Excel Table ending at column M. Writing in the adjacent column makes Excel
swallow it into the table and inherit its formatting. The macro turns the behaviour off, writes
to column P, and restores it — including in the error handler, so a failure does not leave the
setting changed.

**"Why the `IsNumeric` guards?"**
A blank cell reads as `Empty`, and `Empty < 620` evaluates True, so a blank row would be flagged
as a sub-620 FICO exception. The guard checks the cell holds a number before comparing.

**"Why turn off `ScreenUpdating`?"**
Excel repaints on every cell write. Off, a 2,000-row pass runs in about a second instead of
tens of seconds. It is restored in both the success and failure paths — otherwise a crash
leaves the user with a frozen-looking screen.

---

## Honest status

The module is written and statically checked — balanced blocks, no malformed literals, colour
constants verified against their RGB comments, every error label reachable. **It has not been
executed**, because the machine it was written on has no Excel installed.

Run the five steps above before you describe this as working. If something breaks, that is
normal for first-run VBA and fixing it is worth more to you than code that arrived working.
