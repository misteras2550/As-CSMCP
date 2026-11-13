"""
cash_sheet_logic.py

This file has ZERO MCP-specific code in it. It's plain Python that:
  1. Reads Toast's export for a given day
  2. Reads the nightly exception log for that same day
  3. Merges them into the buckets Kristen (the bookkeeper) actually needs

Keeping this separate from the MCP "wiring" (in server.py) is deliberate:
it means you can test and fix the actual business logic without touching
anything related to MCP at all. This file would look almost identical if
you were building a plain script instead of an MCP server.

Where the "exception log" actually comes from: the closing manager already
runs a nightly "Nightly Drop Review" (checking every server/captain drop,
reviewing event checks, sorting paperwork into five labeled pouches) that
has nothing to do with the Cash Sheet on its own -- but it happens to pass
right by everything Buckets A and B below need. The closing manager is
already looking at event checks for party deposits, and already pulling
gift certs, gift cards, and house accounts into the "Extraneous Items"
pouch each night. So the exception log this file reads isn't meant to be
a brand-new chore -- the plan is for it to be the last step of that
existing pass (typed into a shared sheet, or dictated via Whisper Flow),
filled out while that same paperwork is already in front of them. The
Cash in Hand / Tips Declared sheets from the Nightly Drop Review are a
separate, same-night accountability check and are NOT part of this
exception log -- Kristen doesn't need them, and this file doesn't read
them.
"""

import csv
import os

MOCK_DATA_DIR = os.path.join(os.path.dirname(__file__), "mock_data")


def _read_csv(path):
    """Read a CSV file into a list of dictionaries (one dict per row)."""
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _to_amount(row):
    """Toast/exception-log amounts come in as text ('85.00'); turn them into numbers."""
    try:
        return float(row.get("amount") or 0)
    except ValueError:
        return 0.0


def build_cash_sheet(date: str) -> dict:
    """
    The one function that does the real work.

    Given a date like '2026-09-15', this returns a dictionary shaped like
    the Cash Sheet Kristen described: mostly-Toast numbers, plus the three
    buckets of things Toast doesn't fully capture.
    """
    toast_path = os.path.join(MOCK_DATA_DIR, f"toast_export_{date}.csv")
    # "log_path" is the exception log -- see the module docstring above for
    # where this is meant to actually come from (the last step of the
    # closing manager's existing Nightly Drop Review, not a new task).
    log_path = os.path.join(MOCK_DATA_DIR, f"exception_log_{date}.csv")

    toast_rows = _read_csv(toast_path)
    log_rows = _read_csv(log_path)

    if not toast_rows:
        return {"date": date, "error": f"No Toast export found for {date}."}

    # ---- Straight from Toast ----
    sales = {r["label"]: _to_amount(r) for r in toast_rows if r["section"] == "sales"}
    tenders = {r["label"]: _to_amount(r) for r in toast_rows if r["section"] == "tender"}
    gift_card_add_values = [r for r in toast_rows if r["section"] == "giftcard_addvalue"]
    refunds = [r for r in toast_rows if r["section"] == "refund"]

    # Kristen's note: Toast's cash tender is rounded to the nearest whole
    # dollar for deposit purposes. This is the one adjustment that needs
    # zero manual input -- we just do the rounding here.
    raw_cash = tenders.get("Cash", 0.0)
    rounded_cash_for_deposit = round(raw_cash)

    # ---- Bucket A: back-end / after-close-out adjustments ----
    bucket_a = {
        "comp_donation_reclass": [r for r in log_rows if r["type"] == "comp_reclass"],
        "sales_type_corrections": [r for r in log_rows if r["type"] == "sales_type_correction"],
        "cash_rounding": {
            "toast_raw_cash": raw_cash,
            "rounded_for_deposit": rounded_cash_for_deposit,
        },
        # A refund only counts as a "comp needing a reason" if it has a note.
        # If Toast's refund-comment field turns out not to export at all,
        # every refund will land here with notes="" and someone will need
        # to fill the reason in by hand -- which is exactly the open
        # question flagged in the intake doc.
        "refunds_needing_reason": [r for r in refunds if not r.get("notes")],
        "refunds_with_reason": [r for r in refunds if r.get("notes")],
    }

    # ---- Bucket B: detail Toast doesn't (or might not) capture ----
    bucket_b = {
        "gift_card_add_values": gift_card_add_values,
        "paper_cert_redemptions": [r for r in log_rows if r["type"] == "paper_cert_redemption"],
        "party_deposits_applied": [r for r in log_rows if r["type"] == "party_deposit"],
        "no_show_fees": [r for r in log_rows if r["type"] == "no_show_fee"],
    }

    # ---- Bucket C: outside Toast entirely ----
    beginning = next((r for r in log_rows if r["type"] == "house_cash_beginning"), None)
    ending = next((r for r in log_rows if r["type"] == "house_cash_ending"), None)
    bucket_c = {
        "house_cash_beginning": _to_amount(beginning) if beginning else None,
        "house_cash_ending": _to_amount(ending) if ending else None,
        "paid_outs": [r for r in log_rows if r["type"] == "paid_out"],
    }

    return {
        "date": date,
        "toast_sales": sales,
        "toast_tenders": tenders,
        "bucket_a_backend_adjustments": bucket_a,
        "bucket_b_outside_toast_detail": bucket_b,
        "bucket_c_outside_toast_entirely": bucket_c,
    }


def format_cash_sheet_text(sheet: dict) -> str:
    """Turn the dictionary above into the plain-text sheet a human would read."""
    if "error" in sheet:
        return sheet["error"]

    lines = [f"CASH SHEET -- {sheet['date']}", "=" * 40, "", "TOAST SALES"]
    for label, amt in sheet["toast_sales"].items():
        lines.append(f"  {label:<20} ${amt:,.2f}")

    lines += ["", "TOAST TENDERS"]
    for label, amt in sheet["toast_tenders"].items():
        lines.append(f"  {label:<20} ${amt:,.2f}")

    a = sheet["bucket_a_backend_adjustments"]
    lines += ["", "BUCKET A -- BACK-END ADJUSTMENTS"]
    lines.append(
        f"  Cash deposit: Toast raw ${a['cash_rounding']['toast_raw_cash']:,.2f} "
        f"-> rounded ${a['cash_rounding']['rounded_for_deposit']:,.2f}"
    )
    for r in a["comp_donation_reclass"]:
        lines.append(f"  Comp/donation reclass: {r['detail']} -- ${_to_amount(r):,.2f} ({r['notes']})")
    for r in a["sales_type_corrections"]:
        lines.append(f"  Sales-type correction: {r['detail']} -- ${_to_amount(r):,.2f} ({r['notes']})")
    for r in a["refunds_with_reason"]:
        lines.append(f"  Refund (reason on file): ${_to_amount(r):,.2f} -- {r['notes']}")
    for r in a["refunds_needing_reason"]:
        lines.append(f"  ** Refund NEEDS A REASON **: ${_to_amount(r):,.2f} (nothing on file -- flag for Kristen)")

    b = sheet["bucket_b_outside_toast_detail"]
    lines += ["", "BUCKET B -- OUTSIDE-TOAST DETAIL"]
    for r in b["gift_card_add_values"]:
        lines.append(f"  Gift card ADD VALUE: ${_to_amount(r):,.2f} -- {r['notes']}")
    for r in b["paper_cert_redemptions"]:
        lines.append(f"  Paper cert redeemed: {r['detail']} -- ${_to_amount(r):,.2f}")
    for r in b["party_deposits_applied"]:
        lines.append(f"  Party deposit applied: {r['detail']} -- ${_to_amount(r):,.2f} ({r['notes']})")
    for r in b["no_show_fees"]:
        lines.append(f"  No-show fee: {r['detail']} -- ${_to_amount(r):,.2f}")

    c = sheet["bucket_c_outside_toast_entirely"]
    lines += ["", "BUCKET C -- OUTSIDE TOAST ENTIRELY"]
    lines.append(f"  House cash beginning: ${c['house_cash_beginning']:,.2f}")
    lines.append(f"  House cash ending:    ${c['house_cash_ending']:,.2f}")
    for r in c["paid_outs"]:
        lines.append(f"  Paid out: {r['detail']} -- ${_to_amount(r):,.2f} ({r['notes']})")

    return "\n".join(lines)
