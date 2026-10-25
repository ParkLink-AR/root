#!/usr/bin/env python3
"""Example data for the admin panel's sections that are empty today -- support tickets, reports,
new spots waiting for review, hidden reviews and sent broadcasts -- so they can be shown (and
screenshotted) with something in them. Everything hangs off the demo accounts and their bookings.

Every row this adds has an id starting with SEED_PREFIX, so `clean` removes exactly those and
nothing else. Writes straight to the local databases (docker compose), so nothing is sent: no
push, no email, no notification for the broadcasts.

usage: python3 scripts/admin_demo_data.py seed | clean | status
"""

import base64
import io
import json
import subprocess
import sys

SEED_PREFIX = "de300000-0000-4000-8000-"


def seed_id(n: int) -> str:
    return f"{SEED_PREFIX}{n:012d}"


DATABASES = {
    "booking": "root-db-booking-1",
    "parking": "root-db-parking-1",
    "notifications": "root-db-notifications-1",
}

# Demo accounts (auth-service) and demo spots / bookings between them.
LUCAS = "03e8554e-3445-47a6-81eb-4fb312f95fad"
MARTIN = "5303bf38-c9a7-4c7f-bf9f-f717ea54a5c3"
NICOLAS = "0c63e309-3519-472e-a69c-b98f9de80caa"
SOFIA = "31230114-eea0-44ac-b0ee-fad6eb2309f9"
VALENTINA = "03650746-31f9-4272-9f04-d47ce7e5ef55"
CAMILA = "b1d51c28-9b57-418e-a32b-39eec0ea454d"
DIEGO = "7511d478-be1e-4272-aed3-d4cbd936172a"
JULIETA = "a1626b39-20f0-43e1-ac73-80c44969d76a"
ADMIN = "a4cbc6ce-cccb-4fe7-983d-e7671cde5527"  # superadmin

PALERMO = "ded26325-dbf3-47d7-b9a2-b1c41c027c24"  # Camila
RECOLETA = "de31851b-216b-4797-bcb8-04a23ecfc46e"  # Diego
MICROCENTRO = "fa9398b9-6356-4051-8029-e00b393df396"  # Julieta

BOOKING_LUCAS_PALERMO = "952c099a-3bb8-486b-a0c1-c74352bdcb22"
BOOKING_LUCAS_PALERMO_2 = "ce229e28-cf0e-4304-b4e1-e4c9224891aa"
BOOKING_MARTIN_PALERMO = "7b3c9c0c-60e7-4727-9eb8-fd0835aec650"
BOOKING_SOFIA_MICROCENTRO = "efcea90b-eabb-4e25-a134-3987ad71d4b2"
BOOKING_MARTIN_MICROCENTRO = "8d7cbe71-5c79-43d7-9e0c-c99752cd6106"
BOOKING_NICOLAS_RECOLETA = "a0fbc4b9-5918-4fc0-9911-4c911daf2dad"
BOOKING_VALENTINA_RECOLETA = "a7e303c6-6495-4f83-94cc-913e44d55f72"
BOOKING_SOFIA_RECOLETA = "5cd4a74e-e74e-4f8e-8057-32798a25c2f0"
REVIEW_LUCAS_PALERMO = "55664dbb-4232-402f-9e0a-066374f94d47"


def psql(db: str, sql: str) -> str:
    container = DATABASES[db]
    result = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c",
         'psql -v ON_ERROR_STOP=1 -q -At -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
        input=sql, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"[{db}] {result.stderr.strip()}")
    return result.stdout.strip()


def q(value) -> str:
    """A SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def ago(spec: str) -> str:
    return f"now() - interval {q(spec)}"


# --- Support tickets ------------------------------------------------------------------------
# (id, booking, created_by, subject, status, opened, [(sender, is_admin, body, at)])
TICKETS = [
    (1, BOOKING_SOFIA_MICROCENTRO, SOFIA, "No me dejaron entrar a la cochera", "OPEN", "40 minutes", [
        (SOFIA, False, "Llegué a horario y el encargado del edificio no me dejó pasar, dice que no sabía nada de la reserva. Ya pagué. ¿Qué hago?", "40 minutes"),
    ]),
    (2, BOOKING_MARTIN_PALERMO, CAMILA, "El conductor dejó el auto más tiempo", "IN_PROGRESS", "1 day 3 hours", [
        (CAMILA, False, "La reserva terminaba a las 20 y el auto siguió en la cochera hasta las 23. Tenía otra persona esperando el lugar.", "1 day 3 hours"),
        (ADMIN, True, "Hola Camila, gracias por avisar. Ya le escribimos al conductor y estamos revisando el registro de salida para cobrarle el excedente.", "1 day 1 hour"),
        (CAMILA, False, "Perfecto. ¿El excedente me lo pagan a mí en la próxima liquidación?", "20 hours"),
    ]),
    (3, BOOKING_NICOLAS_RECOLETA, NICOLAS, "Me aparecen dos cobros de la misma reserva", "OPEN", "5 hours", [
        (NICOLAS, False, "En el resumen de la tarjeta veo dos cargos por la misma reserva en Recoleta. Adjunto el número de pago de Mercado Pago.", "5 hours"),
        (ADMIN, True, "Hola Nicolás. Revisamos y el segundo cargo es una reserva de prueba que Mercado Pago ya devolvió: puede tardar hasta 10 días hábiles en verse en tu resumen.", "3 hours"),
    ]),
    (4, BOOKING_VALENTINA_RECOLETA, VALENTINA, "¿Puedo cambiar la patente de la reserva?", "RESOLVED", "3 days", [
        (VALENTINA, False, "Reservé con el auto de mi papá pero voy a ir con el mío. ¿Se puede cambiar la patente?", "3 days"),
        (ADMIN, True, "Sí, ya la actualizamos. El propietario ve la patente nueva en la reserva.", "2 days 22 hours"),
        (VALENTINA, False, "¡Genial, gracias!", "2 days 21 hours"),
    ]),
    (5, BOOKING_SOFIA_RECOLETA, DIEGO, "¿Cuándo cobro esta reserva?", "OPEN", "2 hours", [
        (DIEGO, False, "La reserva de Sofía ya terminó y el código de llegada se verificó. ¿Cuándo entra en la liquidación?", "2 hours"),
    ]),
    (6, BOOKING_LUCAS_PALERMO, LUCAS, "Olvidé un paraguas en la cochera", "CLOSED", "6 days", [
        (LUCAS, False, "Me olvidé un paraguas negro en la cochera de Palermo. ¿Le pueden avisar a la dueña?", "6 days"),
        (ADMIN, True, "Le avisamos a Camila y lo tiene guardado. Coordiná con ella desde el chat de la reserva.", "5 days 23 hours"),
    ]),
]

# --- Reports --------------------------------------------------------------------------------
# (id, reporter, target_type, target_id, reason, details, status, admin_note, when)
REPORTS = [
    (101, LUCAS, "spot", MICROCENTRO, "Me pidieron pagar por fuera de ParkLink",
     "Al llegar me dijeron que si pagaba en efectivo me hacían precio y que la próxima reservara por WhatsApp.", "PENDING", None, "3 hours"),
    (102, JULIETA, "user", MARTIN, "Comportamiento inapropiado",
     "Me insultó por el chat cuando le pedí que respetara el horario de salida.", "PENDING", None, "1 day"),
    (103, CAMILA, "review", REVIEW_LUCAS_PALERMO, "Es falsa o no corresponde a una reserva real",
     "Dice que fue de noche pero la reserva era a la mañana.", "PENDING", None, "6 hours"),
    (104, DIEGO, "booking", BOOKING_VALENTINA_RECOLETA, "El conductor se pasó del horario",
     "Salió casi dos horas después del fin de la reserva.", "PENDING", None, "50 minutes"),
    (105, SOFIA, "booking", BOOKING_SOFIA_MICROCENTRO, "La cochera estaba ocupada",
     "Había otro auto estacionado en el lugar cuando llegué.", "PENDING", None, "35 minutes"),
    (106, NICOLAS, "spot", PALERMO, "Fotos o datos engañosos",
     "Las fotos muestran una cochera techada y es descubierta.", "RESOLVED",
     "Se le pidió a la propietaria que actualice las fotos; ya las cambió.", "4 days"),
]

# --- Reviews staff hid ----------------------------------------------------------------------
# (id, booking, reviewer, target_type, target_id, rating, comment, hidden_reason, when)
HIDDEN_REVIEWS = [
    (201, BOOKING_LUCAS_PALERMO_2, CAMILA, "driver", LUCAS, 1,
     "Un desastre este tipo, no lo acepten nunca más.", "Lenguaje ofensivo hacia el conductor.", "2 days"),
    (202, BOOKING_MARTIN_MICROCENTRO, JULIETA, "driver", MARTIN, 1,
     "Escríbanme al 11 5555-0000 que les alquilo más barato sin la app.", "Ofrece pagar por fuera de ParkLink y muestra un teléfono.", "4 days"),
]

# --- Broadcasts already sent ----------------------------------------------------------------
# (id, title, body, audience, recipients, when)
BROADCASTS = [
    (301, "Mantenimiento programado",
     "El domingo de 3 a 5 h la app puede no responder mientras actualizamos los servidores. Las reservas siguen en pie.",
     "all", 64, "2 days"),
    (302, "Nueva opción: media estadía",
     "Ahora podés ofrecer tu cochera por 12 horas a un precio cerrado. Activala desde la edición de tu cochera.",
     "owners", 41, "5 days"),
    (303, "Recordá cargar el código de llegada",
     "Pedile al conductor el código al llegar y cargalo en la app: así cobrás la reserva sin demoras.",
     "owners", 41, "9 days"),
    (304, "¡Bienvenidos a ParkLink!",
     "Ya podés buscar cocheras por hora, por 12 horas o por varios días en toda la ciudad.",
     "drivers", 23, "20 days"),
]


# --- New spots waiting for review -----------------------------------------------------------
def document_image(title: str, lines: list[tuple[str, str]]) -> str:
    """A plain example document (a utility bill, a rental contract), as a data: URI."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int, bold: bool = False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)

    width, height = 820, 1060
    image = Image.new("RGB", (width, height), "#FBFBF8")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, 120], fill="#E9EEF3")
    draw.text((50, 40), title, font=font(36, True), fill="#1F2D3D")
    y = 180
    for label, value in lines:
        draw.text((50, y), label, font=font(22), fill="#6B7A8C")
        draw.text((width - 50, y), value, font=font(22, True), fill="#1F2D3D", anchor="ra")
        y += 34
        draw.line([50, y, width - 50, y], fill="#DDE3E9", width=2)
        y += 30
    for row in range(6):
        draw.rectangle([50, y + row * 34, width - 50 - (row % 3) * 90, y + row * 34 + 14], fill="#E4E8EC")
    draw.text((width / 2, height - 60), "DOCUMENTO DE EJEMPLO", font=font(26, True), fill="#C8CED6", anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def photos_of(spot_id: str) -> list[str]:
    raw = psql("parking", f"select coalesce(photos, '[]'::jsonb) from parking_spots where id = {q(spot_id)}")
    return json.loads(raw or "[]")


def new_spots() -> list[dict]:
    recoleta, microcentro = photos_of(RECOLETA), photos_of(MICROCENTRO)
    return [
        {
            "id": seed_id(401), "owner": CAMILA, "title": "Cochera Belgrano R",
            "description": "Cochera en PH con portón automático. Entra auto mediano o camioneta chica.",
            "address": "Virrey del Pino 3150, Belgrano, CABA", "lat": -34.5672, "lng": -58.4636,
            "price_per_hour": 2800, "covered": True, "vehicle_types": ["car", "suv"], "capacity": 1,
            "photos": recoleta[:3], "when": "2 hours",
            "docs": [
                document_image("Factura de servicio eléctrico", [
                    ("Titular", "Camila Fernández"), ("Domicilio", "Virrey del Pino 3150"),
                    ("Período", "09/2026"), ("N° de cliente", "0012-448123"),
                ]),
            ],
        },
        {
            "id": seed_id(402), "owner": DIEGO, "title": "Garage Villa Crespo",
            "description": "Garage cubierto en edificio con seguridad 24 h. Dos lugares, ideal para estadías.",
            "address": "Av. Corrientes 5400, Villa Crespo, CABA", "lat": -34.5985, "lng": -58.4372,
            "price_per_hour": 2500, "covered": True, "vehicle_types": ["car", "suv", "pickup"], "capacity": 2,
            "photos": recoleta[3:6], "when": "1 day",
            "docs": [
                document_image("Contrato de alquiler de cochera", [
                    ("Locatario", "Diego Torres"), ("Inmueble", "Av. Corrientes 5400, UF 12"),
                    ("Vigencia", "03/2026 – 03/2028"), ("Uso", "Cochera"),
                ]),
                document_image("Expensas", [
                    ("Unidad", "Cochera UF 12"), ("Responsable", "Diego Torres"),
                    ("Período", "10/2026"), ("Estado", "Pagado"),
                ]),
            ],
        },
        {
            "id": seed_id(403), "owner": JULIETA, "title": "Cochera Caballito para motos",
            "description": "Espacio cubierto para motos y bicicletas, a media cuadra del subte A.",
            "address": "Av. Rivadavia 5100, Caballito, CABA", "lat": -34.6189, "lng": -58.4369,
            "price_per_hour": 900, "covered": True, "vehicle_types": ["motorcycle", "bicycle"], "capacity": 3,
            "photos": microcentro, "when": "30 minutes",
            "docs": [],  # no documentation: the review screen warns about it
        },
    ]


def seed() -> None:
    clean(quiet=True)

    statements = []
    for n, booking, creator, subject, ticket_status, opened, messages in TICKETS:
        tid = seed_id(n)
        last = messages[-1][3]
        statements.append(
            "insert into support_tickets (id, booking_id, created_by, subject, status, created_at, updated_at) values "
            f"({q(tid)}, {q(booking)}, {q(creator)}, {q(subject)}, {q(ticket_status)}, {ago(opened)}, {ago(last)});"
        )
        for i, (sender, is_admin, body, at) in enumerate(messages):
            statements.append(
                "insert into support_ticket_messages (id, ticket_id, sender_id, is_admin, body, created_at) values "
                f"({q(seed_id(n * 1000 + i))}, {q(tid)}, {q(sender)}, {q(is_admin)}, {q(body)}, {ago(at)});"
            )
    for n, reporter, target_type, target, reason, details, report_status, note, when in REPORTS:
        resolved = report_status != "PENDING"
        statements.append(
            "insert into reports (id, reporter_id, target_type, target_id, reason, details, status, admin_note, resolved_by, resolved_at, created_at) values "
            f"({q(seed_id(n))}, {q(reporter)}, {q(target_type)}, {q(target)}, {q(reason)}, {q(details)}, {q(report_status)}, "
            f"{q(note)}, {q('superadmin' if resolved else None)}, {ago('1 day') if resolved else 'NULL'}, {ago(when)});"
        )
    for n, booking, reviewer, target_type, target, rating, comment, reason, when in HIDDEN_REVIEWS:
        statements.append(
            "insert into reviews (id, booking_id, reviewer_id, target_type, target_id, rating, comment, created_at, hidden_at, hidden_reason, hidden_by) values "
            f"({q(seed_id(n))}, {q(booking)}, {q(reviewer)}, {q(target_type)}, {q(target)}, {rating}, {q(comment)}, "
            f"{ago(when)}, {ago(when)} + interval '3 hours', {q(reason)}, 'superadmin') "
            "on conflict (booking_id, reviewer_id, target_type) do nothing;"
        )
    psql("booking", "begin;\n" + "\n".join(statements) + "\ncommit;")

    spot_sql = []
    for spot in new_spots():
        spot_sql.append(
            "insert into parking_spots (id, owner_id, title, description, address, location, hourly_enabled, price_per_hour, "
            "covered, vehicle_types, capacity, photos, verification_photos, status, created_at, updated_at) values "
            f"({q(spot['id'])}, {q(spot['owner'])}, {q(spot['title'])}, {q(spot['description'])}, {q(spot['address'])}, "
            f"ST_SetSRID(ST_MakePoint({spot['lng']}, {spot['lat']}), 4326)::geography, true, {spot['price_per_hour']}, "
            f"{q(spot['covered'])}, {q(json.dumps(spot['vehicle_types']))}::jsonb, {spot['capacity']}, "
            f"{q(json.dumps(spot['photos']))}::jsonb, {q(json.dumps(spot['docs']))}::jsonb, 'pending_review', "
            f"(now() - interval {q(spot['when'])})::timestamp, (now() - interval {q(spot['when'])})::timestamp);"
        )
        # Monday to Friday 8 to 20, Saturday 9 to 14.
        hours = [(day, 8, 20) for day in range(5)] + [(5, 9, 14)]
        for day, start, end in hours:
            spot_sql.append(
                "insert into parking_spot_schedules (parking_spot_id, day_of_week, start_hour, end_hour) values "
                f"({q(spot['id'])}, {day}, {start}, {end});"
            )
    psql("parking", "begin;\n" + "\n".join(spot_sql) + "\ncommit;")

    psql("notifications", "begin;\n" + "\n".join(
        "insert into broadcasts (id, title, body, audience, recipients, created_by, created_at) values "
        f"({q(seed_id(n))}, {q(title)}, {q(body)}, {q(audience)}, {recipients}, 'superadmin', {ago(when)});"
        for n, title, body, audience, recipients, when in BROADCASTS
    ) + "\ncommit;")

    status()


def clean(quiet: bool = False) -> None:
    like = q(SEED_PREFIX + "%")
    psql("booking", f"""
        begin;
        delete from support_ticket_messages where ticket_id::text like {like};
        delete from support_tickets where id::text like {like};
        delete from reports where id::text like {like};
        delete from reviews where id::text like {like};
        commit;""")
    # The schedules go with the spot (on delete cascade).
    psql("parking", f"delete from parking_spots where id::text like {like};")
    psql("notifications", f"delete from broadcasts where id like {like};")
    if not quiet:
        status()


def status() -> None:
    like = q(SEED_PREFIX + "%")
    counts = {
        "tickets de soporte": psql("booking", f"select count(*) from support_tickets where id::text like {like}"),
        "denuncias": psql("booking", f"select count(*) from reports where id::text like {like}"),
        "reseñas ocultas": psql("booking", f"select count(*) from reviews where id::text like {like}"),
        "cocheras por revisar": psql("parking", f"select count(*) from parking_spots where id::text like {like}"),
        "avisos enviados": psql("notifications", f"select count(*) from broadcasts where id like {like}"),
    }
    print("Datos de ejemplo cargados:")
    for label, count in counts.items():
        print(f"  {label}: {count}")


if __name__ == "__main__":
    commands = {"seed": seed, "clean": clean, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
