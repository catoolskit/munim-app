"""MUNIM Mobile Export — creates a config JSON for the mobile APK
and imports invoices JSON from the mobile APK."""
import json
import os
from datetime import date
from db import setup as s
from utils import settings


def export_mobile_config(con, out_path):
    """Export company config, parties, stock items and last invoice number
    to a JSON file for the mobile APK."""
    st = settings.load_settings()
    fy = s.fy_of(date.today())

    # Company details
    company = {
        "name":         st.get("company_name", ""),
        "address":      st.get("address", ""),
        "gstin":        st.get("gstin", ""),
        "state_name":   st.get("state_name", ""),
        "phone":        st.get("phone", ""),
        "invoice_prefix": st.get("invoice_prefix", ""),
        "gst_registered": st.get("gst_registered", True),
        "fy":           fy,
    }

    # Active parties only
    parties = []
    for p in s.list_parties(con):
        parties.append({
            "name":    p["name"],
            "ptype":   p["ptype"],
            "gstin":   p["gstin"] or "",
            "phone":   p["phone"] or "",
            "address": p["address"] or "",
        })

    # Stock items
    stock_items = []
    for it in s.list_stock_items(con):
        stock_items.append({
            "name":     it["name"],
            "hsn":      it["hsn"] or "",
            "unit":     it["unit"] or "pcs",
            "gst_rate": it["gst_rate"] or "0",
        })

    # Last invoice number for Sales in current FY
    last_vno = con.execute(
        "SELECT COALESCE(MAX(vno), 0) FROM vouchers WHERE vtype='Sales' AND fy=?",
        (fy,)).fetchone()[0]

    config = {
        "munim_version":  "v0.17",
        "exported_at":    date.today().isoformat(),
        "company":        company,
        "parties":        parties,
        "stock_items":    stock_items,
        "last_sales_vno": last_vno,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return out_path


def import_mobile_invoices(con, json_path, username="admin"):
    """Import invoices from a mobile JSON file into MUNIM.
    Auto-creates parties that don't exist.
    Returns dict with imported, skipped, errors lists."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    invoices = data.get("invoices", [])
    if not invoices:
        return {"imported": [], "skipped": [], "errors": []}

    imported, skipped, errors = [], [], []

    for inv in invoices:
        mob_id = inv.get("mobile_id", "?")
        try:
            # Check for duplicate (same mobile_id already imported)
            existing = con.execute(
                "SELECT id FROM vouchers WHERE narration LIKE ?",
                (f"%MOB-ID:{mob_id}%",)).fetchone()
            if existing:
                skipped.append(f"Invoice {inv.get('inv_no','?')} — already imported")
                continue

            party_name = inv.get("party", "").strip()
            ptype      = inv.get("party_type", "Customer")
            gstin      = inv.get("party_gstin", "").strip().upper()
            phone      = inv.get("party_phone", "").strip()
            address    = inv.get("party_address", "").strip()

            # Auto-create party if not found
            if party_name:
                exists = con.execute(
                    "SELECT 1 FROM parties WHERE name=?", (party_name,)).fetchone()
                if not exists:
                    s.add_party(con, party_name, ptype, gstin, phone, address)

            # Build invoice items
            items = inv.get("items", [])
            if not items:
                errors.append(f"Invoice {inv.get('inv_no','?')} — no items, skipped")
                continue

            # Compute totals
            taxable_total = 0
            cgst_total    = 0
            sgst_total    = 0
            igst_total    = 0
            interstate    = bool(inv.get("interstate", False))

            item_rows = []
            for seq, it in enumerate(items, 1):
                try:
                    qty      = float(it.get("qty", 0))
                    rate     = float(it.get("rate", 0))
                    gst_rate = float(it.get("gst_rate", 0))
                except (ValueError, TypeError):
                    continue
                amount_paise = s.to_paise(qty * rate)
                gst_paise    = s.to_paise(qty * rate * gst_rate / 100)
                taxable_total += amount_paise
                if interstate:
                    igst_total += gst_paise
                else:
                    cgst_total += gst_paise // 2
                    sgst_total += gst_paise // 2

                # Find stock item id
                sit = con.execute(
                    "SELECT id FROM stock_items WHERE name=? COLLATE NOCASE",
                    (it.get("name", ""),)).fetchone()
                stock_item_id = sit["id"] if sit else None

                item_rows.append({
                    "seq":          seq,
                    "description":  it.get("name", ""),
                    "hsn":          it.get("hsn", ""),
                    "qty":          str(qty),
                    "rate":         str(rate),
                    "gst":          str(gst_rate),
                    "amount_paise": amount_paise,
                    "stock_item_id": stock_item_id,
                })

            total_paise = taxable_total + cgst_total + sgst_total + igst_total

            # Build ledger lines
            vdate_str = inv.get("date", date.today().isoformat())
            vdate     = date.fromisoformat(vdate_str)
            narration = f"Mobile invoice | MOB-ID:{mob_id}"

            # Ensure GST accounts exist
            if not interstate:
                s.ensure_account(con, "Output CGST", "Duties & Taxes", "Liability")
                s.ensure_account(con, "Output SGST", "Duties & Taxes", "Liability")
            else:
                s.ensure_account(con, "Output IGST", "Duties & Taxes", "Liability")

            party_acc = party_name or "Cash"
            lines = [(party_acc, s.to_rupees(total_paise), 0),
                     ("Sales",   0, s.to_rupees(taxable_total))]
            if not interstate:
                if cgst_total:
                    lines.append(("Output CGST", 0, s.to_rupees(cgst_total)))
                if sgst_total:
                    lines.append(("Output SGST", 0, s.to_rupees(sgst_total)))
            else:
                if igst_total:
                    lines.append(("Output IGST", 0, s.to_rupees(igst_total)))

            # Post voucher
            vno = s.post_voucher(con, "Sales", vdate, narration, lines, username)

            # Get voucher id
            fy  = s.fy_of(vdate)
            vid = con.execute(
                "SELECT id FROM vouchers WHERE vtype='Sales' AND vno=? AND fy=?",
                (vno, fy)).fetchone()["id"]

            # Insert invoice record
            cur = con.execute(
                """INSERT INTO invoices(voucher_id, kind, party, interstate,
                   taxable, cgst, sgst, igst, total, customer_name, rcm)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (vid, "Sales", party_name, 1 if interstate else 0,
                 taxable_total, cgst_total, sgst_total, igst_total,
                 total_paise, inv.get("customer_name", party_name), 0))
            inv_id = cur.lastrowid

            # Insert invoice items
            for it in item_rows:
                con.execute(
                    """INSERT INTO invoice_items
                       (invoice_id, seq, description, hsn, qty, rate, gst, amount, stock_item_id)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (inv_id, it["seq"], it["description"], it["hsn"],
                     it["qty"], it["rate"], it["gst"],
                     it["amount_paise"], it["stock_item_id"]))

            con.commit()
            imported.append(f"Invoice {inv.get('inv_no','?')} — {party_name} — imported as Sales #{vno}")

        except Exception as e:
            con.rollback()
            errors.append(f"Invoice {mob_id}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}
