#!/usr/bin/env python3
"""Seed (or remove) a large number of demo parking spots spread across CABA,
for showing off a zoomed-out map full of pins/prices in a demo.

Unlike `seed_demo_data.py` (which stacks ~50 spots within a few hundred
meters of each of 16 fixed points), this spreads spots out using rejection
sampling so no two are closer than MIN_DISTANCE_METERS -- zoomed out, the
city reads as densely covered instead of a handful of tight clusters.

Idempotent and self-contained: every spot this script creates gets the same
recognizable marker in its description ("[parklink-demo-spread]"), so
`--clear` can remove exactly (and only) those spots, leaving every
pre-existing spot -- real or from another seed script -- untouched. The
point generation is deterministic (fixed random seed), so re-running
`--count N` twice in a row is a no-op (same ids, same coordinates,
`ON CONFLICT (id) DO NOTHING`), and raising N later only adds new points
without moving the ones already placed.

Run from the repository root, for example:

    PARKING_DATABASE_URL=postgresql://... python scripts/seed_spread_parking_spots.py
    PARKING_DATABASE_URL=postgresql://... python scripts/seed_spread_parking_spots.py --count 600
    PARKING_DATABASE_URL=postgresql://... python scripts/seed_spread_parking_spots.py --clear

Requires psycopg2-binary, already used by `auth-service`/`seed_demo_data.py`.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import uuid

import psycopg2

DEMO_MARKER = "[parklink-demo-spread]"
SPOT_NAMESPACE = uuid.UUID("40000000-0000-0000-0000-000000000000")
RANDOM_SEED = 2026
MIN_DISTANCE_METERS = 180.0
JITTER_RADIUS_METERS = 1400.0
MAX_ATTEMPTS_PER_POINT = 300

# Approximate barrio centroids spread across the whole city (north, south,
# east and west), not just the usual handful of well-known ones -- the point
# is coverage, not precision, since these are jittered anyway below.
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
    ("Chacarita", -34.5875, -58.4530),
    ("Saavedra", -34.5556, -58.4867),
    ("Coghlan", -34.5661, -58.4701),
    ("Mataderos", -34.6600, -58.5083),
    ("Liniers", -34.6422, -58.5267),
    ("Versalles", -34.6256, -58.5192),
    ("Monte Castro", -34.6214, -58.5056),
    ("Villa Pueyrredón", -34.5847, -58.5027),
    ("Parque Avellaneda", -34.6386, -58.4751),
    ("Boedo", -34.6286, -58.4178),
    ("Parque Patricios", -34.6358, -58.4039),
    ("Constitución", -34.6263, -58.3816),
    ("Retiro", -34.5924, -58.3745),
    ("Nueva Pompeya", -34.6516, -58.4109),
    ("Villa Lugano", -34.6774, -58.4722),
    ("Villa Soldati", -34.6652, -58.4442),
    ("Villa Riachuelo", -34.6889, -58.4745),
    ("Floresta", -34.6276, -58.4848),
    ("Agronomía", -34.5942, -58.4879),
    ("Vélez Sarsfield", -34.6306, -58.4932),
    ("Paternal", -34.5983, -58.4659),
]


def database_url() -> str:
    return os.getenv(
        "PARKING_DATABASE_URL",
        "postgresql://parklink:parklink@localhost:5432/parking_service",
    )


def _meters_to_degrees_lat(meters: float) -> float:
    return meters / 111_320.0


def _meters_to_degrees_lng(meters: float, at_lat: float) -> float:
    return meters / (111_320.0 * math.cos(math.radians(at_lat)))


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def generate_points(count: int) -> list[tuple[str, float, float]]:
    """Rejection-samples `count` points jittered around the neighborhoods above,
    discarding any candidate closer than MIN_DISTANCE_METERS to one already
    placed -- the same fixed RANDOM_SEED makes this deterministic, so calling
    it again with a larger `count` reproduces every earlier point exactly and
    just appends new ones."""
    rng = random.Random(RANDOM_SEED)
    points: list[tuple[str, float, float]] = []
    attempts = 0
    max_attempts = count * MAX_ATTEMPTS_PER_POINT

    while len(points) < count and attempts < max_attempts:
        attempts += 1
        name, base_lat, base_lng = rng.choice(NEIGHBORHOODS)
        # Uniform sampling over a disk (not a square) around the neighborhood
        # center -- sqrt(random) avoids over-concentrating points near the center.
        radius = JITTER_RADIUS_METERS * math.sqrt(rng.random())
        theta = rng.uniform(0, 2 * math.pi)
        lat = base_lat + _meters_to_degrees_lat(radius * math.sin(theta))
        lng = base_lng + _meters_to_degrees_lng(radius * math.cos(theta), base_lat)

        if any(_haversine_meters(lat, lng, p[1], p[2]) < MIN_DISTANCE_METERS for p in points):
            continue
        points.append((name, lat, lng))

    if len(points) < count:
        raise RuntimeError(
            f"Solo se pudieron ubicar {len(points)}/{count} puntos respetando "
            f"MIN_DISTANCE_METERS={MIN_DISTANCE_METERS}. Bajá --count, o bajá "
            "MIN_DISTANCE_METERS, o subí JITTER_RADIUS_METERS."
        )
    return points


DEMO_OWNER_NAMESPACE = uuid.UUID("50000000-0000-0000-0000-000000000000")
DEMO_OWNER_COUNT = 20


def pick_owner_ids() -> list[uuid.UUID]:
    """Deterministic, dedicated fake owner ids -- never a real account. Reusing
    whoever already owns real spots (including the account someone is actively
    testing with) was the previous approach, and it backfired badly: round-robining
    400 demo spots across a handful of real owners landed ~80 of them on a single
    real owner, and every owner-dashboard screen fans out one request per owned
    spot (bookings/detailed, ratings, etc.) -- 80 spots meant 80+ simultaneous
    requests just from opening the app, enough to trip the gateway's rate limit on
    its own. These ids don't need a matching row in auth-service's users table
    (parking_spots.owner_id has no real FK to it) -- the only cost is cosmetic:
    an admin screen resolving "owner name" for one of these won't find a user."""
    return [uuid.uuid5(DEMO_OWNER_NAMESPACE, f"owner-{i}") for i in range(DEMO_OWNER_COUNT)]


AVERAGE_PRICE_PER_HOUR = 8000
PRICE_SPREAD = 3500  # prices range roughly AVERAGE ± PRICE_SPREAD, in both directions


def seed(connection, count: int) -> int:
    owner_ids = pick_owner_ids()
    points = generate_points(count)
    # Separate seeded generator (not the one generate_points already consumed)
    # so re-running with a different --count still reproduces the same prices
    # for the points that were already placed.
    price_rng = random.Random(RANDOM_SEED + 1)

    with connection.cursor() as cursor:
        for index, (neighborhood, lat, lng) in enumerate(points):
            spot_id = uuid.uuid5(SPOT_NAMESPACE, f"spread-{index}")
            owner_id = owner_ids[index % len(owner_ids)]
            title = f"Cochera {neighborhood} #{index + 1}"
            address = f"{neighborhood}, Ciudad Autónoma de Buenos Aires, Argentina"
            price = round(price_rng.uniform(
                AVERAGE_PRICE_PER_HOUR - PRICE_SPREAD, AVERAGE_PRICE_PER_HOUR + PRICE_SPREAD
            ) / 50) * 50
            covered = index % 3 != 0

            cursor.execute(
                """
                INSERT INTO parking_spots (
                    id, owner_id, title, description, address, location,
                    hourly_enabled, price_per_hour, stay_enabled, covered,
                    vehicle_types, capacity, photos, rules, status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    true, %s, false, %s,
                    %s::jsonb, 1, '[]'::jsonb, '[]'::jsonb, 'active'
                )
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    str(spot_id),
                    str(owner_id),
                    title,
                    f"Publicación demo repartida por CABA. {DEMO_MARKER}",
                    address,
                    lng,
                    lat,
                    price,
                    covered,
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
    return len(points)


def clear(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM parking_spots WHERE description LIKE %s",
            (f"%{DEMO_MARKER}%",),
        )
        spot_ids = [str(row[0]) for row in cursor.fetchall()]
        if not spot_ids:
            return 0

        cursor.execute(
            "DELETE FROM parking_spot_schedules WHERE parking_spot_id = ANY(%s::uuid[])",
            (spot_ids,),
        )
        cursor.execute(
            "DELETE FROM parking_spots WHERE id = ANY(%s::uuid[])",
            (spot_ids,),
        )
    connection.commit()
    return len(spot_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.getenv("SPREAD_SPOT_COUNT", "400")),
        help="Cuántas cocheras demo crear (default: 400, o $SPREAD_SPOT_COUNT).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="En vez de crear, borra todas las cocheras demo de este script y nada más.",
    )
    args = parser.parse_args()

    with psycopg2.connect(database_url()) as connection:
        if args.clear:
            removed = clear(connection)
            print(f"Borradas {removed} cocheras demo repartidas por CABA.")
        else:
            created = seed(connection, args.count)
            print(f"Seed completado: {created} cocheras demo repartidas por CABA.")


if __name__ == "__main__":
    main()
