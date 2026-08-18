"""Generate a synthetic healthcare-wholesale email corpus for ATLAS trials.

Modelled on the *kinds* of mail a medical distributor like EBOS Group handles
(quotes, SAP orders, invoices, credits/returns, buy-in / direct ship, ETAs,
backorders, warehouse, AR, purchasing). All customers, staff, and document
numbers are fictional. Default output: examples/wholesale/
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "examples" / "wholesale"

COMPANY = "Helix Medical Distribution"
DOMAIN = "helixmed.internal"

STAFF = {
    "cs": ("Priya Nair", "priya.nair", "Customer Service"),
    "cs2": ("Daniel Crowe", "daniel.crowe", "Customer Service"),
    "quotes": ("Sophie Lang", "sophie.lang", "Pricing"),
    "credits": ("Helen Walsh", "helen.walsh", "Credits"),
    "ar": ("Marcus Bell", "marcus.bell", "Accounts Receivable"),
    "orders": ("Amy Tran", "amy.tran", "Order Processing"),
    "purchasing": ("James Okeke", "james.okeke", "Purchasing"),
    "warehouse": ("Lina Park", "lina.park", "Warehouse"),
    "logistics": ("Tom Rangi", "tom.rangi", "Logistics"),
}

CUSTOMERS = [
    ("Rivergate Private Hospital", "stores@rivergate.example", "NSW"),
    ("Waitaki Day Surgery", "purchasing@waitaki.example", "NZ"),
    ("Lakeside Pharmacy Group", "orders@lakeside.example", "VIC"),
    ("Oakwood Aged Care", "procurement@oakwood.example", "QLD"),
    ("Harbour Veterinary Hospital", "nurse@harbourvet.example", "NZ"),
    ("Capricorn Pathology", "supplies@capricornpath.example", "QLD"),
    ("Amberley Ambulance Service", "logistics@amberleyamb.example", "QLD"),
    ("Redfern Community Clinic", "admin@redfernclinic.example", "NSW"),
    ("Tasman Surgical Centre", "theatres@tasmansurgical.example", "TAS"),
    ("Kaimai Medical Centre", "practice@kaimai.example", "NZ"),
]

PRODUCTS = [
    ("GLV-NIT-100", "Nitrile exam gloves, medium, 100s", 8.40, True),
    ("GLV-NIT-200", "Nitrile exam gloves, large, 200s", 14.90, True),
    ("IVC-20G", "IV cannula 20G, box 50", 42.50, True),
    ("IVC-22G", "IV cannula 22G, box 50", 42.50, True),
    ("NDL-21G", "Hypodermic needle 21G x 1.5\", box 100", 6.20, True),
    ("SYR-10ML", "Luer slip syringe 10 mL, box 100", 18.75, True),
    ("DRP-ADH", "Adhesive wound dressing 10x10 cm, box 50", 27.40, True),
    ("FOAM-15", "Foam dressing 15x15 cm, box 10", 61.00, True),
    ("SHP-7L", "Sharps container 7 L yellow", 9.85, True),
    ("ALC-SWB", "Alcohol swabs, box 200", 4.10, True),
    ("ECG-50", "ECG electrodes, pack 50", 12.60, True),
    ("TUBE-EDTA", "EDTA blood tubes, rack 100", 22.00, True),
    ("SAN-500", "Hand sanitiser 500 mL", 5.90, True),
    ("GOWN-XL", "Surgical gown XL sterile, each", 6.45, True),
    ("DRAPE-OP", "Opsite-style drape 45x45, box 10", 38.20, True),
    ("VAC-FLU", "Influenza vaccine 10-dose vial (2–8 °C)", 86.00, True),
    ("INS-PEN", "Insulin pen needles 4 mm, box 100 (2–8 °C)", 19.40, True),
    ("SUT-3-0", "Vicryl-style suture 3-0, box 12", 74.50, False),
    ("IMP-HIP", "Revision hip liner (specialist)", 1840.00, False),
    ("CATH-SPC", "Specialty Foley 3-way 22Fr (buy-in)", 28.90, False),
    ("MESH-HER", "Hernia mesh 15x15 lightweight (buy-in)", 215.00, False),
    ("DRILL-BIT", "Ortho drill bit 3.2 mm (direct ship)", 96.00, False),
]

COURIERS = ["StarTrack", "NZ Couriers", "Direct Freight", "Helix fleet"]
DCS = ["Sydney DC", "Melbourne DC", "Auckland DC", "Brisbane DC"]

START = datetime(2026, 1, 6, 8, 40, tzinfo=None)


def addr(key: str) -> str:
    name, user, _dept = STAFF[key]
    return f"{name} <{user}@{DOMAIN}>"


def mailbox(key: str) -> str:
    return f"{STAFF[key][1]}@{DOMAIN}"


def write_eml(
    folder: Path,
    *,
    index: int,
    subject: str,
    sender: str,
    to: str,
    body: str,
    date: datetime,
    message_id: str,
    in_reply_to: str = "",
    cc: str = "",
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    msg = EmailMessage()
    msg["MIME-Version"] = "1.0"
    msg["Date"] = date.strftime("%a, %d %b %Y %H:%M:%S +1000")
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg["Subject"] = subject
    msg.set_content(body.strip() + "\n")
    (folder / f"{index:04d}.eml").write_bytes(msg.as_bytes())


def sig(key: str) -> str:
    name, user, dept = STAFF[key]
    return f"{name}\n{dept} | {COMPANY}\n{user}@{DOMAIN} | +61 2 9000 4400"


def order_no(rng: random.Random) -> str:
    return f"45{rng.randint(1000000, 9999999)}"


def ra_no(rng: random.Random) -> str:
    return f"RA-{rng.randint(24000, 28999)}"


def inv_no(rng: random.Random) -> str:
    return f"INV-{rng.randint(910000, 989999)}"


def consignment(rng: random.Random) -> str:
    return f"HMD{rng.randint(100000, 999999)}"


def when(rng: random.Random) -> datetime:
    return START + timedelta(days=rng.randint(0, 200), hours=rng.randint(0, 9), minutes=rng.randint(0, 59))


def product(rng: random.Random, stocked: bool | None = None):
    pool = [p for p in PRODUCTS if stocked is None or p[3] is stocked]
    return rng.choice(pool)


def customer(rng: random.Random):
    return rng.choice(CUSTOMERS)


def policy_emails(out: Path) -> int:
    folder = out / "policy"
    n = 0
    policies = [
        (
            "SOP-CS-014 Returns and credits",
            "credits",
            """Team,

SOP-CS-014 is current from 1 March 2026.

- Unused, original carton, 14 days from invoice date: raise an RA in SAP before collecting stock.
- Opened sterile lines, cold-chain product, and buy-in / direct-ship lines are not returnable unless Helix supplied in error.
- Credits team issues the G2 credit note within 5 business days of the warehouse receipt posting.
- Do not tell the customer to “just send it back”. No RA, no credit.
- Short-dated (under 90 days) requires Credits + Purchasing sign-off.

Send RA queries to helen.walsh@helixmed.internal and copy the original sales order.""",
        ),
        (
            "SOP-CS-018 Damaged, wet, or contaminated deliveries",
            "credits",
            """Damaged-in-transit process SOP-CS-018 (current 1 March 2026):

If a customer reports leakage, wet cartons, crushed packaging, or product ruined in the same consignment:

- This is treated as Helix / carrier error, not a change-of-mind return. Do not apply buy-in firm-sale rules.
- Tell the customer not to use the stock. Quarantine at their site until Credits confirms collection or destruction.
- CS raises an RA the same day (reason: damaged in transit) and a replacement sales order if the customer still needs the lines urgently. Replacement uses stocked ATP; if the line was buy-in, Purchasing must confirm a new supplier PO.
- Photo of the carton and consignment / order number go to Credits (helen.walsh@helixmed.internal) and Logistics (tom.rangi@helixmed.internal).
- G2 credit follows the RA receipt or documented destruction. Replacement is a new order, not a free-text promise.
- Do not mix damaged units back into pick face.

This SOP sits beside SOP-CS-014 (unused returns) and SOP-TMS-008 (delivery ETAs).""",
        ),
        (
            "SOP-PRC-006 Buy-in and direct ship",
            "purchasing",
            """Buy-in / direct ship rules (SOP-PRC-006):

A buy-in is a non-stocked line purchased for one customer. A direct ship is supplier-to-customer; Helix still invoices.

- Flag the line as buy-in in SAP. Do not promise DC stock or same-day dispatch.
- Standard lead time is 5–10 business days once the supplier confirms. Theatre dates must be on the PO.
- Buy-in and direct ship are firm sale: no returns, no cancels after the supplier PO is sent.
- Direct ship POD comes from the supplier. Logistics will not have a Helix consignment until the supplier ASN is in.
- If the customer later wants the item as a stocked line, raise it with Purchasing — do not keep a silent overstock in the DC.

Purchasing inbox: james.okeke@helixmed.internal.""",
        ),
        (
            "SOP-OTC-003 Quotes and contract pricing",
            "quotes",
            """Quotation rules SOP-OTC-003:

- One-off quotes are valid 30 days. After that, re-price from the current SAP condition.
- Hospital contract prices (state health / private group) override the list price. Do not quote list if a contract exists.
- MOQ and carton multiples still apply on contract.
- Cold-chain and buy-in lines must show lead time and ‘firm sale’ on the quote PDF.
- Price queries on an existing invoice are not quotes — send those to Accounts Receivable with the invoice number.

Pricing: sophie.lang@helixmed.internal.""",
        ),
        (
            "SOP-FIN-011 Invoice queries",
            "ar",
            """Invoice query process SOP-FIN-011:

- Customer must quote INV-###### and the Helix sales order.
- Price variance: AR checks the SAP condition vs the quote. If we invoiced list by mistake, AR raises the credit; CS does not verbally agree a new price.
- Duplicate invoice: AR reverses the later document. Do not ask the customer to ignore it.
- Missing invoice / not received: AR reissues PDF; do not create a new invoice.
- GST on medical devices: taxable unless the line is GST-free in SAP. Do not change tax codes in email.

AR: marcus.bell@helixmed.internal. Target response: 2 business days.""",
        ),
        (
            "SOP-WH-009 Warehouse pick, short pick, and POD",
            "warehouse",
            """Warehouse SOP-WH-009:

- Short pick: post the shortage in SAP the same day and email CS with the order, SKU, and quantity short.
- Do not substitute without CS confirmation on the sales order.
- POD for Helix fleet and StarTrack is attached to the consignment in TMS within 24 hours of delivery.
- Direct-ship POD is the supplier’s. Warehouse will not have a Helix scan.
- Credits stock must be booked to returns location RET-01, not mixed back into pick face until QA.

Sydney / Melbourne / Brisbane / Auckland DCs follow the same posting rules.""",
        ),
        (
            "SOP-TMS-008 Delivery enquiries and ETAs",
            "logistics",
            """Delivery enquiries SOP-TMS-008:

- First check SAP for GI date and TMS consignment (HMD######).
- Metro metro AU: next business day if packed before 14:00 from the local DC.
- Inter-island NZ and TAS: 2–4 business days plus any booking slot.
- If the courier scan has not moved for 24 hours, Logistics chases the carrier. CS should not give a made-up ETA.
- Failed delivery / closed dock: we rebook once. A second fail is charged.
- Cold chain must stay 2–8 °C; if a logger is out of range, do not tell the customer to use the stock — quarantine and call Quality.

Logistics: tom.rangi@helixmed.internal.""",
        ),
        (
            "SOP-OTC-011 Backorders and ATP",
            "orders",
            """Backorders SOP-OTC-011:

- If ATP cannot cover the order, put the balance on backorder. Do not delete the line to ‘make it ship’.
- Give the customer the next inbound PO ETA from Purchasing, not a guess.
- Partial ship is the default unless the customer is marked complete-delivery.
- When inbound goods receipt posts, backorders allocate overnight. CS can promise ‘allocated tomorrow’ only after GR.
- Substitutes need customer approval in writing on the order.

Order processing: amy.tran@helixmed.internal.""",
        ),
        (
            "SOP-AR-004 Credit terms and collections",
            "ar",
            """Credit terms SOP-AR-004:

- Standard terms 30 days EOM unless Credit has approved 45 or 60.
- Stop-supply at 15 days past due on the oldest invoice, after one courtesy call.
- Credits (G2) reduce the open item; they are not cash refunds unless Credit Control approves.
- Do not tell a customer they can ‘take it off the next payment’ unless AR has applied the credit note.

Copy marcus.bell@helixmed.internal on any stop-supply discussion.""",
        ),
    ]
    date = datetime(2026, 3, 1, 9, 15)
    for subject, owner, body in policies:
        n += 1
        write_eml(
            folder,
            index=n,
            subject=subject,
            sender=addr(owner),
            to=f"All Staff <all-staff@{DOMAIN}>",
            body=body + "\n\n" + sig(owner),
            date=date,
            message_id=f"<policy-{n}@{DOMAIN}>",
        )
        date += timedelta(days=2)
    return n


def thread_quote(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, price, _stock = product(rng, stocked=True)
    qty = rng.choice([10, 20, 40, 100])
    qid = f"<quote-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"RFQ — {desc} for {cust} ({state})",
        sender=f"{cust} Purchasing <{email}>",
        to=addr("quotes"),
        body=(
            f"Hi Sophie,\n\n"
            f"Please quote {qty} cartons of {sku} ({desc}) for delivery to our {state} site.\n"
            f"We are currently paying about ${price * 0.92:.2f} from another wholesaler.\n"
            f"Need this priced as a 12-month estimate, GST exclusive, and confirm MOQ / carton multiple.\n"
            f"If a hospital contract price exists, use that rather than list.\n\n"
            f"Thanks,\nPurchasing\n{cust}"
        ),
        date=date,
        message_id=qid,
    )
    n += 1
    contract = rng.choice([True, False])
    offer = price * (0.88 if contract else 0.97)
    write_eml(
        folder,
        index=n,
        subject=f"Re: RFQ — {desc} for {cust} ({state})",
        sender=addr("quotes"),
        to=f"{cust} Purchasing <{email}>",
        body=(
            f"Hi,\n\n"
            f"Quote Q-{rng.randint(80000, 89999)} for {cust}. Valid 30 days (SOP-OTC-003).\n"
            f"- {sku} {desc}: ${offer:.2f} per carton GST excl, MOQ {rng.choice([5, 10])} cartons.\n"
            f"- {'State health / group contract applied.' if contract else 'No contract on file — this is a one-off net price, not list.'}\n"
            f"- Stocked at {rng.choice(DCS)}. Standard lead time 1–2 business days if packed before 14:00.\n"
            f"- Convert to a sales order by replying with your PO. After 30 days we re-price.\n\n"
            + sig("quotes")
        ),
        date=date + timedelta(hours=3),
        message_id=f"<quote-{n}@{DOMAIN}>",
        in_reply_to=qid,
    )
    return n


def thread_order(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, price, _stock = product(rng, stocked=True)
    oid = order_no(rng)
    qty = rng.choice([4, 8, 12, 24])
    mid = f"<ord-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"PO {rng.randint(10000, 99999)} — please raise SAP order {desc}",
        sender=f"{cust} Stores <{email}>",
        to=addr("cs"),
        body=(
            f"Hi Helix CS,\n\n"
            f"Please raise a sales order for {qty} x {sku} {desc} to our {state} dock.\n"
            f"PO attached in our system as {cust[:3].upper()}-{rng.randint(1000, 9999)}.\n"
            f"Need delivery this week if ATP allows. Loading dock closes 15:30.\n\n"
            f"Stores\n{cust}"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    write_eml(
        folder,
        index=n,
        subject=f"Re: PO — SAP {oid} confirmed {desc}",
        sender=addr("orders"),
        to=f"{cust} Stores <{email}>",
        cc=addr("cs"),
        body=(
            f"Order {oid} is in SAP (VA01) for {cust}.\n\n"
            f"{qty} x {sku} at ${price:.2f} GST excl. ATP confirmed from {rng.choice(DCS)}.\n"
            f"Packed today if we GI before 14:00, otherwise tomorrow.\n"
            f"Complete-delivery is off — we will partial ship if a later line appears.\n\n"
            + sig("orders")
        ),
        date=date + timedelta(hours=2),
        message_id=f"<ord-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_backorder(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, price, _stock = product(rng, stocked=True)
    oid = order_no(rng)
    mid = f"<bo-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"Backorder on {oid} — {sku} still showing zero ATP",
        sender=f"{cust} <{email}>",
        to=addr("cs"),
        body=(
            f"We only received {rng.randint(2, 6)} of {rng.randint(10, 20)} cartons of {sku} ({desc}) on order {oid}.\n"
            f"Theatre is {rng.choice(['Thursday', 'Monday', 'next Wednesday'])}. What is the rest of the backorder ETA?\n"
            f"Do not substitute without email confirmation.\n\n{cust} ({state})"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    eta = (date + timedelta(days=rng.randint(3, 12))).strftime("%d %b")
    write_eml(
        folder,
        index=n,
        subject=f"Re: Backorder on {oid} — {sku}",
        sender=addr("orders"),
        to=f"{cust} <{email}>",
        cc=addr("purchasing"),
        body=(
            f"Confirmed under SOP-OTC-011.\n\n"
            f"Order {oid}: shipped quantity posted, remainder is on backorder against inbound PO {rng.randint(4500000, 4599999)}.\n"
            f"Purchasing ETA at {rng.choice(DCS)} is {eta}. Allocation runs overnight after goods receipt.\n"
            f"We have not substituted {sku}. Unit price remains ${price:.2f}.\n\n"
            + sig("orders")
        ),
        date=date + timedelta(hours=4),
        message_id=f"<bo-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_invoice(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, list_price, _stock = product(rng, stocked=True)
    inv = inv_no(rng)
    oid = order_no(rng)
    mid = f"<inv-{n}@{DOMAIN}>"
    date = when(rng)
    billed = list_price
    expected = list_price * 0.9
    write_eml(
        folder,
        index=n,
        subject=f"Price variance {inv} vs quote — {sku}",
        sender=f"{cust} Accounts <{email}>",
        to=addr("ar"),
        body=(
            f"Hello AR,\n\n"
            f"Invoice {inv} for order {oid} billed {sku} at ${billed:.2f}.\n"
            f"Our quote / contract is ${expected:.2f} GST excl.\n"
            f"Please check SAP conditions and issue a credit for the difference if we were billed list in error.\n"
            f"We will not short-pay until we have a credit note number.\n\n"
            f"Accounts\n{cust} ({state})"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    cn = f"CN-{rng.randint(50000, 59999)}"
    write_eml(
        folder,
        index=n,
        subject=f"Re: Price variance {inv} — credit {cn}",
        sender=addr("ar"),
        to=f"{cust} Accounts <{email}>",
        body=(
            f"Checked under SOP-FIN-011.\n\n"
            f"{inv} used list price. Contract condition should have applied.\n"
            f"G2 credit {cn} raised for ${billed - expected:.2f} GST excl on {sku}. It will show on your next statement.\n"
            f"This is not a cash refund. Original invoice {inv} stays; the credit reduces the open item.\n\n"
            + sig("ar")
        ),
        date=date + timedelta(days=1),
        message_id=f"<inv-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_credit(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, _price, stocked = product(rng)
    ra = ra_no(rng)
    oid = order_no(rng)
    inv = inv_no(rng)
    mid = f"<cr-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"Return request {sku} — order {oid} invoice {inv}",
        sender=f"{cust} <{email}>",
        to=addr("cs"),
        body=(
            f"Hi CS,\n\n"
            f"We need to return {rng.randint(1, 6)} x {sku} ({desc}) from order {oid} / {inv}.\n"
            f"Reason: {rng.choice(['over-ordered', 'wrong size sent', 'duplicate delivery', 'short dated on arrival'])}.\n"
            f"Cartons are unopened. Please send an RA and collection.\n"
            f"Site is {cust}, {state}.\n"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    if not stocked:
        decision = (
            f"This line is buy-in / non-stocked. Under SOP-CS-014 and SOP-PRC-006 it is firm sale "
            f"unless Helix supplied in error. We cannot raise RA {ra} for a change-of-mind return.\n"
            f"If the goods were faulty or the wrong SKU, reply with photos and lot numbers and Credits will review."
        )
    else:
        decision = (
            f"RA {ra} raised. Unused original carton, 14-day window from {inv} applies.\n"
            f"Warehouse will collect to RET-01. G2 credit within 5 business days of receipt posting.\n"
            f"Do not send stock without the RA on the carton."
        )
    write_eml(
        folder,
        index=n,
        subject=f"Re: Return request {sku} — {ra if stocked else 'not returnable'}",
        sender=addr("credits"),
        to=f"{cust} <{email}>",
        cc=addr("cs"),
        body=decision + "\n\n" + sig("credits"),
        date=date + timedelta(hours=5),
        message_id=f"<cr-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_damage(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, _price, stocked = product(rng, stocked=True)
    oid = order_no(rng)
    ra = ra_no(rng)
    cons = consignment(rng)
    mid = f"<dmg-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"Damaged delivery — liquid leaked through order {oid}",
        sender=f"{cust} <{email}>",
        to=addr("cs"),
        body=(
            f"Hi CS,\n\n"
            f"Consignment {cons} arrived at {cust} ({state}) with liquid spilled through the carton.\n"
            f"The {sku} ({desc}) from order {oid} is ruined and we cannot use it.\n"
            f"Please quarantine, raise an RA, and send a replacement today if stock allows.\n"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    write_eml(
        folder,
        index=n,
        subject=f"Re: Damaged delivery {oid} — {ra} + replacement",
        sender=addr("credits"),
        to=f"{cust} <{email}>",
        cc=f"{addr('cs')}, {addr('logistics')}",
        body=(
            f"SOP-CS-018 applies: wet / leaked cartons are Helix or carrier error, not a change-of-mind return.\n"
            f"Do not apply buy-in firm-sale rules. Customer must not use the stock.\n"
            f"RA {ra} raised (reason: damaged in transit). Replacement sales order to follow from ATP"
            f"{'' if stocked else ' after Purchasing confirms a new supplier PO'}.\n"
            f"Photos and consignment {cons} copied to Logistics. G2 credit after RA receipt or documented destruction.\n\n"
            + sig("credits")
        ),
        date=date + timedelta(hours=3),
        message_id=f"<dmg-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_buyin(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    sku, desc, price, _stock = product(rng, stocked=False)
    oid = order_no(rng)
    mid = f"<bi-{n}@{DOMAIN}>"
    date = when(rng)
    theatre = rng.choice(["12 May", "3 Jun", "18 Jun", "7 Jul"])
    write_eml(
        folder,
        index=n,
        subject=f"Buy-in / direct ship needed — {sku} for {theatre} case",
        sender=f"{cust} Theatres <{email}>",
        to=addr("cs"),
        body=(
            f"Hi Helix,\n\n"
            f"We need {rng.randint(1, 4)} x {sku} ({desc}) for a case on {theatre} at {cust} ({state}).\n"
            f"This is not a stocked glove/syringe line — please buy in or direct ship.\n"
            f"Confirm lead time, firm-sale terms, and whether Helix or the supplier delivers.\n"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    direct = rng.choice([True, False])
    write_eml(
        folder,
        index=n,
        subject=f"Re: Buy-in {sku} — order {oid}",
        sender=addr("purchasing"),
        to=f"{cust} Theatres <{email}>",
        cc=f"{addr('cs')}, {addr('logistics')}",
        body=(
            f"Order {oid} raised as {'direct ship' if direct else 'buy-in'} under SOP-PRC-006.\n\n"
            f"{sku} is not held in a Helix DC. Supplier lead time 5–10 business days from PO send.\n"
            f"Price ${price:.2f} GST excl, firm sale — no cancel, no return once the supplier PO is sent.\n"
            f"{'Supplier ships to your dock; Helix invoices. POD will be the supplier POD, not an HMD consignment.' if direct else 'Stock will receipt at DC then we will forward on Helix fleet / StarTrack.'}\n"
            f"Theatre date {theatre} is on the PO. If the date moves, tell us before we send the supplier PO.\n\n"
            + sig("purchasing")
        ),
        date=date + timedelta(hours=6),
        message_id=f"<bi-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_delivery(rng: random.Random, folder: Path, n: int) -> int:
    cust, email, state = customer(rng)
    oid = order_no(rng)
    con = consignment(rng)
    courier = rng.choice(COURIERS)
    sku, desc, _p, _s = product(rng, stocked=True)
    mid = f"<del-{n}@{DOMAIN}>"
    date = when(rng)
    write_eml(
        folder,
        index=n,
        subject=f"Where is consignment {con}? Order {oid}",
        sender=f"{cust} Receiving <{email}>",
        to=addr("cs"),
        body=(
            f"We have not received {sku} ({desc}) on order {oid}.\n"
            f"Helix said it left {rng.choice(DCS)} yesterday with {courier}, consignment {con}.\n"
            f"Dock closes 15:30. Please send POD or a real ETA — not ‘it’s on the truck’.\n"
            f"{cust} ({state})"
        ),
        date=date,
        message_id=mid,
    )
    n += 1
    eta = rng.choice(["today 14:00–16:00", "tomorrow AM", "rebooked after failed delivery"])
    write_eml(
        folder,
        index=n,
        subject=f"Re: Consignment {con} — ETA update",
        sender=addr("logistics"),
        to=f"{cust} Receiving <{email}>",
        cc=addr("cs"),
        body=(
            f"TMS checked under SOP-TMS-008.\n\n"
            f"GI posted on {oid}. Consignment {con} with {courier}.\n"
            f"Last scan: {rng.choice(['on board for delivery', 'at depot', 'out for delivery', 'card left — closed dock'])}.\n"
            f"ETA: {eta}. If this is a second failed delivery there will be a redelivery fee.\n"
            f"POD will sit on the consignment within 24 hours of a successful drop.\n\n"
            + sig("logistics")
        ),
        date=date + timedelta(hours=2),
        message_id=f"<del-{n}@{DOMAIN}>",
        in_reply_to=mid,
    )
    return n


def thread_internal(rng: random.Random, folder: Path, n: int, kind: str) -> int:
    cust, _email, state = customer(rng)
    sku, desc, _p, _s = product(rng, stocked=True)
    oid = order_no(rng)
    date = when(rng)
    if kind == "credits":
        ra = ra_no(rng)
        write_eml(
            folder,
            index=n,
            subject=f"Internal — please post RA {ra} for {cust}",
            sender=addr("cs"),
            to=addr("credits"),
            cc=addr("warehouse"),
            body=(
                f"Helen — customer {cust} ({state}) returned {sku} against order {oid}.\n"
                f"CS has quoted SOP-CS-014 (unopened, inside 14 days). Can you raise {ra} and ask Warehouse to collect to RET-01?\n"
                f"Do not credit until GR of the return.\n\n"
                + sig("cs")
            ),
            date=date,
            message_id=f"<int-cr-{n}@{DOMAIN}>",
        )
        n += 1
        write_eml(
            folder,
            index=n,
            subject=f"Re: RA {ra} posted",
            sender=addr("credits"),
            to=addr("cs"),
            body=(
                f"{ra} is in SAP. Collection booked. G2 will follow within 5 days of RET-01 receipt.\n"
                f"I have told Warehouse not to mix {sku} back into pick face until QA.\n\n"
                + sig("credits")
            ),
            date=date + timedelta(hours=1),
            message_id=f"<int-cr-{n}@{DOMAIN}>",
            in_reply_to=f"<int-cr-{n-1}@{DOMAIN}>",
        )
        return n
    if kind == "ar":
        inv = inv_no(rng)
        write_eml(
            folder,
            index=n,
            subject=f"Internal — stop-supply check {cust} {inv}",
            sender=addr("cs"),
            to=addr("ar"),
            body=(
                f"Marcus — {cust} wants another order for {desc}. Oldest open item {inv} looks 20 days past due.\n"
                f"SOP-AR-004 is stop-supply at 15 days after one call. Are they released or on hold?\n"
                f"I will not promise dispatch until you confirm.\n\n"
                + sig("cs")
            ),
            date=date,
            message_id=f"<int-ar-{n}@{DOMAIN}>",
        )
        n += 1
        write_eml(
            folder,
            index=n,
            subject=f"Re: stop-supply {cust}",
            sender=addr("ar"),
            to=addr("cs"),
            body=(
                f"Hold stays on until {inv} is paid or a payment plan is in Credit Control.\n"
                f"Do not tell stores it will ship. New orders can sit parked in SAP.\n\n"
                + sig("ar")
            ),
            date=date + timedelta(hours=1),
            message_id=f"<int-ar-{n}@{DOMAIN}>",
            in_reply_to=f"<int-ar-{n-1}@{DOMAIN}>",
        )
        return n
    if kind == "purchasing":
        write_eml(
            folder,
            index=n,
            subject=f"Internal — inbound ETA for {sku} backorders",
            sender=addr("orders"),
            to=addr("purchasing"),
            body=(
                f"James — {sku} ATP is zero. Several backorders including {oid} ({cust}).\n"
                f"What is the supplier PO and DC GR date? CS is being asked for theatre ETAs.\n\n"
                + sig("orders")
            ),
            date=date,
            message_id=f"<int-pur-{n}@{DOMAIN}>",
        )
        n += 1
        write_eml(
            folder,
            index=n,
            subject=f"Re: inbound {sku}",
            sender=addr("purchasing"),
            to=addr("orders"),
            body=(
                f"Supplier PO {rng.randint(780000, 789999)} due {rng.choice(DCS)} "
                f"{(date + timedelta(days=rng.randint(2, 8))).strftime('%d %b')}.\n"
                f"ASN not yet in. Do not promise ‘tomorrow’ until GR posts. Then backorders allocate overnight.\n\n"
                + sig("purchasing")
            ),
            date=date + timedelta(hours=2),
            message_id=f"<int-pur-{n}@{DOMAIN}>",
            in_reply_to=f"<int-pur-{n-1}@{DOMAIN}>",
        )
        return n
    # warehouse
    write_eml(
        folder,
        index=n,
        subject=f"Internal — short pick {oid} {sku}",
        sender=addr("warehouse"),
        to=addr("cs"),
        cc=addr("orders"),
        body=(
            f"Short pick on {oid} for {cust}: {sku} {desc}, {rng.randint(1, 4)} carton(s) short vs pick ticket.\n"
            f"Posted in SAP today per SOP-WH-009. Location empty. Not substituted.\n"
            f"Please tell the customer the balance is backorder, not lost in transit.\n\n"
            + sig("warehouse")
        ),
        date=date,
        message_id=f"<int-wh-{n}@{DOMAIN}>",
    )
    n += 1
    write_eml(
        folder,
        index=n,
        subject=f"Re: short pick {oid}",
        sender=addr("cs"),
        to=addr("warehouse"),
        body=(
            f"Noted. CS will email {cust} that {oid} is partial and the rest is backorder, not a missing consignment.\n"
            f"Thanks for posting the same day.\n\n"
            + sig("cs")
        ),
        date=date + timedelta(minutes=40),
        message_id=f"<int-wh-{n}@{DOMAIN}>",
        in_reply_to=f"<int-wh-{n-1}@{DOMAIN}>",
    )
    return n


def generate(out: Path, count: int, seed: int) -> int:
    rng = random.Random(seed)
    if out.exists():
        for old in out.rglob("*.eml"):
            old.unlink()
    n = policy_emails(out)
    builders = (
        [(thread_quote, out / "quotes")] * 8
        + [(thread_order, out / "orders")] * 12
        + [(thread_backorder, out / "backorders")] * 8
        + [(thread_invoice, out / "invoices")] * 8
        + [(thread_credit, out / "credits")] * 10
        + [(thread_damage, out / "credits")] * 3
        + [(thread_buyin, out / "buyin")] * 8
        + [(thread_delivery, out / "deliveries")] * 9
        + [(lambda r, f, i: thread_internal(r, f, i, "credits"), out / "internal")] * 4
        + [(lambda r, f, i: thread_internal(r, f, i, "ar"), out / "internal")] * 4
        + [(lambda r, f, i: thread_internal(r, f, i, "purchasing"), out / "internal")] * 4
        + [(lambda r, f, i: thread_internal(r, f, i, "warehouse"), out / "internal")] * 5
    )
    while n < count:
        fn, folder = rng.choice(builders)
        n = fn(rng, folder, n + 1)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Helix wholesale trial emails")
    parser.add_argument("--count", type=int, default=700)
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    total = generate(args.out, args.count, args.seed)
    print(f"Wrote {total} messages under {args.out}")
    for folder in sorted(p for p in args.out.iterdir() if p.is_dir()):
        print(f"  {folder.name:12} {len(list(folder.glob('*.eml')))}")


if __name__ == "__main__":
    main()
