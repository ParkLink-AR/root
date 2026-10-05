#!/usr/bin/env python3
"""Fix bookings created before booking-service stored what the driver was actually
charged.

Back then `bookings.amount` held the owner's own price (without ParkLink's commission)
and `owner_amount` didn't exist yet, while Mercado Pago charged the price *with* the
commission. Two things go wrong with those rows:

  * the driver's app shows the amount without commission instead of what they paid;
  * the payout fallback (GeneratePendingPayoutsUseCase, owner_amount IS NULL) assumes
    `amount` includes the commission and takes it out again -- underpaying the owner.

For every booking with owner_amount IS NULL whose payment is on record in
payment-service, this sets:

    owner_amount := amount                       (the owner's price, as stored)
    amount       := what Mercado Pago charged     (transactions.amount, in centavos)

Only when the charge is actually larger than the stored amount (i.e. it does include a
commission on top). Bookings with no transaction on record (hand-seeded demo data) are
left untouched. Idempotent: an updated row has owner_amount set, so it's never picked
up again.

It also recomputes any payout already generated for one of those bookings that is still
PENDING and not yet in a settlement (gross = amount, net = owner_amount). Payouts already
drafted into a settlement or PAID are only listed, never changed -- those need a human.

Dry run by default -- prints what it would change. Run from the repository root:

    BOOKING_DATABASE_URL=postgresql://... PAYMENT_DATABASE_URL=postgresql://... \\
        python scripts/backfill_booking_charged_amounts.py           # dry run
    BOOKING_DATABASE_URL=... PAYMENT_DATABASE_URL=... \\
        python scripts/backfill_booking_charged_amounts.py --apply   # write

Requires psycopg2-binary, same as the other scripts here.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    args = parser.parse_args()

    booking_dsn = os.environ.get("BOOKING_DATABASE_URL")
    payment_dsn = os.environ.get("PAYMENT_DATABASE_URL")
    if not booking_dsn or not payment_dsn:
        print("BOOKING_DATABASE_URL and PAYMENT_DATABASE_URL are required", file=sys.stderr)
        return 2

    with psycopg2.connect(booking_dsn) as booking_db, psycopg2.connect(payment_dsn) as payment_db:
        with booking_db.cursor() as cursor:
            cursor.execute(
                "SELECT id::text, amount FROM bookings WHERE owner_amount IS NULL AND paid_at IS NOT NULL"
            )
            legacy = dict(cursor.fetchall())

        fix_pending_payouts(booking_db, args.apply)
        if not legacy:
            print("No bookings to fix.")
            return 0

        # The most recent payment per booking -- same choice payment-service makes when it
        # looks a booking's transaction up by external_reference.
        with payment_db.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (external_reference) external_reference, amount
                FROM transactions
                WHERE external_reference = ANY(%s)
                ORDER BY external_reference, created_at DESC
                """,
                (list(legacy),),
            )
            charged = {booking_id: round(float(amount) * 100) for booking_id, amount in cursor.fetchall()}

        updates = [
            (booking_id, stored, charged[booking_id])
            for booking_id, stored in legacy.items()
            if booking_id in charged and charged[booking_id] > stored
        ]
        skipped = len(legacy) - len(updates)

        for booking_id, stored, total in updates:
            print(f"{booking_id}: owner_amount := {stored}, amount {stored} -> {total}")
        print(f"\n{len(updates)} booking(s) to fix, {skipped} left as is (no payment on record or nothing to add).")

        if not args.apply:
            print("Dry run -- re-run with --apply to write.")
            return 0

        with booking_db.cursor() as cursor:
            for booking_id, stored, total in updates:
                cursor.execute(
                    """
                    UPDATE bookings
                    SET owner_amount = %s, amount = %s, updated_at = now()
                    WHERE id = %s AND owner_amount IS NULL
                    """,
                    (stored, total, booking_id),
                )
        booking_db.commit()
        print("Applied.")
        # The bookings just fixed may already have a payout computed from the old amount.
        fix_pending_payouts(booking_db, apply=True)
    return 0


def fix_pending_payouts(booking_db, apply: bool) -> None:
    """Payouts generated with the pre-owner_amount fallback (which took a commission out of
    the owner's own price). Fixes the still-PENDING, unsettled ones; lists the rest."""
    with booking_db.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.id::text, p.booking_id::text, p.net_amount, b.amount, b.owner_amount, p.status,
                   p.settlement_id IS NOT NULL
            FROM payouts p
            JOIN bookings b ON b.id = p.booking_id
            WHERE b.owner_amount IS NOT NULL
              AND (p.net_amount <> b.owner_amount OR p.gross_amount <> b.amount)
            """
        )
        rows = cursor.fetchall()
    fixable = [r for r in rows if r[5] == "PENDING" and not r[6]]
    for payout_id, booking_id, net, amount, owner_amount, status, settled in rows:
        action = "fix" if (status == "PENDING" and not settled) else "REVIEW BY HAND (already settled/paid)"
        print(f"payout {payout_id} (booking {booking_id}): net {net} -> {owner_amount} [{action}]")
    if not apply or not fixable:
        return
    with booking_db.cursor() as cursor:
        for payout_id, _, _, amount, owner_amount, _, _ in fixable:
            cursor.execute(
                """
                UPDATE payouts
                SET gross_amount = %s, commission_amount = %s, net_amount = %s
                WHERE id = %s AND status = 'PENDING' AND settlement_id IS NULL
                """,
                (amount, amount - owner_amount, owner_amount, payout_id),
            )
    booking_db.commit()
    print(f"Fixed {len(fixable)} pending payout(s).")


if __name__ == "__main__":
    sys.exit(main())
