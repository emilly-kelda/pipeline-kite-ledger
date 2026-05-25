"""
data_generator.py
─────────────────
Generates realistic fake data and inserts it into the database.

Uses the faker library to create Brazilian names, phones, and emails.
Simulates 6 months of school operations:
- 8 instructors
- 60 students
- ~300 classes
- Waivers and billing for each

Intentional problems planted for validator.py to catch:
- Some students have expired waivers
- Some classes have no billing entry
- Some billing amounts don't match class duration
"""

import random
from datetime import date, timedelta
from faker import Faker
from database import get_connection

fake = Faker("pt_BR")
random.seed(42)
Faker.seed(42)

# Seasonal wind profile for Cumbuco-based school
MONTHLY_PROFILE = {
    1:  {"avg_wind": 20, "classes_per_day": (2, 5), "cancel_prob": 0.10},  # Jan — end of peak
    2:  {"avg_wind": 16, "classes_per_day": (0, 2), "cancel_prob": 0.35},  # Feb — rainy
    3:  {"avg_wind": 15, "classes_per_day": (0, 2), "cancel_prob": 0.40},  # Mar — rainy
    4:  {"avg_wind": 14, "classes_per_day": (0, 1), "cancel_prob": 0.50},  # Apr — low
    5:  {"avg_wind": 15, "classes_per_day": (0, 1), "cancel_prob": 0.45},  # May — low
    6:  {"avg_wind": 17, "classes_per_day": (1, 3), "cancel_prob": 0.20},  # Jun — picking up
    7:  {"avg_wind": 20, "classes_per_day": (3, 6), "cancel_prob": 0.05},  # Jul — peak starts
    8:  {"avg_wind": 22, "classes_per_day": (4, 7), "cancel_prob": 0.05},  # Aug — peak
    9:  {"avg_wind": 24, "classes_per_day": (4, 8), "cancel_prob": 0.05},  # Sep — strongest
    10: {"avg_wind": 25, "classes_per_day": (4, 8), "cancel_prob": 0.05},  # Oct — strongest
    11: {"avg_wind": 23, "classes_per_day": (4, 7), "cancel_prob": 0.08},  # Nov — peak
    12: {"avg_wind": 21, "classes_per_day": (3, 6), "cancel_prob": 0.08},  # Dec — peak
}

def generate_instructors(cursor):
    """Insert 8 instructors with realistic Brazilian profiles."""
    instructors = [
        ("Carlos Mendes",    "+55 85 99201-3344", 0.35),
        ("Fernanda Lima",    "+55 85 98877-2211", 0.30),
        ("Rafael Souza",     "+55 85 99543-1122", 0.30),
        ("Juliana Costa",    "+55 85 97766-8899", 0.35),
        ("Thiago Alves",     "+55 85 99123-4567", 0.25),
        ("Mariana Rocha",    "+55 85 98234-5678", 0.30),
        ("Pedro Henrique",   "+55 85 99345-6789", 0.25),
        ("Aline Ferreira",   "+55 85 97456-7890", 0.35),
    ]
    cursor.executemany(
        "INSERT INTO instructors (name, phone, commission_rate) VALUES (?, ?, ?)",
        instructors
    )
    print(f"[✓] {len(instructors)} instructors inserted")


def generate_students(cursor, n=60):
    """Insert n students with realistic Brazilian profiles."""
    skill_levels = ["beginner", "intermediate", "advanced"]
    rows = []
    for _ in range(n):
        rows.append((
            fake.name(),
            fake.email(),
            fake.phone_number(),
            round(random.uniform(55, 100), 1),
            random.choice(skill_levels),
        ))
    cursor.executemany(
        "INSERT INTO students (name, email, phone, weight_kg, skill_level) VALUES (?, ?, ?, ?, ?)",
        rows
    )
    print(f"[✓] {n} students inserted")


def generate_waivers(cursor, student_ids):
    """Insert one waiver per student.

    Most waivers are valid for 1 year.
    Intentional problem: 10% of students have expired waivers.
    validator.py will catch these.
    """
    today = date.today()
    rows = []

    for student_id in student_ids:
        # 10% chance of expired waiver — planted problem
        if random.random() < 0.10:
            signed_at = today - timedelta(days=random.randint(370, 500))
        else:
            signed_at = today - timedelta(days=random.randint(1, 30))

        expires_at = signed_at + timedelta(days=365)
        drive_url = f"https://drive.google.com/fake/{student_id}"

        rows.append((student_id, str(signed_at), str(expires_at), drive_url))

    cursor.executemany(
        "INSERT INTO waivers (student_id, signed_at, expires_at, drive_url) VALUES (?, ?, ?, ?)",
        rows
    )
    print(f"[✓] {len(rows)} waivers inserted")


def generate_classes(cursor, student_ids, instructor_ids):
    """Insert classes with realistic seasonal distribution.

    Peak season July-January: 4-8 classes per day, strong wind.
    Low season Feb-May: 0-2 classes per day, higher cancellation.
    Some days fully cancelled due to rain or no wind.
    """
    today      = date.today()
    start_date = today - timedelta(days=365)  # full year of data
    all_dates  = [start_date + timedelta(days=i)
                  for i in range((today - start_date).days)]

    rows = []

    for session_date in all_dates:
        month   = session_date.month
        profile = MONTHLY_PROFILE[month]

        # Some days fully cancelled
        if random.random() < profile["cancel_prob"]:
            continue

        n_min, n_max = profile["classes_per_day"]
        n_classes    = random.randint(n_min, n_max)
        avg_wind     = profile["avg_wind"]

        for _ in range(n_classes):
            # Wind varies ±4 knots around monthly average
            wind = round(max(8.0, avg_wind + random.uniform(-4, 4)), 1)

            rows.append((
                random.choice(student_ids),
                random.choice(instructor_ids),
                str(session_date),
                random.choice([60, 90, 120, 150]),
                wind,
                "completed",
            ))

    cursor.executemany(
        """INSERT INTO classes
           (student_id, instructor_id, date, duration_min, wind_speed_kn, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows
    )
    print(f"[✓] {len(rows)} classes inserted")
    return len(rows)


def generate_billing(cursor, class_ids):
    """Insert billing entries for most classes.

    Intentional problem: 8% of classes have no billing entry.
    These are the ones validator.py will flag.

    Price is based on duration:
    60 min  → R$ 150
    90 min  → R$ 200
    120 min → R$ 250
    150 min → R$ 300
    """
    PRICE_MAP = {60: 150, 90: 200, 120: 250, 150: 300}

    rows = []
    skipped = 0

    for class_id, duration_min, commission_rate in class_ids:
        # 8% chance of missing billing — planted problem
        if random.random() < 0.08:
            skipped += 1
            continue

        amount = PRICE_MAP.get(duration_min, 150)
        commission = round(amount * commission_rate, 2)

        rows.append((
            class_id,
            amount,
            commission,
            "confirmed",
        ))

    cursor.executemany(
        """INSERT INTO billing (class_id, amount_brl, commission_brl, status)
           VALUES (?, ?, ?, ?)""",
        rows
    )
    print(f"[✓] {len(rows)} billing entries inserted")
    print(f"[!] {skipped} classes intentionally left without billing")


def run():
    """Run all generators in the correct order."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n── Generating data ──────────────────────────────────")

    # Order matters — students before waivers, instructors before classes
    generate_instructors(cursor)
    generate_students(cursor, n=60)

    # Get the IDs we just inserted to use as foreign keys
    student_ids = [r[0] for r in cursor.execute("SELECT id FROM students").fetchall()]
    instructor_ids = [r[0] for r in cursor.execute("SELECT id FROM instructors").fetchall()]

    generate_waivers(cursor, student_ids)

    n_classes = generate_classes(cursor, student_ids, instructor_ids)

    # Get class ids + duration + commission rate for billing
    class_data = cursor.execute("""
        SELECT c.id, c.duration_min, i.commission_rate
        FROM classes c
        JOIN instructors i ON c.instructor_id = i.id
    """).fetchall()

    generate_billing(cursor, class_data)

    conn.commit()
    conn.close()
    print("\n── Done ─────────────────────────────────────────────")
    print("Next step → run validator.py")


if __name__ == "__main__":
    run()