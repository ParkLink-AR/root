#!/usr/bin/env python3
"""Create demo owners, a driver, and 800 active parking publications in CABA.

The operation is idempotent. Existing users are preserved and parking spots are
only added until the active-publication total reaches TARGET_ACTIVE_SPOTS.

Run from the repository root, for example:

    AUTH_DATABASE_URL=postgresql://... \
    PARKING_DATABASE_URL=postgresql://... \
    python scripts/seed_demo_data.py

The script requires psycopg2-binary and passlib, both already used by
`auth-service`.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import psycopg2
from passlib.context import CryptContext

TARGET_ACTIVE_SPOTS = 800
OWNER_COUNT = 50
DRIVER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
OWNER_NAMESPACE = uuid.UUID("10000000-0000-0000-0000-000000000000")
SPOT_NAMESPACE = uuid.UUID("20000000-0000-0000-0000-000000000000")
PASSWORD = os.getenv("SEED_PASSWORD", "Parklink2026!")

# Representative points distributed over CABA neighborhoods. The generated
# coordinates stay inside the city and are paired with a matching address.
NEIGHBORHOODS = [
    ("Microcentro", -34.6037, -58.3816),
    ("Palermo", -34.5889, -58.4200),
    ("Belgrano", -34.5627, -58.4583),
    ("Recoleta", -34.5888, -58.3974),
    ("San Telmo", -34.6219, -58.3732),
    ("Caballito", -34.6186, -58.4410),
    ("Almagro", -34.6038, -58.4173),
    ("Villa Urquiza", -34.5708, -58.4877),
    ("Villa Devoto", -34.6000, -58.5134),
    ("Núñez", -34.5450, -58.4616),
    ("La Boca", -34.6345, -58.3631),
    ("Flores", -34.6315, -58.4634),
    ("Barracas", -34.6465, -58.3814),
    ("Colegiales", -34.5735, -58.4490),
    ("Villa Crespo", -34.5998, -58.4380),
    ("Parque Chas", -34.5840, -58.4765),
]

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def database_url(name: str, default: str) -> str:
    return os.getenv(name, default)


def seed_users(connection) -> list[uuid.UUID]:
    owner_ids = []
    password_hash = pwd_context.hash(PASSWORD)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (
                id, email, phone, account_type, first_name, last_name, dni,
                birth_date, password_hash, email_verified, phone_verified, status
            ) VALUES (%s, %s, %s, 'DRIVER', %s, %s, %s, %s, %s, true, true, 'ACTIVE')
            ON CONFLICT (email) DO NOTHING
            """,
            (
                str(DRIVER_ID),
                "demo.conductor@parklink.com.ar",
                "+5491100000001",
                "Conductor",
                "Demo",
                "10000001",
                date(1990, 1, 1),
                password_hash,
            ),
        )

        for number in range(1, OWNER_COUNT + 1):
            owner_id = uuid.uuid5(OWNER_NAMESPACE, f"owner-{number}")
            owner_ids.append(owner_id)
            cursor.execute(
                """
                INSERT INTO users (
                    id, email, phone, account_type, first_name, last_name, dni,
                    birth_date, password_hash, email_verified, phone_verified, status
                ) VALUES (%s, %s, %s, 'OWNER', %s, %s, %s, %s, %s, true, true, 'ACTIVE')
                ON CONFLICT (email) DO NOTHING
                """,
                (
                    str(owner_id),
                    f"demo.propietario{number:02d}@parklink.com.ar",
                    f"+549110001{number:04d}",
                    f"Propietario {number:02d}",
                    "Demo",
                    str(20000000 + number),
                    date(1975, 1, 1),
                    password_hash,
                ),
            )
    connection.commit()
    return owner_ids


def seed_spots(connection, owner_ids: list[uuid.UUID]) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        if active_count > TARGET_ACTIVE_SPOTS:
            raise RuntimeError(
                f"La base ya tiene {active_count} publicaciones activas; "
                f"no se eliminaron datos para alcanzar {TARGET_ACTIVE_SPOTS}."
            )

        spots_to_add = TARGET_ACTIVE_SPOTS - active_count
        for offset in range(spots_to_add):
            sequence = active_count + offset + 1
            spot_id = uuid.uuid5(SPOT_NAMESPACE, f"spot-{sequence}")
            owner_id = owner_ids[offset % len(owner_ids)]
            neighborhood, lat, lng = NEIGHBORHOODS[offset % len(NEIGHBORHOODS)]
            # Small deterministic offsets avoid putting every generated spot at
            # exactly the same point while keeping all points in CABA.
            lat += ((offset // len(NEIGHBORHOODS)) % 7 - 3) * 0.0007
            lng += ((offset // len(NEIGHBORHOODS)) % 9 - 4) * 0.0007
            title = f"Cochera {neighborhood} {sequence:03d}"
            address = f"Calle {10 + sequence % 90} {100 + sequence % 8000}, {neighborhood}, CABA"

            cursor.execute(
                """
                INSERT INTO parking_spots (
                    id, owner_id, title, description, address, location,
                    hourly_enabled, price_per_hour, stay_enabled, covered,
                    vehicle_types, instant_booking, capacity, photos, rules, status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    true, %s, false, %s,
                    %s::jsonb, true, 1, '[]'::jsonb, '[]'::jsonb, 'active'
                )
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    str(spot_id),
                    str(owner_id),
                    title,
                    f"Publicación demo en {neighborhood}, Ciudad de Buenos Aires.",
                    address,
                    lng,
                    lat,
                    500 + sequence % 1000,
                    sequence % 2 == 0,
                    '["car"]',
                ),
            )

            for day in range(7):
                cursor.execute(
                    """
                    INSERT INTO parking_spot_schedules
                        (id, parking_spot_id, day_of_week, start_hour, end_hour)
                    VALUES (%s, %s, %s, 7, 23)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (str(uuid.uuid5(spot_id, f"schedule-{day}")), str(spot_id), day),
                )

        connection.commit()
        cursor.execute("SELECT COUNT(*) FROM parking_spots WHERE status = 'active'")
        return cursor.fetchone()[0]


def main() -> None:
    auth_url = database_url(
        "AUTH_DATABASE_URL",
        "postgresql://parklink_auth:parklink_auth@localhost:5432/parklink_auth_db",
    )
    parking_url = database_url(
        "PARKING_DATABASE_URL",
        "postgresql://parklink:parklink@localhost:5432/parking_service",
    )

    with psycopg2.connect(auth_url) as auth_connection:
        owner_ids = seed_users(auth_connection)

    with psycopg2.connect(parking_url) as parking_connection:
        active_count = seed_spots(parking_connection, owner_ids)

    print(
        f"Seed completado: {OWNER_COUNT} propietarios, 1 conductor y "
        f"{active_count} publicaciones activas en CABA."
    )
    print(f"Contraseña demo para todas las cuentas: {PASSWORD}")


if __name__ == "__main__":
    main()
