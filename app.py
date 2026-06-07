from __future__ import annotations

import hashlib
import random
import re
import sqlite3
import string
from datetime import datetime, timedelta
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ModuleNotFoundError as exc:
    if exc.name == "_tkinter":
        raise SystemExit(
            "Tkinter bulunamadi. Ubuntu/Debian uzerinde python3-tk paketi kurulu olmalidir."
        ) from exc
    raise

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "airline.db"

C = {
    "bg": "#F0F4F8",
    "card": "#FFFFFF",
    "primary": "#1A3C5E",
    "accent": "#0EA5E9",
    "success": "#16A34A",
    "warning": "#D97706",
    "danger": "#DC2626",
    "muted": "#64748B",
    "text": "#111827",
    "sidebar_fg": "#CBD5E1",
}

ACTIVE_BOOKING_STATUSES = ("PendingPayment", "Confirmed", "Ticketed")
BOOKING_STATUSES = ("PendingPayment", "Confirmed", "Ticketed", "Cancelled", "Refunded", "Expired")
PAYMENT_TYPES = ("Card", "Credit Card", "Online", "Transfer", "Google Pay", "Cash")
SPECIAL_REQUEST_TYPES = (
    "Wheelchair Assistance",
    "Seat Change",
    "Cancellation Request",
    "Refund Request",
    "Other",
)

# Paid options selected during booking. These are not admin tickets; they are
# added to the ticket price immediately.
BOOKING_ADDON_SEED = (
    ("BAG10", "Extra Baggage 10 kg", 650.00),
    ("BAG20", "Extra Baggage 20 kg", 1150.00),
    ("MEAL", "Meal Preference", 180.00),
    ("PETCABIN", "Pet in Cabin", 900.00),
)


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_date(val: str) -> bool:
    try:
        datetime.strptime(val.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time(val: str) -> bool:
    try:
        datetime.strptime(val.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def normalize_seat(seat_no: str) -> str:
    return seat_no.strip().upper().replace(" ", "")


def is_valid_seat(seat_no: str) -> bool:
    return bool(re.fullmatch(r"[1-9][0-9]{0,2}[A-F]", normalize_seat(seat_no)))


class Repository:
    """SQLite repository.

    Real-life booking rule used here:
    Passenger pays -> booking is ticketed immediately -> payment/ticket/transaction rows are created.
    Admin approval is used only for special requests such as cancellation/refund/assistance.
    """

    def __init__(self) -> None:
        self.ensure_database()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def fetchall(self, query: str, params: tuple = ()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def fetchone(self, query: str, params: tuple = ()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchone()

    def execute(self, query: str, params: tuple = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, params)
            conn.commit()

    def ensure_database(self) -> None:
        with self.connect() as conn:
            self._create_schema(conn)
            self._migrate_old_db(conn)
            self._seed_data(conn)
            conn.commit()

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS Countries (
                Country_code TEXT PRIMARY KEY,
                Country_Name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS Airport (
                Air_Code TEXT PRIMARY KEY,
                Air_Name TEXT NOT NULL,
                City TEXT NOT NULL,
                State TEXT,
                Country_code TEXT NOT NULL,
                FOREIGN KEY (Country_code) REFERENCES Countries(Country_code) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS Airplane_type (
                A_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Capacity INTEGER NOT NULL CHECK (Capacity > 0),
                A_weight REAL,
                Company TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Route (
                Route_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Destination TEXT NOT NULL,
                Take_Off_point TEXT NOT NULL,
                R_type TEXT NOT NULL,
                FOREIGN KEY (Destination) REFERENCES Airport(Air_Code) ON DELETE RESTRICT,
                FOREIGN KEY (Take_Off_point) REFERENCES Airport(Air_Code) ON DELETE RESTRICT,
                CHECK (Destination <> Take_Off_point)
            );

            CREATE TABLE IF NOT EXISTS AirFare (
                Fare_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Charge_Amount REAL NOT NULL CHECK (Charge_Amount >= 0),
                Description TEXT
            );

            CREATE TABLE IF NOT EXISTS Flight (
                Flight_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Flight_No TEXT UNIQUE,
                Departure TEXT NOT NULL,
                Arrival TEXT NOT NULL,
                Flight_date TEXT NOT NULL,
                Route_ID INTEGER NOT NULL,
                A_ID INTEGER NOT NULL,
                Fare_ID INTEGER NOT NULL,
                FOREIGN KEY (Route_ID) REFERENCES Route(Route_ID) ON DELETE RESTRICT,
                FOREIGN KEY (A_ID) REFERENCES Airplane_type(A_ID) ON DELETE RESTRICT,
                FOREIGN KEY (Fare_ID) REFERENCES AirFare(Fare_ID) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS Passengers (
                Ps_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Address TEXT,
                Age INTEGER CHECK (Age >= 0),
                Sex TEXT,
                Contacts TEXT
            );

            CREATE TABLE IF NOT EXISTS Employees (
                Emp_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT NOT NULL,
                Address TEXT,
                Age INTEGER CHECK (Age >= 18),
                Email_ID TEXT UNIQUE,
                Contacts TEXT,
                Air_Code TEXT,
                FOREIGN KEY (Air_Code) REFERENCES Airport(Air_Code) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS Auth_Accounts (
                Account_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Role TEXT NOT NULL CHECK (Role IN ('Passenger', 'Admin')),
                Ps_ID INTEGER,
                Emp_ID INTEGER,
                Password_Hash TEXT NOT NULL,
                Created_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE CASCADE,
                FOREIGN KEY (Emp_ID) REFERENCES Employees(Emp_ID) ON DELETE CASCADE,
                CHECK ((Role = 'Passenger' AND Ps_ID IS NOT NULL AND Emp_ID IS NULL) OR
                       (Role = 'Admin' AND Emp_ID IS NOT NULL AND Ps_ID IS NULL))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_ps ON Auth_Accounts(Ps_ID) WHERE Ps_ID IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_emp ON Auth_Accounts(Emp_ID) WHERE Emp_ID IS NOT NULL;

            CREATE TABLE IF NOT EXISTS Addon_Catalog (
                Addon_Code TEXT PRIMARY KEY,
                Addon_Name TEXT NOT NULL UNIQUE,
                Price REAL NOT NULL CHECK (Price >= 0),
                Is_Active INTEGER NOT NULL DEFAULT 1 CHECK (Is_Active IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS Bookings (
                Booking_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                PNR TEXT NOT NULL UNIQUE,
                Ps_ID INTEGER NOT NULL,
                Flight_ID INTEGER NOT NULL,
                Seat_No TEXT NOT NULL,
                Status TEXT NOT NULL CHECK (Status IN ('PendingPayment','Confirmed','Ticketed','Cancelled','Refunded','Expired')),
                Fare_ID INTEGER,
                Amount REAL NOT NULL CHECK (Amount >= 0),
                Created_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                Confirmed_At TEXT,
                Cancelled_At TEXT,
                Refunded_At TEXT,
                FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE CASCADE,
                FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE RESTRICT,
                FOREIGN KEY (Fare_ID) REFERENCES AirFare(Fare_ID) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS Booking_Addons (
                Booking_Addon_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Booking_ID INTEGER NOT NULL,
                Addon_Code TEXT NOT NULL,
                Price_At_Booking REAL NOT NULL CHECK (Price_At_Booking >= 0),
                FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE,
                FOREIGN KEY (Addon_Code) REFERENCES Addon_Catalog(Addon_Code) ON DELETE RESTRICT,
                UNIQUE (Booking_ID, Addon_Code)
            );

            CREATE TABLE IF NOT EXISTS Payments (
                Payment_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Booking_ID INTEGER NOT NULL,
                Payment_Type TEXT NOT NULL CHECK (Payment_Type IN ('Card','Cash','Transfer','Online','Google Pay','Credit Card')),
                Amount REAL NOT NULL CHECK (Amount >= 0),
                Status TEXT NOT NULL CHECK (Status IN ('Authorized','Captured','Failed','Refunded')),
                Paid_At TEXT,
                FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Tickets (
                Ticket_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Booking_ID INTEGER NOT NULL UNIQUE,
                Ticket_No TEXT NOT NULL UNIQUE,
                Issued_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Transactions (
                TS_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Booking_ID INTEGER,
                Booking_Date TEXT NOT NULL,
                Departure_Date TEXT NOT NULL,
                Type TEXT NOT NULL CHECK (Type IN ('Card','Cash','Transfer','Online','Google Pay','Paytm','PhonePe','Credit Card')),
                Emp_ID INTEGER NOT NULL,
                Ps_ID INTEGER NOT NULL,
                Flight_ID INTEGER NOT NULL,
                Charge_Amount REAL NOT NULL CHECK (Charge_Amount >= 0),
                FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE SET NULL,
                FOREIGN KEY (Emp_ID) REFERENCES Employees(Emp_ID) ON DELETE RESTRICT,
                FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE RESTRICT,
                FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS Special_Requests (
                Request_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Booking_ID INTEGER,
                Ps_ID INTEGER NOT NULL,
                Request_Type TEXT NOT NULL,
                Note TEXT,
                Status TEXT NOT NULL DEFAULT 'Pending' CHECK (Status IN ('Pending','Approved','Rejected','Cancelled')),
                Reviewed_By_Emp_ID INTEGER,
                Created_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                Decided_At TEXT,
                FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE,
                FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE CASCADE,
                FOREIGN KEY (Reviewed_By_Emp_ID) REFERENCES Employees(Emp_ID) ON DELETE SET NULL
            );

            CREATE TRIGGER IF NOT EXISTS trg_booking_seat_conflict
            BEFORE INSERT ON Bookings
            WHEN NEW.Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            AND EXISTS (
                SELECT 1 FROM Bookings
                WHERE Flight_ID = NEW.Flight_ID
                  AND Seat_No = NEW.Seat_No
                  AND Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            )
            BEGIN
                SELECT RAISE(ABORT, 'This seat is already occupied for this flight');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_booking_capacity_check
            BEFORE INSERT ON Bookings
            WHEN NEW.Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            AND (
                SELECT COUNT(*) FROM Bookings
                WHERE Flight_ID = NEW.Flight_ID
                  AND Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            ) >= (
                SELECT at.Capacity FROM Flight f
                JOIN Airplane_type at ON at.A_ID = f.A_ID
                WHERE f.Flight_ID = NEW.Flight_ID
            )
            BEGIN
                SELECT RAISE(ABORT, 'Flight capacity is full');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_booking_seat_conflict_update
            BEFORE UPDATE OF Seat_No, Status ON Bookings
            WHEN NEW.Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            AND EXISTS (
                SELECT 1 FROM Bookings
                WHERE Flight_ID = NEW.Flight_ID
                  AND Seat_No = NEW.Seat_No
                  AND Booking_ID <> NEW.Booking_ID
                  AND Status IN ('PendingPayment', 'Confirmed', 'Ticketed')
            )
            BEGIN
                SELECT RAISE(ABORT, 'This seat is already occupied for this flight');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_ts_departure_after_booking
            BEFORE INSERT ON Transactions
            WHEN date(NEW.Departure_Date) < date(NEW.Booking_Date)
            BEGIN
                SELECT RAISE(ABORT, 'Departure date cannot be earlier than booking date');
            END;

            DROP VIEW IF EXISTS v_booking_overview;
            CREATE VIEW v_booking_overview AS
            SELECT
                b.Booking_ID,
                b.PNR,
                p.Name AS Passenger_Name,
                f.Flight_No,
                f.Flight_ID,
                r.Take_Off_point,
                r.Destination,
                f.Flight_date,
                f.Departure,
                f.Arrival,
                b.Seat_No,
                b.Status AS Booking_Status,
                b.Amount,
                COALESCE(ax.Addon_Total, 0) AS Addon_Total,
                COALESCE(ax.Addons, '-') AS Addons,
                pay.Payment_Type,
                pay.Status AS Payment_Status,
                t.Ticket_No,
                b.Created_At,
                b.Confirmed_At
            FROM Bookings b
            JOIN Passengers p ON p.Ps_ID = b.Ps_ID
            JOIN Flight f ON f.Flight_ID = b.Flight_ID
            JOIN Route r ON r.Route_ID = f.Route_ID
            LEFT JOIN (
                SELECT
                    ba.Booking_ID,
                    SUM(ba.Price_At_Booking) AS Addon_Total,
                    GROUP_CONCAT(ac.Addon_Name || ' (+₺' || printf('%.2f', ba.Price_At_Booking) || ')', ', ') AS Addons
                FROM Booking_Addons ba
                JOIN Addon_Catalog ac ON ac.Addon_Code = ba.Addon_Code
                GROUP BY ba.Booking_ID
            ) ax ON ax.Booking_ID = b.Booking_ID
            LEFT JOIN Payments pay ON pay.Booking_ID = b.Booking_ID
            LEFT JOIN Tickets t ON t.Booking_ID = b.Booking_ID;
            """
        )

    def _migrate_old_db(self, conn: sqlite3.Connection) -> None:
        # Old versions may have Transactions without Booking_ID.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(Transactions)")}
        if cols and "Booking_ID" not in cols:
            conn.execute("ALTER TABLE Transactions ADD COLUMN Booking_ID INTEGER")

    def _seed_data(self, conn: sqlite3.Connection) -> None:
        default_hash = hash_password("1234")
        conn.executescript(
            """
            INSERT OR IGNORE INTO Countries (Country_code, Country_Name) VALUES
                ('TR', 'Turkiye'),
                ('DE', 'Germany'),
                ('GB', 'United Kingdom'),
                ('US', 'United States'),
                ('FR', 'France'),
                ('NL', 'Netherlands'),
                ('IT', 'Italy');

            INSERT OR IGNORE INTO Airport (Air_Code, Air_Name, City, State, Country_code) VALUES
                ('IST', 'Istanbul Airport', 'Istanbul', 'Marmara', 'TR'),
                ('SAW', 'Sabiha Gokcen International Airport', 'Istanbul', 'Marmara', 'TR'),
                ('ESB', 'Esenboga Airport', 'Ankara', 'Central Anatolia', 'TR'),
                ('ADB', 'Adnan Menderes Airport', 'Izmir', 'Aegean', 'TR'),
                ('AYT', 'Antalya Airport', 'Antalya', 'Mediterranean', 'TR'),
                ('TZX', 'Trabzon Airport', 'Trabzon', 'Black Sea', 'TR'),
                ('ADA', 'Adana Airport', 'Adana', 'Mediterranean', 'TR'),
                ('DLM', 'Dalaman Airport', 'Mugla', 'Aegean', 'TR'),
                ('LHR', 'Heathrow Airport', 'London', 'England', 'GB'),
                ('JFK', 'John F. Kennedy International Airport', 'New York', 'New York', 'US'),
                ('CDG', 'Charles de Gaulle Airport', 'Paris', 'Ile-de-France', 'FR'),
                ('AMS', 'Amsterdam Airport Schiphol', 'Amsterdam', 'North Holland', 'NL'),
                ('FCO', 'Rome Fiumicino Airport', 'Rome', 'Lazio', 'IT'),
                ('BER', 'Berlin Brandenburg Airport', 'Berlin', 'Brandenburg', 'DE');

            INSERT OR IGNORE INTO Airplane_type (A_ID, Capacity, A_weight, Company) VALUES
                (1, 180, 73500, 'Airbus A320'),
                (2, 160, 70500, 'Boeing 737'),
                (3, 260, 125000, 'Airbus A330'),
                (4, 300, 145000, 'Boeing 777'),
                (5, 220, 98000, 'Airbus A321neo'),
                (6, 280, 138000, 'Boeing 787');

            INSERT OR IGNORE INTO Route (Route_ID, Destination, Take_Off_point, R_type) VALUES
                (1, 'ESB', 'IST', 'Domestic'),
                (2, 'AYT', 'ADB', 'Domestic'),
                (3, 'TZX', 'IST', 'Domestic'),
                (4, 'ADA', 'IST', 'Domestic'),
                (5, 'DLM', 'SAW', 'Domestic'),
                (6, 'IST', 'AYT', 'Domestic'),
                (7, 'LHR', 'IST', 'International'),
                (8, 'JFK', 'IST', 'International'),
                (9, 'CDG', 'IST', 'International'),
                (10, 'AMS', 'SAW', 'International'),
                (11, 'FCO', 'IST', 'International'),
                (12, 'BER', 'IST', 'International'),
                (13, 'IST', 'JFK', 'International'),
                (14, 'IST', 'LHR', 'International');

            INSERT OR IGNORE INTO AirFare (Fare_ID, Charge_Amount, Description) VALUES
                (1, 1499.90, 'Economy Base Fare'),
                (2, 2399.50, 'Flexible Fare'),
                (3, 3499.00, 'Domestic Business'),
                (4, 12999.00, 'International Economy'),
                (5, 24999.00, 'International Business'),
                (6, 6999.00, 'Promo International'),
                (7, 4999.00, 'Premium Domestic');

            INSERT OR IGNORE INTO Addon_Catalog (Addon_Code, Addon_Name, Price, Is_Active) VALUES
                ('BAG10', 'Extra Baggage 10 kg', 650.00, 1),
                ('BAG20', 'Extra Baggage 20 kg', 1150.00, 1),
                ('MEAL', 'Meal Preference', 180.00, 1),
                ('PETCABIN', 'Pet in Cabin', 900.00, 1);

            INSERT OR IGNORE INTO Flight (Flight_ID, Flight_No, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID) VALUES
                (1, 'TK100', '09:00', '10:10', date('now', '+30 days'), 1, 1, 1),
                (2, 'TK204', '14:00', '15:20', date('now', '+31 days'), 2, 2, 2),
                (3, 'TK311', '18:20', '20:05', date('now', '+34 days'), 3, 1, 1),
                (4, 'TK420', '08:45', '10:20', date('now', '+37 days'), 4, 2, 2),
                (5, 'TK512', '11:30', '12:45', date('now', '+40 days'), 5, 5, 3),
                (6, 'TK626', '17:15', '18:35', date('now', '+41 days'), 6, 2, 1),
                (7, 'TK700', '07:40', '10:05', date('now', '+45 days'), 7, 3, 4),
                (8, 'TK901', '01:15', '12:45', date('now', '+50 days'), 8, 4, 5),
                (9, 'TK1821', '12:30', '15:10', date('now', '+52 days'), 9, 3, 6),
                (10, 'TK1953', '16:20', '19:00', date('now', '+54 days'), 10, 5, 6),
                (11, 'TK1865', '10:10', '12:45', date('now', '+56 days'), 11, 3, 4),
                (12, 'TK1721', '20:00', '22:10', date('now', '+58 days'), 12, 5, 6),
                (13, 'TK003', '13:30', '17:55', date('now', '+60 days'), 13, 6, 5),
                (14, 'TK1980', '21:15', '03:05', date('now', '+62 days'), 14, 3, 4),
                (15, 'TK145', '06:20', '07:30', date('now', '+65 days'), 1, 1, 1),
                (16, 'TK209', '19:25', '20:45', date('now', '+66 days'), 2, 2, 2),
                (17, 'TK315', '22:00', '23:40', date('now', '+68 days'), 3, 1, 3),
                (18, 'TK428', '12:15', '13:45', date('now', '+70 days'), 4, 2, 7);

            INSERT OR IGNORE INTO Passengers (Ps_ID, Name, Address, Age, Sex, Contacts) VALUES
                (1, 'Buse Yilmaz', 'Istanbul', 22, 'F', '+90-555-010-1010'),
                (2, 'Mert Kaya', 'Izmir', 24, 'M', '+90-555-020-2020'),
                (3, 'Aylin Demir', 'Ankara', 27, 'F', '+90-555-030-3030'),
                (4, 'Emre Sahin', 'Bursa', 31, 'M', '+90-555-040-4040'),
                (5, 'Zeynep Arslan', 'Antalya', 29, 'F', '+90-555-050-5050'),
                (6, 'Can Yildiz', 'Trabzon', 34, 'M', '+90-555-060-6060'),
                (7, 'Ece Korkmaz', 'Adana', 26, 'F', '+90-555-070-7070'),
                (8, 'Deniz Acar', 'Mugla', 38, 'Other', '+90-555-080-8080'),
                (9, 'Selin Ozturk', 'Istanbul', 21, 'F', '+90-555-090-9090'),
                (10, 'Kerem Celik', 'Ankara', 45, 'M', '+90-555-100-1010'),
                (11, 'Melis Kaplan', 'Izmir', 33, 'F', '+90-555-110-1111'),
                (12, 'Burak Polat', 'Konya', 28, 'M', '+90-555-120-1212'),
                (13, 'Irem Koc', 'Eskisehir', 25, 'F', '+90-555-130-1313'),
                (14, 'Onur Gunes', 'Samsun', 41, 'M', '+90-555-140-1414'),
                (15, 'Derya Aydin', 'Kayseri', 36, 'F', '+90-555-150-1515'),
                (16, 'Tolga Ergin', 'Mersin', 39, 'M', '+90-555-160-1616'),
                (17, 'Nil Kara', 'Gaziantep', 23, 'F', '+90-555-170-1717'),
                (18, 'Ali Eren', 'Diyarbakir', 30, 'M', '+90-555-180-1818'),
                (19, 'Yagmur Sari', 'Balikesir', 32, 'F', '+90-555-190-1919'),
                (20, 'Ozan Demirci', 'Kocaeli', 44, 'M', '+90-555-200-2020'),
                (21, 'Ceren Aksoy', 'London', 28, 'F', '+44-7700-900001'),
                (22, 'Arda Basaran', 'New York', 35, 'M', '+1-212-555-0101'),
                (23, 'Mina Cakir', 'Paris', 27, 'F', '+33-1-5555-0102'),
                (24, 'Sarp Uslu', 'Amsterdam', 40, 'M', '+31-20-555-0103'),
                (25, 'Elif Tunc', 'Berlin', 30, 'F', '+49-30-555-0104'),
                (26, 'Kaan Ersoy', 'Rome', 37, 'M', '+39-06-555-0105');

            INSERT OR IGNORE INTO Employees (Emp_ID, Name, Address, Age, Email_ID, Contacts, Air_Code) VALUES
                (1, 'Online Sales System', 'Istanbul', 30, 'online.sales@demo.local', '+90-555-000-0001', 'IST');
            """
        )
        conn.execute(
            """
            INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash)
            SELECT 'Passenger', p.Ps_ID, ?
            FROM Passengers p
            WHERE NOT EXISTS (SELECT 1 FROM Auth_Accounts a WHERE a.Ps_ID = p.Ps_ID)
            """,
            (default_hash,),
        )
        # Remove any extra admins from older DB versions — keep only Online Sales System (Emp_ID=1)
        conn.execute("DELETE FROM Employees WHERE Emp_ID <> 1")
        conn.execute(
            """
            INSERT INTO Auth_Accounts (Role, Emp_ID, Password_Hash)
            SELECT 'Admin', e.Emp_ID, ?
            FROM Employees e
            WHERE NOT EXISTS (SELECT 1 FROM Auth_Accounts a WHERE a.Emp_ID = e.Emp_ID)
            """,
            (default_hash,),
        )

        # Seed realistic paid bookings only if no booking exists.
        existing = conn.execute("SELECT COUNT(*) AS n FROM Bookings").fetchone()["n"]
        if existing == 0:
            seed_bookings = [
                (1, 1, "12A", "Card", ["BAG10"]),
                (2, 2, "9C", "Online", ["MEAL"]),
                (3, 3, "5E", "Credit Card", ["BAG20", "MEAL"]),
                (4, 4, "14D", "Transfer", []),
                (5, 5, "3A", "Card", ["PETCABIN"]),
                (6, 6, "18F", "Cash", []),
                (7, 7, "21C", "Google Pay", ["BAG10"]),
                (8, 8, "5D", "Credit Card", ["BAG20"]),
                (9, 9, "10A", "Online", ["MEAL"]),
                (10, 10, "11B", "Card", []),
                (11, 11, "2C", "Transfer", ["BAG10", "MEAL"]),
                (12, 12, "16E", "Online", []),
                (13, 13, "8A", "Credit Card", ["PETCABIN"]),
                (14, 14, "22F", "Card", ["BAG20"]),
                (15, 15, "6A", "Card", []),
                (16, 16, "4C", "Online", ["MEAL"]),
                (17, 17, "13D", "Cash", ["BAG10"]),
                (18, 18, "15B", "Transfer", []),
            ]
            created: dict[int, int] = {}
            for ps_id, flight_id, seat, payment_type, addon_codes in seed_bookings:
                result = self._create_paid_booking_conn(
                    conn, ps_id, flight_id, seat, payment_type, addon_codes=addon_codes, seed=True
                )
                created[ps_id] = int(result["booking_id"])

            conn.execute(
                """
                INSERT INTO Special_Requests (Booking_ID, Ps_ID, Request_Type, Note, Status, Created_At)
                VALUES (?, 4, 'Wheelchair Assistance', 'Assistance needed at boarding gate.', 'Pending', datetime('now'))
                """,
                (created.get(4),),
            )
            conn.execute(
                """
                INSERT INTO Special_Requests (Booking_ID, Ps_ID, Request_Type, Note, Status, Created_At)
                VALUES (?, 8, 'Refund Request', 'Travel plan changed.', 'Pending', datetime('now'))
                """,
                (created.get(8),),
            )
            conn.execute(
                """
                INSERT INTO Special_Requests (Booking_ID, Ps_ID, Request_Type, Note, Status, Reviewed_By_Emp_ID, Created_At, Decided_At)
                VALUES (?, 3, 'Seat Change', 'Prefer window seat if available.', 'Rejected', 1, datetime('now', '-1 day'), datetime('now'))
                """,
                (created.get(3),),
            )

    # ── Auth ──────────────────────────────────────────────────────
    def passenger_options(self):
        return self.fetchall("SELECT Ps_ID, Name FROM Passengers ORDER BY Name")

    def admin_options(self):
        return self.fetchall("SELECT Emp_ID, Name FROM Employees ORDER BY Name")

    def validate_passenger_login(self, ps_id: int, raw: str) -> bool:
        row = self.fetchone(
            "SELECT Account_ID FROM Auth_Accounts WHERE Role='Passenger' AND Ps_ID=? AND Password_Hash=?",
            (ps_id, hash_password(raw)),
        )
        return row is not None

    def validate_admin_login(self, emp_id: int, raw: str) -> bool:
        row = self.fetchone(
            "SELECT Account_ID FROM Auth_Accounts WHERE Role='Admin' AND Emp_ID=? AND Password_Hash=?",
            (emp_id, hash_password(raw)),
        )
        return row is not None

    def create_passenger_account(self, name: str, address: str, age: int, sex: str, contacts: str, raw: str):
        if not name.strip():
            raise ValueError("Name is required.")
        if age < 0:
            raise ValueError("Age cannot be negative.")
        if not raw.strip():
            raise ValueError("Password is required.")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO Passengers (Name, Address, Age, Sex, Contacts) VALUES (?, ?, ?, ?, ?)",
                (name.strip(), address.strip(), age, sex.strip(), contacts.strip()),
            )
            ps_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash) VALUES ('Passenger', ?, ?)",
                (ps_id, hash_password(raw)),
            )
            conn.commit()

    # ── Reference lists ───────────────────────────────────────────
    def list_routes(self):
        return self.fetchall("SELECT Route_ID, Take_Off_point, Destination, R_type FROM Route ORDER BY Route_ID")

    def list_airplanes(self):
        return self.fetchall("SELECT A_ID, Company, Capacity, A_weight FROM Airplane_type ORDER BY A_ID")

    def list_airfares(self):
        return self.fetchall("SELECT Fare_ID, Charge_Amount, Description FROM AirFare ORDER BY Fare_ID")

    def list_addons(self):
        return self.fetchall(
            "SELECT Addon_Code, Addon_Name, Price FROM Addon_Catalog WHERE Is_Active=1 ORDER BY Price, Addon_Name"
        )

    def addon_total(self, addon_codes: list[str] | None) -> float:
        codes = list(dict.fromkeys(addon_codes or []))
        if not codes:
            return 0.0
        placeholders = ",".join("?" for _ in codes)
        rows = self.fetchall(
            f"SELECT Addon_Code, Price FROM Addon_Catalog WHERE Is_Active=1 AND Addon_Code IN ({placeholders})",
            tuple(codes),
        )
        if len(rows) != len(codes):
            raise ValueError("Invalid add-on selected.")
        return float(sum(float(row["Price"]) for row in rows))

    # ── Flights ───────────────────────────────────────────────────
    def list_flights(self, keyword: str = "", flight_date: str = ""):
        conds = ["1=1"]
        params: list = []
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            conds.append("(f.Flight_No LIKE ? OR r.Take_Off_point LIKE ? OR r.Destination LIKE ? OR at.Company LIKE ?)")
            params += [like, like, like, like]
        if flight_date.strip():
            conds.append("f.Flight_date = ?")
            params.append(flight_date.strip())
        active = "'PendingPayment','Confirmed','Ticketed'"
        query = f"""
            SELECT f.Flight_ID, COALESCE(f.Flight_No, 'FL-' || f.Flight_ID) AS Flight_No,
                   f.Departure, f.Arrival, f.Flight_date,
                   r.Route_ID, r.Take_Off_point, r.Destination, r.R_type,
                   at.A_ID, at.Company, at.Capacity,
                   af.Fare_ID, af.Charge_Amount,
                   COALESCE((
                       SELECT COUNT(*) FROM Bookings b
                       WHERE b.Flight_ID = f.Flight_ID AND b.Status IN ({active})
                   ), 0) AS Booked_Count,
                   at.Capacity - COALESCE((
                       SELECT COUNT(*) FROM Bookings b
                       WHERE b.Flight_ID = f.Flight_ID AND b.Status IN ({active})
                   ), 0) AS Available_Count
            FROM Flight f
            JOIN Route r ON r.Route_ID = f.Route_ID
            JOIN Airplane_type at ON at.A_ID = f.A_ID
            JOIN AirFare af ON af.Fare_ID = f.Fare_ID
            WHERE {' AND '.join(conds)}
            ORDER BY f.Flight_date, f.Departure, f.Flight_ID
        """
        return self.fetchall(query, tuple(params))

    def flight_capacity_and_price(self, flight_id: int):
        return self.fetchone(
            """
            SELECT f.Flight_ID, f.Flight_No, at.Capacity, af.Fare_ID, af.Charge_Amount, f.Flight_date
            FROM Flight f
            JOIN Airplane_type at ON at.A_ID = f.A_ID
            JOIN AirFare af ON af.Fare_ID = f.Fare_ID
            WHERE f.Flight_ID = ?
            """,
            (flight_id,),
        )

    def add_flight(self, flight_no: str, dep: str, arr: str, fdate: str, route_id: int, a_id: int, fare_id: int):
        if not flight_no.strip():
            raise ValueError("Flight number is required.")
        if not validate_time(dep) or not validate_time(arr):
            raise ValueError("Departure and arrival must be valid HH:MM values.")
        if not validate_date(fdate):
            raise ValueError("Flight date must be YYYY-MM-DD.")
        self.execute(
            """
            INSERT INTO Flight (Flight_No, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (flight_no.strip().upper(), dep.strip(), arr.strip(), fdate.strip(), route_id, a_id, fare_id),
        )

    def update_flight(self, flight_id: int, flight_no: str, dep: str, arr: str, fdate: str, route_id: int, a_id: int, fare_id: int):
        if not validate_time(dep) or not validate_time(arr):
            raise ValueError("Departure and arrival must be valid HH:MM values.")
        if not validate_date(fdate):
            raise ValueError("Flight date must be YYYY-MM-DD.")
        self.execute(
            """
            UPDATE Flight
            SET Flight_No=?, Departure=?, Arrival=?, Flight_date=?, Route_ID=?, A_ID=?, Fare_ID=?
            WHERE Flight_ID=?
            """,
            (flight_no.strip().upper(), dep.strip(), arr.strip(), fdate.strip(), route_id, a_id, fare_id, flight_id),
        )

    def delete_flight(self, flight_id: int):
        self.execute("DELETE FROM Flight WHERE Flight_ID=?", (flight_id,))

    # ── Real-life booking/payment/ticketing ───────────────────────
    def occupied_seats_for_flight(self, flight_id: int) -> list[str]:
        rows = self.fetchall(
            """
            SELECT Seat_No FROM Bookings
            WHERE Flight_ID=? AND Status IN ('PendingPayment','Confirmed','Ticketed')
            ORDER BY Seat_No
            """,
            (flight_id,),
        )
        return [row["Seat_No"] for row in rows]

    def _generate_unique_code(self, conn: sqlite3.Connection, table: str, column: str, length: int, prefix: str = "") -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(100):
            code = prefix + "".join(random.choice(alphabet) for _ in range(length))
            row = conn.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (code,)).fetchone()
            if row is None:
                return code
        raise RuntimeError(f"Could not generate unique {column}.")

    def _generate_ticket_no(self, conn: sqlite3.Connection) -> str:
        # Demo e-ticket number: 13 numeric digits.
        for _ in range(100):
            code = "".join(random.choice(string.digits) for _ in range(13))
            row = conn.execute("SELECT 1 FROM Tickets WHERE Ticket_No=?", (code,)).fetchone()
            if row is None:
                return code
        raise RuntimeError("Could not generate unique Ticket_No.")

    def _online_sales_emp_id(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT Emp_ID FROM Employees WHERE Email_ID='online.sales@demo.local'").fetchone()
        if row:
            return int(row["Emp_ID"])
        row = conn.execute("SELECT Emp_ID FROM Employees ORDER BY Emp_ID LIMIT 1").fetchone()
        if row is None:
            raise ValueError("No employee/system account found.")
        return int(row["Emp_ID"])

    def _create_paid_booking_conn(
        self,
        conn: sqlite3.Connection,
        ps_id: int,
        flight_id: int,
        seat_no: str,
        payment_type: str,
        note: str = "",
        addon_codes: list[str] | None = None,
        seed: bool = False,
    ) -> dict:
        seat_no = normalize_seat(seat_no)
        if not is_valid_seat(seat_no):
            raise ValueError("Seat number must be like 12A, 9C, 1F.")
        if payment_type not in PAYMENT_TYPES:
            raise ValueError("Invalid payment type.")
        info = conn.execute(
            """
            SELECT f.Flight_ID, COALESCE(f.Flight_No, 'FL-' || f.Flight_ID) AS Flight_No,
                   f.Flight_date, at.Capacity, af.Fare_ID, af.Charge_Amount
            FROM Flight f
            JOIN Airplane_type at ON at.A_ID = f.A_ID
            JOIN AirFare af ON af.Fare_ID = f.Fare_ID
            WHERE f.Flight_ID=?
            """,
            (flight_id,),
        ).fetchone()
        if info is None:
            raise ValueError("Flight not found.")
        if not seed and datetime.strptime(info["Flight_date"], "%Y-%m-%d").date() < datetime.now().date():
            raise ValueError("Cannot book a past flight.")
        active_count = conn.execute(
            """
            SELECT COUNT(*) AS n FROM Bookings
            WHERE Flight_ID=? AND Status IN ('PendingPayment','Confirmed','Ticketed')
            """,
            (flight_id,),
        ).fetchone()["n"]
        if active_count >= int(info["Capacity"]):
            raise ValueError("This flight is full.")

        addon_codes = list(dict.fromkeys(addon_codes or []))
        addon_rows = []
        if addon_codes:
            placeholders = ",".join("?" for _ in addon_codes)
            rows = conn.execute(
                f"SELECT Addon_Code, Addon_Name, Price FROM Addon_Catalog WHERE Is_Active=1 AND Addon_Code IN ({placeholders})",
                tuple(addon_codes),
            ).fetchall()
            row_by_code = {row["Addon_Code"]: row for row in rows}
            if len(row_by_code) != len(addon_codes):
                raise ValueError("Invalid add-on selected.")
            addon_rows = [row_by_code[code] for code in addon_codes]
        addon_total = sum(float(row["Price"]) for row in addon_rows)
        total_amount = float(info["Charge_Amount"]) + addon_total

        max_row = (int(info["Capacity"]) + 5) // 6
        row_num = int(re.match(r"\d+", seat_no).group(0))
        if row_num > max_row:
            raise ValueError(f"Seat row cannot exceed {max_row} for this aircraft.")

        pnr = self._generate_unique_code(conn, "Bookings", "PNR", 6)
        ticket_no = self._generate_ticket_no(conn)
        emp_id = self._online_sales_emp_id(conn)

        cur = conn.execute(
            """
            INSERT INTO Bookings (
                PNR, Ps_ID, Flight_ID, Seat_No, Status, Fare_ID, Amount,
                Created_At, Confirmed_At
            )
            VALUES (?, ?, ?, ?, 'Ticketed', ?, ?, datetime('now'), datetime('now'))
            """,
            (pnr, ps_id, flight_id, seat_no, info["Fare_ID"], total_amount),
        )
        booking_id = int(cur.lastrowid)
        for addon in addon_rows:
            conn.execute(
                """
                INSERT INTO Booking_Addons (Booking_ID, Addon_Code, Price_At_Booking)
                VALUES (?, ?, ?)
                """,
                (booking_id, addon["Addon_Code"], addon["Price"]),
            )
        conn.execute(
            """
            INSERT INTO Payments (Booking_ID, Payment_Type, Amount, Status, Paid_At)
            VALUES (?, ?, ?, 'Captured', datetime('now'))
            """,
            (booking_id, payment_type, total_amount),
        )
        conn.execute(
            "INSERT INTO Tickets (Booking_ID, Ticket_No, Issued_At) VALUES (?, ?, datetime('now'))",
            (booking_id, ticket_no),
        )
        flight_date_obj = datetime.strptime(info["Flight_date"], "%Y-%m-%d").date()
        booking_date = datetime.now().date()
        if seed and booking_date > flight_date_obj:
            booking_date = flight_date_obj - timedelta(days=30)

        conn.execute(
            """
            INSERT INTO Transactions (
                Booking_ID, Booking_Date, Departure_Date, Type, Emp_ID, Ps_ID, Flight_ID, Charge_Amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (booking_id, booking_date.isoformat(), info["Flight_date"], payment_type, emp_id, ps_id, flight_id, total_amount),
        )
        if note.strip():
            conn.execute(
                """
                INSERT INTO Special_Requests (Booking_ID, Ps_ID, Request_Type, Note, Status, Created_At)
                VALUES (?, ?, 'Other', ?, 'Pending', datetime('now'))
                """,
                (booking_id, ps_id, note.strip()),
            )
        return {"booking_id": booking_id, "pnr": pnr, "ticket_no": ticket_no}

    def create_paid_booking(
        self,
        ps_id: int,
        flight_id: int,
        seat_no: str,
        payment_type: str,
        note: str = "",
        addon_codes: list[str] | None = None,
    ) -> dict:
        with self.connect() as conn:
            result = self._create_paid_booking_conn(conn, ps_id, flight_id, seat_no, payment_type, note, addon_codes)
            conn.commit()
            return result

    def passenger_bookings(self, ps_id: int):
        return self.fetchall(
            """
            SELECT * FROM v_booking_overview
            WHERE Booking_ID IN (SELECT Booking_ID FROM Bookings WHERE Ps_ID=?)
            ORDER BY Booking_ID DESC
            """,
            (ps_id,),
        )

    def all_bookings(self):
        return self.fetchall("SELECT * FROM v_booking_overview ORDER BY Booking_ID DESC")

    def cancel_booking_admin(self, booking_id: int, refund: bool = False):
        row = self.fetchone("SELECT Status FROM Bookings WHERE Booking_ID=?", (booking_id,))
        if row is None:
            raise ValueError("Booking not found.")
        if row["Status"] not in ACTIVE_BOOKING_STATUSES:
            raise ValueError(f"Booking is already {row['Status']}.")
        with self.connect() as conn:
            if refund:
                conn.execute(
                    "UPDATE Bookings SET Status='Refunded', Refunded_At=datetime('now') WHERE Booking_ID=?",
                    (booking_id,),
                )
                conn.execute("UPDATE Payments SET Status='Refunded' WHERE Booking_ID=?", (booking_id,))
            else:
                conn.execute(
                    "UPDATE Bookings SET Status='Cancelled', Cancelled_At=datetime('now') WHERE Booking_ID=?",
                    (booking_id,),
                )
            conn.commit()

    # ── Special requests ──────────────────────────────────────────
    def booking_options_for_passenger(self, ps_id: int):
        return self.fetchall(
            """
            SELECT Booking_ID, PNR, Flight_No, Take_Off_point, Destination, Flight_date, Seat_No, Booking_Status
            FROM v_booking_overview
            WHERE Booking_ID IN (SELECT Booking_ID FROM Bookings WHERE Ps_ID=?)
            ORDER BY Booking_ID DESC
            """,
            (ps_id,),
        )

    def submit_special_request(self, ps_id: int, booking_id: int, request_type: str, note: str):
        if request_type not in SPECIAL_REQUEST_TYPES:
            raise ValueError("Invalid request type.")
        if not note.strip():
            raise ValueError("Please add a short note for the request.")
        row = self.fetchone("SELECT Ps_ID FROM Bookings WHERE Booking_ID=?", (booking_id,))
        if row is None:
            raise ValueError("Booking not found.")
        if int(row["Ps_ID"]) != int(ps_id):
            raise ValueError("This booking does not belong to you.")
        self.execute(
            """
            INSERT INTO Special_Requests (Booking_ID, Ps_ID, Request_Type, Note, Status, Created_At)
            VALUES (?, ?, ?, ?, 'Pending', datetime('now'))
            """,
            (booking_id, ps_id, request_type, note.strip()),
        )

    def passenger_special_requests(self, ps_id: int):
        return self.fetchall(
            """
            SELECT sr.Request_ID, sr.Booking_ID, b.PNR, sr.Request_Type, sr.Note, sr.Status,
                   sr.Created_At, sr.Decided_At, e.Name AS Reviewer_Name
            FROM Special_Requests sr
            LEFT JOIN Bookings b ON b.Booking_ID = sr.Booking_ID
            LEFT JOIN Employees e ON e.Emp_ID = sr.Reviewed_By_Emp_ID
            WHERE sr.Ps_ID=?
            ORDER BY sr.Request_ID DESC
            """,
            (ps_id,),
        )

    def all_special_requests(self):
        return self.fetchall(
            """
            SELECT sr.Request_ID, sr.Booking_ID, b.PNR, p.Name AS Passenger_Name,
                   sr.Request_Type, sr.Note, sr.Status, sr.Created_At, sr.Decided_At,
                   e.Name AS Reviewer_Name
            FROM Special_Requests sr
            JOIN Passengers p ON p.Ps_ID = sr.Ps_ID
            LEFT JOIN Bookings b ON b.Booking_ID = sr.Booking_ID
            LEFT JOIN Employees e ON e.Emp_ID = sr.Reviewed_By_Emp_ID
            ORDER BY CASE sr.Status WHEN 'Pending' THEN 0 ELSE 1 END, sr.Request_ID DESC
            """
        )

    def approve_special_request(self, request_id: int, emp_id: int):
        row = self.fetchone("SELECT * FROM Special_Requests WHERE Request_ID=?", (request_id,))
        if row is None:
            raise ValueError("Request not found.")
        if row["Status"] != "Pending":
            raise ValueError(f"Request is already {row['Status']}.")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE Special_Requests
                SET Status='Approved', Reviewed_By_Emp_ID=?, Decided_At=datetime('now')
                WHERE Request_ID=?
                """,
                (emp_id, request_id),
            )
            if row["Booking_ID"] is not None and row["Request_Type"] == "Cancellation Request":
                conn.execute(
                    "UPDATE Bookings SET Status='Cancelled', Cancelled_At=datetime('now') WHERE Booking_ID=?",
                    (row["Booking_ID"],),
                )
            elif row["Booking_ID"] is not None and row["Request_Type"] == "Refund Request":
                conn.execute(
                    "UPDATE Bookings SET Status='Refunded', Refunded_At=datetime('now') WHERE Booking_ID=?",
                    (row["Booking_ID"],),
                )
                conn.execute("UPDATE Payments SET Status='Refunded' WHERE Booking_ID=?", (row["Booking_ID"],))
            conn.commit()

    def reject_special_request(self, request_id: int, emp_id: int):
        row = self.fetchone("SELECT Status FROM Special_Requests WHERE Request_ID=?", (request_id,))
        if row is None:
            raise ValueError("Request not found.")
        if row["Status"] != "Pending":
            raise ValueError(f"Request is already {row['Status']}.")
        self.execute(
            """
            UPDATE Special_Requests
            SET Status='Rejected', Reviewed_By_Emp_ID=?, Decided_At=datetime('now')
            WHERE Request_ID=?
            """,
            (emp_id, request_id),
        )

    # ── Reports ───────────────────────────────────────────────────
    def all_transactions(self):
        return self.fetchall(
            """
            SELECT t.TS_ID, t.Booking_ID, b.PNR, p.Name AS Passenger_Name,
                   e.Name AS Employee_Name, t.Flight_ID, r.Take_Off_point, r.Destination,
                   t.Booking_Date, t.Departure_Date, t.Type, t.Charge_Amount
            FROM Transactions t
            LEFT JOIN Bookings b ON b.Booking_ID = t.Booking_ID
            JOIN Passengers p ON p.Ps_ID = t.Ps_ID
            JOIN Employees e ON e.Emp_ID = t.Emp_ID
            JOIN Flight f ON f.Flight_ID = t.Flight_ID
            JOIN Route r ON r.Route_ID = f.Route_ID
            ORDER BY t.TS_ID DESC
            """
        )

    def kpi_passenger(self, ps_id: int) -> dict:
        return {
            "avail": self.fetchone("SELECT COUNT(*) AS n FROM Flight WHERE Flight_date >= date('now')")["n"],
            "ticketed": self.fetchone(
                "SELECT COUNT(*) AS n FROM Bookings WHERE Ps_ID=? AND Status='Ticketed'", (ps_id,)
            )["n"],
            "pending_requests": self.fetchone(
                "SELECT COUNT(*) AS n FROM Special_Requests WHERE Ps_ID=? AND Status='Pending'", (ps_id,)
            )["n"],
            "spent": self.fetchone(
                "SELECT COALESCE(SUM(Amount),0) AS s FROM Payments WHERE Booking_ID IN (SELECT Booking_ID FROM Bookings WHERE Ps_ID=?) AND Status IN ('Captured','Refunded')",
                (ps_id,),
            )["s"],
        }

    def kpi_admin(self) -> dict:
        return {
            "flights": self.fetchone("SELECT COUNT(*) AS n FROM Flight")["n"],
            "bookings": self.fetchone("SELECT COUNT(*) AS n FROM Bookings WHERE Status='Ticketed'")["n"],
            "special_pending": self.fetchone("SELECT COUNT(*) AS n FROM Special_Requests WHERE Status='Pending'")["n"],
            "revenue": self.fetchone("SELECT COALESCE(SUM(Amount),0) AS s FROM Payments WHERE Status='Captured'")["s"],
        }


class AirlineApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.repo = Repository()
        self.current_role: str | None = None
        self.current_id: int | None = None
        self.current_name: str | None = None
        self.selected_flight_id: int | None = None
        self.selected_booking_id: int | None = None
        self.selected_request_id: int | None = None
        self.route_map: dict[str, int] = {}
        self.airplane_map: dict[str, int] = {}
        self.fare_map: dict[str, int] = {}
        self.booking_map: dict[str, int] = {}
        self.passenger_map: dict[str, int] = {}
        self.admin_map: dict[str, int] = {}
        self.p_addon_vars: dict[str, tk.IntVar] = {}
        self.addon_name_map: dict[str, str] = {}
        self.addon_price_map: dict[str, float] = {}

        self.title("Airline Management System — Real-Life Booking Flow")
        self.geometry("1280x780")
        self.minsize(1120, 680)
        self.configure(bg=C["bg"])
        self._style()
        self.container = tk.Frame(self, bg=C["bg"])
        self.container.pack(fill="both", expand=True)
        self.show_login()

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("TFrame", background=C["bg"])
        st.configure("TNotebook", background=C["bg"], borderwidth=0)
        st.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 10, "bold"), background="#DDE6F0", foreground=C["primary"])
        st.map("TNotebook.Tab", background=[("selected", C["primary"])], foreground=[("selected", "white")])
        st.configure("Treeview", rowheight=28, font=("Segoe UI", 9), background=C["card"], fieldbackground=C["card"], foreground=C["text"])
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=C["primary"], foreground="white")
        st.map("Treeview", background=[("selected", C["accent"])], foreground=[("selected", "white")])
        st.configure("TEntry", padding=6)
        st.configure("TCombobox", padding=6)
        st.configure("TButton", padding=(10, 6), font=("Segoe UI", 9, "bold"))

    def clear(self):
        for child in self.container.winfo_children():
            child.destroy()

    def _button(self, parent, text, color, command):
        return tk.Button(parent, text=text, bg=color, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", command=command)

    def _label(self, parent, text, **kwargs):
        opts = {"bg": kwargs.pop("bg", C["card"]), "fg": kwargs.pop("fg", C["text"]), "font": kwargs.pop("font", ("Segoe UI", 9))}
        opts.update(kwargs)
        return tk.Label(parent, text=text, **opts)

    def _make_tree(self, parent, columns, headings, widths):
        wrapper = tk.Frame(parent, bg=C["card"])
        tree = ttk.Treeview(wrapper, columns=columns, show="headings", selectmode="browse")
        tree.tag_configure("odd", background="#F8FAFC")
        tree.tag_configure("even", background=C["card"])
        for key, title in headings:
            tree.heading(key, text=title, anchor="w")
            tree.column(key, width=widths.get(key, 120), anchor="w", minwidth=40)
        vsb = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(wrapper, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        return wrapper, tree

    def _insert_rows(self, tree, rows, value_fn):
        for item in tree.get_children():
            tree.delete(item)
        for i, row in enumerate(rows):
            tree.insert("", "end", values=value_fn(row), tags=("odd" if i % 2 else "even",))

    def _kpi_card(self, parent, title: str, value: str, color: str, col: int):
        card = tk.Frame(parent, bg=C["card"], padx=18, pady=14)
        card.grid(row=0, column=col, sticky="nsew", padx=6)
        tk.Frame(card, bg=color, width=4, height=42).pack(side="left", fill="y", padx=(0, 12))
        right = tk.Frame(card, bg=C["card"])
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text=value, bg=C["card"], fg=color, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(right, text=title, bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).pack(anchor="w")

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            "Pending": "🟡 Pending",
            "Approved": "🟢 Approved",
            "Rejected": "🔴 Rejected",
            "Cancelled": "⚫ Cancelled",
            "Ticketed": "🟢 Ticketed",
            "Confirmed": "🟢 Confirmed",
            "Refunded": "🔵 Refunded",
            "Expired": "⚫ Expired",
            "Captured": "🟢 Captured",
        }.get(status, status)

    # ── Login ─────────────────────────────────────────────────────
    def show_login(self):
        self.clear()
        header = tk.Frame(self.container, bg=C["primary"], height=108)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="✈  Airline Management System", bg=C["primary"], fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=28, pady=(18, 0))
        tk.Label(header, text="Real-life flow: passenger pays, booking is ticketed immediately; admin manages flights, refunds and special requests.", bg=C["primary"], fg=C["sidebar_fg"], font=("Segoe UI", 10)).pack(anchor="w", padx=28)

        main = tk.Frame(self.container, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=40, pady=30)
        main.columnconfigure((0, 1), weight=1)
        self._login_card(main, "🧳 Passenger Login", "Passenger", C["accent"]).grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self._login_card(main, "🛠 Admin Login", "Admin", C["primary"]).grid(row=0, column=1, sticky="nsew", padx=(14, 0))

    def _login_card(self, parent, title: str, role: str, color: str):
        card = tk.Frame(parent, bg=C["card"], padx=18, pady=18)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text=title, bg=C["card"], fg=color, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 12))
        tk.Label(card, text="Demo account", bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        combo = ttk.Combobox(card, state="readonly")
        combo.grid(row=2, column=0, sticky="ew", pady=(4, 10))
        if role == "Passenger":
            rows = self.repo.passenger_options()
            labels = [f"{r['Name']}  (ID:{r['Ps_ID']})" for r in rows]
            self.passenger_map = {labels[i]: int(rows[i]["Ps_ID"]) for i in range(len(rows))}
        else:
            rows = self.repo.admin_options()
            labels = [f"{r['Name']}  (ID:{r['Emp_ID']})" for r in rows]
            self.admin_map = {labels[i]: int(rows[i]["Emp_ID"]) for i in range(len(rows))}
        combo["values"] = labels
        if labels:
            combo.set(labels[0])
        tk.Label(card, text="Password", bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w")
        pwd = ttk.Entry(card, show="*")
        pwd.grid(row=4, column=0, sticky="ew", pady=(4, 12))
        pwd.bind("<Return>", lambda _e: self.login(role, combo, pwd))
        self._button(card, f"Enter as {role}", color, lambda: self.login(role, combo, pwd)).grid(row=5, column=0, sticky="ew")
        if role == "Passenger":
            ttk.Button(card, text="Create New Passenger Account", command=self.open_passenger_signup).grid(row=6, column=0, sticky="ew", pady=(8, 0))
        tk.Label(card, text="Default password: 1234", bg=C["card"], fg=C["muted"], font=("Segoe UI", 8)).grid(row=7, column=0, sticky="w", pady=(10, 0))
        return card

    def login(self, role, combo, pwd_entry):
        selected = combo.get().strip()
        password = pwd_entry.get().strip()
        if not selected or not password:
            messagebox.showwarning("Login", "Select a user and enter password.")
            return
        if role == "Passenger":
            user_id = self.passenger_map.get(selected)
            valid = user_id is not None and self.repo.validate_passenger_login(user_id, password)
        else:
            user_id = self.admin_map.get(selected)
            valid = user_id is not None and self.repo.validate_admin_login(user_id, password)
        if not valid:
            messagebox.showerror("Login", "Invalid account or password.")
            return
        self.current_role = role
        self.current_id = int(user_id)
        self.current_name = selected.split("  (ID:")[0]
        self.show_dashboard()

    def open_passenger_signup(self):
        win = tk.Toplevel(self)
        win.title("Create Passenger Account")
        win.geometry("420x480")
        win.configure(bg=C["bg"])
        frame = tk.Frame(win, bg=C["card"], padx=20, pady=20)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        frame.columnconfigure(0, weight=1)
        entries: dict[str, ttk.Entry] = {}
        for i, (label, key, secret) in enumerate([
            ("Full Name *", "name", False), ("Address", "address", False), ("Age *", "age", False),
            ("Contacts", "contacts", False), ("Password *", "password", True), ("Confirm *", "confirm", True),
        ]):
            tk.Label(frame, text=label, bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).grid(row=i * 2, column=0, sticky="w", pady=(6, 2))
            e = ttk.Entry(frame, show="*" if secret else "")
            e.grid(row=i * 2 + 1, column=0, sticky="ew")
            entries[key] = e
        tk.Label(frame, text="Sex", bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).grid(row=12, column=0, sticky="w", pady=(6, 2))
        sex = ttk.Combobox(frame, state="readonly", values=["F", "M", "Other"])
        sex.grid(row=13, column=0, sticky="ew")
        sex.set("F")

        def create():
            try:
                if entries["password"].get() != entries["confirm"].get():
                    raise ValueError("Passwords do not match.")
                age = int(entries["age"].get().strip())
                self.repo.create_passenger_account(
                    entries["name"].get(), entries["address"].get(), age, sex.get(), entries["contacts"].get(), entries["password"].get()
                )
            except Exception as exc:
                messagebox.showerror("Account", str(exc), parent=win)
                return
            messagebox.showinfo("Account", "Account created. You can now login.", parent=win)
            win.destroy()
            self.show_login()

        self._button(frame, "Create Account", C["success"], create).grid(row=14, column=0, sticky="ew", pady=(16, 0))

    # ── Dashboard frame ───────────────────────────────────────────
    def show_dashboard(self):
        self.clear()
        bar = tk.Frame(self.container, bg=C["primary"], height=54)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="✈ AMS", bg=C["primary"], fg="white", font=("Segoe UI", 13, "bold")).pack(side="left", padx=20)
        tk.Label(bar, text=f"{self.current_name} · {self.current_role}", bg=C["primary"], fg=C["sidebar_fg"], font=("Segoe UI", 10)).pack(side="left")
        self._button(bar, "Logout", C["danger"], self.show_login).pack(side="right", padx=16, pady=10)
        if self.current_role == "Passenger":
            self.build_passenger_screen()
        else:
            self.build_admin_screen()

    # ── Passenger screens ─────────────────────────────────────────
    def build_passenger_screen(self):
        wrap = tk.Frame(self.container, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        kpi = self.repo.kpi_passenger(int(self.current_id))
        kpi_row = tk.Frame(wrap, bg=C["bg"])
        kpi_row.pack(fill="x", pady=(0, 14))
        for i, (color, title, value) in enumerate([
            (C["accent"], "Available Flights", str(kpi["avail"])),
            (C["success"], "Ticketed Trips", str(kpi["ticketed"])),
            (C["warning"], "Pending Special Requests", str(kpi["pending_requests"])),
            (C["primary"], "Paid Total (₺)", f"{kpi['spent']:,.0f}"),
        ]):
            kpi_row.columnconfigure(i, weight=1)
            self._kpi_card(kpi_row, title, value, color, i)
        notebook = ttk.Notebook(wrap)
        notebook.pack(fill="both", expand=True)
        flights_tab = tk.Frame(notebook, bg=C["bg"])
        trips_tab = tk.Frame(notebook, bg=C["bg"])
        requests_tab = tk.Frame(notebook, bg=C["bg"])
        notebook.add(flights_tab, text=" ✈ Flights ")
        notebook.add(trips_tab, text=" 🎫 My Trips ")
        notebook.add(requests_tab, text=" 📝 Special Requests ")
        self._passenger_flights_tab(flights_tab)
        self._passenger_trips_tab(trips_tab)
        self._passenger_requests_tab(requests_tab)
        self.refresh_passenger_flights()
        self.refresh_passenger_trips()
        self.refresh_passenger_special_requests()

    def _passenger_flights_tab(self, parent):
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)
        filt = tk.Frame(parent, bg=C["card"], padx=14, pady=10)
        filt.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(10, 6))
        filt.columnconfigure((0, 1, 2), weight=1)
        self._label(filt, "Search flight/city/aircraft", fg=C["muted"]).grid(row=0, column=0, sticky="w")
        self.p_keyword = ttk.Entry(filt)
        self.p_keyword.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self._label(filt, "Date (YYYY-MM-DD)", fg=C["muted"]).grid(row=0, column=1, sticky="w")
        self.p_date = ttk.Entry(filt)
        self.p_date.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        btns = tk.Frame(filt, bg=C["card"])
        btns.grid(row=1, column=2, sticky="ew")
        self._button(btns, "Filter", C["accent"], self.refresh_passenger_flights).pack(side="left")
        self._button(btns, "Reset", C["muted"], self.reset_passenger_filter).pack(side="left", padx=(6, 0))
        tbl, self.p_flight_tree = self._make_tree(
            parent,
            ("ID", "No", "Route", "Date", "Dep", "Arr", "Aircraft", "Seats", "Fare"),
            [("ID", "ID"), ("No", "No"), ("Route", "Route"), ("Date", "Date"), ("Dep", "Dep"), ("Arr", "Arr"), ("Aircraft", "Aircraft"), ("Seats", "Available"), ("Fare", "Fare ₺")],
            {"ID": 45, "No": 80, "Route": 180, "Date": 100, "Dep": 65, "Arr": 65, "Aircraft": 120, "Seats": 90, "Fare": 90},
        )
        tbl.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.p_flight_tree.bind("<<TreeviewSelect>>", self.on_select_passenger_flight)

        # Scrollable booking panel — content often exceeds window height
        outer = tk.Frame(parent, bg=C["card"])
        outer.grid(row=1, column=1, sticky="nsew", pady=(0, 10))
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        bk_canvas = tk.Canvas(outer, bg=C["card"], highlightthickness=0)
        bk_vsb = ttk.Scrollbar(outer, orient="vertical", command=bk_canvas.yview)
        bk_canvas.configure(yscrollcommand=bk_vsb.set)
        bk_canvas.grid(row=0, column=0, sticky="nsew")
        bk_vsb.grid(row=0, column=1, sticky="ns")

        act = tk.Frame(bk_canvas, bg=C["card"], padx=16, pady=16)
        bk_win = bk_canvas.create_window((0, 0), window=act, anchor="nw")

        def _bk_resize(event):
            bk_canvas.itemconfigure(bk_win, width=event.width)

        bk_canvas.bind("<Configure>", _bk_resize)
        act.bind("<Configure>", lambda e: bk_canvas.configure(scrollregion=bk_canvas.bbox("all")))

        def _bk_scroll(event):
            bk_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        bk_canvas.bind("<MouseWheel>", _bk_scroll)
        act.bind("<MouseWheel>", _bk_scroll)

        act.columnconfigure(0, weight=1)
        self._label(act, "Pay & Book Now", fg=C["primary"], font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.selected_flight_label = tk.Label(act, text="No flight selected", bg="#EFF6FF", fg=C["accent"], padx=10, pady=8, wraplength=220, justify="left")
        self.selected_flight_label.grid(row=1, column=0, sticky="ew", pady=(8, 12))
        self._label(act, "Seat Number *", fg=C["muted"]).grid(row=2, column=0, sticky="w")
        self.p_seat = ttk.Entry(act)
        self.p_seat.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        tk.Button(act, text="Show Seat Map", bg="#DDE6F0", fg=C["primary"], font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2", command=self.open_seat_map).grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self._label(act, "Payment Type", fg=C["muted"]).grid(row=5, column=0, sticky="w")
        self.p_payment = ttk.Combobox(act, state="readonly", values=PAYMENT_TYPES)
        self.p_payment.grid(row=6, column=0, sticky="ew", pady=(2, 10))
        self.p_payment.set("Card")

        self._label(act, "Paid add-ons", fg=C["muted"]).grid(row=7, column=0, sticky="w")
        addon_box = tk.Frame(act, bg=C["card"])
        addon_box.grid(row=8, column=0, sticky="ew", pady=(2, 8))
        addon_box.columnconfigure(0, weight=1)
        addon_box.bind("<MouseWheel>", _bk_scroll)
        self.p_addon_vars = {}
        self.addon_name_map = {}
        self.addon_price_map = {}
        for i, addon in enumerate(self.repo.list_addons()):
            code = addon["Addon_Code"]
            price = float(addon["Price"])
            self.addon_name_map[code] = addon["Addon_Name"]
            self.addon_price_map[code] = price
            var = tk.IntVar(value=0)
            self.p_addon_vars[code] = var
            cb = tk.Checkbutton(
                addon_box,
                text=f"{addon['Addon_Name']} (+₺{price:,.0f})",
                variable=var,
                command=self.update_total_preview,
                bg=C["card"],
                fg=C["text"],
                activebackground=C["card"],
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
            )
            cb.grid(row=i, column=0, sticky="ew")
            cb.bind("<MouseWheel>", _bk_scroll)
        self.p_total_label = tk.Label(act, text="Total: select a flight", bg="#F8FAFC", fg=C["primary"], padx=10, pady=7, font=("Segoe UI", 9, "bold"), wraplength=230, justify="left")
        self.p_total_label.grid(row=9, column=0, sticky="ew", pady=(0, 10))

        self._label(act, "Optional note / special request", fg=C["muted"]).grid(row=10, column=0, sticky="w")
        self.p_note = tk.Text(act, height=3, font=("Segoe UI", 9), bg="#F8FAFC", relief="flat")
        self.p_note.grid(row=11, column=0, sticky="ew", pady=(2, 10))
        self._button(act, "💳 Pay & Book Now", C["success"], self.pay_and_book_now).grid(row=12, column=0, sticky="ew")
        tk.Label(act, text="Payment is simulated. Paid add-ons are included in the ticket total immediately. Admin approval is only for later requests such as cancellation/refund/assistance.", bg=C["card"], fg=C["muted"], font=("Segoe UI", 8), justify="left", wraplength=230).grid(row=13, column=0, sticky="w", pady=(8, 0))

    def _passenger_trips_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        self._button(ctrl, "Refresh", C["muted"], self.refresh_passenger_trips).pack(side="left")
        tbl, self.p_trip_tree = self._make_tree(
            parent,
            ("Booking", "PNR", "Ticket", "Flight", "Route", "Date", "Seat", "Status", "Addons", "Amount", "Payment"),
            [("Booking", "Booking"), ("PNR", "PNR"), ("Ticket", "Ticket"), ("Flight", "Flight"), ("Route", "Route"), ("Date", "Date"), ("Seat", "Seat"), ("Status", "Status"), ("Addons", "Add-ons"), ("Amount", "Amount"), ("Payment", "Payment")],
            {"Booking": 70, "PNR": 80, "Ticket": 110, "Flight": 80, "Route": 170, "Date": 100, "Seat": 60, "Status": 110, "Addons": 240, "Amount": 90, "Payment": 90},
        )
        tbl.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

    def _passenger_requests_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        form = tk.Frame(parent, bg=C["card"], padx=14, pady=10)
        form.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        form.columnconfigure((0, 1, 2, 3), weight=1)
        self._label(form, "Booking", fg=C["muted"]).grid(row=0, column=0, sticky="w")
        self.p_req_booking = ttk.Combobox(form, state="readonly")
        self.p_req_booking.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._label(form, "Request Type", fg=C["muted"]).grid(row=0, column=1, sticky="w")
        self.p_req_type = ttk.Combobox(form, state="readonly", values=SPECIAL_REQUEST_TYPES)
        self.p_req_type.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        self.p_req_type.set("Wheelchair Assistance")
        self._label(form, "Note", fg=C["muted"]).grid(row=0, column=2, sticky="w")
        self.p_req_note = ttk.Entry(form)
        self.p_req_note.grid(row=1, column=2, sticky="ew", padx=(0, 8))
        self._button(form, "Submit Request", C["accent"], self.submit_passenger_special_request).grid(row=1, column=3, sticky="ew")
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self._button(ctrl, "Refresh", C["muted"], self.refresh_passenger_special_requests).pack(side="left")
        tbl, self.p_req_tree = self._make_tree(
            parent,
            ("ID", "PNR", "Type", "Status", "Note", "Created", "Decided"),
            [("ID", "ID"), ("PNR", "PNR"), ("Type", "Type"), ("Status", "Status"), ("Note", "Note"), ("Created", "Created"), ("Decided", "Decided")],
            {"ID": 55, "PNR": 90, "Type": 160, "Status": 110, "Note": 260, "Created": 140, "Decided": 140},
        )
        tbl.grid(row=2, column=0, sticky="nsew", pady=(0, 10))

    def refresh_passenger_flights(self):
        rows = self.repo.list_flights(self.p_keyword.get().strip(), self.p_date.get().strip())
        self._insert_rows(
            self.p_flight_tree,
            rows,
            lambda r: (
                r["Flight_ID"], r["Flight_No"], f"{r['Take_Off_point']} → {r['Destination']}", r["Flight_date"], r["Departure"], r["Arrival"], r["Company"], f"{r['Available_Count']} / {r['Capacity']}", f"{r['Charge_Amount']:,.2f}",
            ),
        )

    def reset_passenger_filter(self):
        self.p_keyword.delete(0, tk.END)
        self.p_date.delete(0, tk.END)
        self.refresh_passenger_flights()

    def on_select_passenger_flight(self, _event=None):
        sel = self.p_flight_tree.selection()
        if not sel:
            return
        values = self.p_flight_tree.item(sel[0], "values")
        self.selected_flight_id = int(values[0])
        self.selected_flight_label.configure(text=f"Selected: {values[1]}\n{values[2]}\n{values[3]} {values[4]}-{values[5]}")
        self.update_total_preview()

    def selected_addon_codes(self) -> list[str]:
        return [code for code, var in getattr(self, "p_addon_vars", {}).items() if var.get()]

    def update_total_preview(self):
        if not hasattr(self, "p_total_label"):
            return
        if self.selected_flight_id is None:
            self.p_total_label.configure(text="Total: select a flight")
            return
        info = self.repo.flight_capacity_and_price(self.selected_flight_id)
        if info is None:
            self.p_total_label.configure(text="Total: flight info not found")
            return
        base = float(info["Charge_Amount"])
        addon_total = sum(self.addon_price_map.get(code, 0.0) for code in self.selected_addon_codes())
        self.p_total_label.configure(
            text=f"Base ₺{base:,.2f} + Add-ons ₺{addon_total:,.2f}\nTotal ₺{base + addon_total:,.2f}"
        )

    def pay_and_book_now(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Booking", "Select a flight first.")
            return

        seat = normalize_seat(self.p_seat.get())
        note = self.p_note.get("1.0", "end").strip()
        payment_type = self.p_payment.get().strip()
        addon_codes = self.selected_addon_codes()

        if not seat:
            messagebox.showwarning("Booking", "Enter or select a seat first.")
            return
        if not is_valid_seat(seat):
            messagebox.showwarning("Booking", "Seat number must be like 12A, 9C, 1F.")
            return
        if not payment_type:
            messagebox.showwarning("Booking", "Select a payment type.")
            return

        # Real-life-inspired demo rule:
        # Cash can be treated as pay-at-counter / immediate manual collection in this demo.
        # Every other payment type opens a simulated payment screen first.
        if payment_type == "Cash":
            self._complete_paid_booking(seat, payment_type, note, addon_codes)
            return

        self.open_simulated_payment_window(seat, payment_type, note, addon_codes)

    def _complete_paid_booking(self, seat: str, payment_type: str, note: str, addon_codes: list[str] | None = None):
        try:
            result = self.repo.create_paid_booking(
                int(self.current_id),
                self.selected_flight_id,
                seat,
                payment_type,
                note,
                addon_codes,
            )
        except Exception as exc:
            messagebox.showerror("Booking", str(exc))
            return

        self.p_seat.delete(0, tk.END)
        self.p_note.delete("1.0", tk.END)
        for var in getattr(self, "p_addon_vars", {}).values():
            var.set(0)
        self.update_total_preview()
        self.refresh_passenger_flights()
        self.refresh_passenger_trips()
        self.refresh_passenger_special_requests()
        messagebox.showinfo(
            "Booking Confirmed",
            f"Payment completed successfully.\nBooking ticketed immediately.\n\nPNR: {result['pnr']}\nTicket No: {result['ticket_no']}",
        )

    def open_simulated_payment_window(self, seat: str, payment_type: str, note: str, addon_codes: list[str] | None = None):
        addon_codes = addon_codes or []
        info = self.repo.flight_capacity_and_price(self.selected_flight_id)
        if info is None:
            messagebox.showerror("Payment", "Flight info not found.")
            return
        base_amount = float(info["Charge_Amount"])
        addon_total = sum(self.addon_price_map.get(code, 0.0) for code in addon_codes)
        total_amount = base_amount + addon_total
        selected_addons = ", ".join(self.addon_name_map.get(code, code) for code in addon_codes) or "None"

        win = tk.Toplevel(self)
        win.title("Simulated Payment")
        win.geometry("460x580")
        win.resizable(False, False)
        win.configure(bg=C["bg"])
        win.transient(self)
        win.grab_set()

        card = tk.Frame(win, bg=C["card"], padx=20, pady=18)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.columnconfigure(0, weight=1)

        tk.Label(
            card,
            text="💳 Simulated Payment",
            bg=C["card"],
            fg=C["primary"],
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            card,
            text="No real payment is processed. Enter demo card details to continue.",
            bg=C["card"],
            fg=C["muted"],
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 14))

        summary = tk.Frame(card, bg="#EFF6FF", padx=12, pady=10)
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        summary.columnconfigure(1, weight=1)
        tk.Label(summary, text="Payment Type", bg="#EFF6FF", fg=C["muted"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(summary, text=payment_type, bg="#EFF6FF", fg=C["text"], font=("Segoe UI", 9)).grid(row=0, column=1, sticky="e")
        tk.Label(summary, text="Seat", bg="#EFF6FF", fg=C["muted"], font=("Segoe UI", 8, "bold")).grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Label(summary, text=seat, bg="#EFF6FF", fg=C["text"], font=("Segoe UI", 9)).grid(row=1, column=1, sticky="e", pady=(4, 0))
        tk.Label(summary, text="Base Fare", bg="#EFF6FF", fg=C["muted"], font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="w", pady=(4, 0))
        tk.Label(summary, text=f"₺{base_amount:,.2f}", bg="#EFF6FF", fg=C["text"], font=("Segoe UI", 9)).grid(row=2, column=1, sticky="e", pady=(4, 0))
        tk.Label(summary, text="Add-ons", bg="#EFF6FF", fg=C["muted"], font=("Segoe UI", 8, "bold")).grid(row=3, column=0, sticky="w", pady=(4, 0))
        tk.Label(summary, text=f"{selected_addons} (+₺{addon_total:,.2f})", bg="#EFF6FF", fg=C["text"], font=("Segoe UI", 9), wraplength=230, justify="right").grid(row=3, column=1, sticky="e", pady=(4, 0))
        tk.Label(summary, text="Total Amount", bg="#EFF6FF", fg=C["muted"], font=("Segoe UI", 8, "bold")).grid(row=4, column=0, sticky="w", pady=(4, 0))
        tk.Label(summary, text=f"₺{total_amount:,.2f}", bg="#EFF6FF", fg=C["success"], font=("Segoe UI", 11, "bold")).grid(row=4, column=1, sticky="e", pady=(4, 0))

        fields = tk.Frame(card, bg=C["card"])
        fields.grid(row=3, column=0, sticky="ew")
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)

        def label(row, text, col=0, colspan=1):
            tk.Label(fields, text=text, bg=C["card"], fg=C["muted"], font=("Segoe UI", 9)).grid(
                row=row, column=col, columnspan=colspan, sticky="w", pady=(8, 2)
            )

        label(0, "Cardholder Name *", colspan=2)
        name_entry = ttk.Entry(fields)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew")

        label(2, "Card Number *", colspan=2)
        number_entry = ttk.Entry(fields)
        number_entry.grid(row=3, column=0, columnspan=2, sticky="ew")
        number_entry.insert(0, "4242 4242 4242 4242")

        label(4, "Expiry (MM/YY) *", col=0)
        label(4, "CVV *", col=1)
        expiry_entry = ttk.Entry(fields)
        expiry_entry.grid(row=5, column=0, sticky="ew", padx=(0, 8))
        expiry_entry.insert(0, "12/30")
        cvv_entry = ttk.Entry(fields, show="*")
        cvv_entry.grid(row=5, column=1, sticky="ew")
        cvv_entry.insert(0, "123")

        error_label = tk.Label(card, text="", bg=C["card"], fg=C["danger"], font=("Segoe UI", 9), wraplength=360, justify="left")
        error_label.grid(row=4, column=0, sticky="w", pady=(10, 0))

        def validate_payment_fields() -> bool:
            name = name_entry.get().strip()
            number = re.sub(r"\D", "", number_entry.get())
            expiry = expiry_entry.get().strip()
            cvv = cvv_entry.get().strip()

            if len(name) < 3:
                error_label.configure(text="Cardholder name is required.")
                return False
            if not re.fullmatch(r"\d{13,19}", number):
                error_label.configure(text="Card number must contain 13 to 19 digits.")
                return False
            if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", expiry):
                error_label.configure(text="Expiry must be in MM/YY format.")
                return False
            if not re.fullmatch(r"\d{3,4}", cvv):
                error_label.configure(text="CVV must contain 3 or 4 digits.")
                return False

            month = int(expiry[:2])
            year = 2000 + int(expiry[-2:])
            now = datetime.now()
            if (year, month) < (now.year, now.month):
                error_label.configure(text="Card expiry date cannot be in the past.")
                return False

            error_label.configure(text="")
            return True

        def confirm_payment():
            if not validate_payment_fields():
                return
            win.grab_release()
            win.destroy()
            self._complete_paid_booking(seat, payment_type, note, addon_codes)

        btn_row = tk.Frame(card, bg=C["card"])
        btn_row.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        tk.Button(
            btn_row,
            text="Cancel",
            bg=C["muted"],
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=lambda: (win.grab_release(), win.destroy()),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tk.Button(
            btn_row,
            text="Pay Now (Demo)",
            bg=C["success"],
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=confirm_payment,
        ).grid(row=0, column=1, sticky="ew")

        name_entry.focus_set()
        win.bind("<Return>", lambda _event: confirm_payment())
        win.protocol("WM_DELETE_WINDOW", lambda: (win.grab_release(), win.destroy()))

    def open_seat_map(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Seat Map", "Select a flight first.")
            return
        info = self.repo.flight_capacity_and_price(self.selected_flight_id)
        if info is None:
            messagebox.showerror("Seat Map", "Flight info not found.")
            return
        reserved = set(self.repo.occupied_seats_for_flight(self.selected_flight_id))
        capacity = int(info["Capacity"])
        rows_count = (capacity + 5) // 6
        cols = ["A", "B", "C", "D", "E", "F"]
        win = tk.Toplevel(self)
        win.title(f"Seat Map — Flight {self.selected_flight_id}")
        win.configure(bg=C["bg"])
        tk.Label(win, text=f"Flight {self.selected_flight_id} · Capacity: {capacity}", bg=C["bg"], fg=C["primary"], font=("Segoe UI", 12, "bold")).pack(pady=(14, 4))
        frame = tk.Frame(win, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        canvas = tk.Canvas(frame, bg=C["bg"], highlightthickness=0, width=520, height=460)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=C["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        selected = tk.StringVar(value="")
        buttons = []

        def choose(seat_no: str):
            if seat_no in reserved:
                return
            selected.set(seat_no)
            for b, s in buttons:
                if s in reserved:
                    b.configure(bg="#FEE2E2", fg="#991B1B")
                elif s == selected.get():
                    b.configure(bg=C["accent"], fg="white")
                else:
                    b.configure(bg="#DCFCE7", fg="#166534")

        seat_count = 0
        for row in range(1, rows_count + 1):
            tk.Label(inner, text=str(row), bg=C["bg"], fg=C["muted"], width=4).grid(row=row, column=0, padx=3, pady=2)
            for ci, col in enumerate(cols):
                seat_count += 1
                if seat_count > capacity:
                    break
                seat_no = f"{row}{col}"
                grid_col = ci + 1 if ci < 3 else ci + 2
                bg, fg = ("#FEE2E2", "#991B1B") if seat_no in reserved else ("#DCFCE7", "#166534")
                btn = tk.Button(inner, text=seat_no, width=5, bg=bg, fg=fg, relief="flat", command=lambda s=seat_no: choose(s))
                btn.grid(row=row, column=grid_col, padx=2, pady=2)
                buttons.append((btn, seat_no))
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        bottom = tk.Frame(win, bg=C["bg"])
        bottom.pack(fill="x", padx=20, pady=(0, 14))
        tk.Label(bottom, textvariable=selected, bg=C["bg"], fg=C["primary"], font=("Segoe UI", 11, "bold")).pack(side="left")

        def apply_selected():
            if not selected.get():
                messagebox.showwarning("Seat", "Select an available seat.", parent=win)
                return
            self.p_seat.delete(0, tk.END)
            self.p_seat.insert(0, selected.get())
            win.destroy()

        self._button(bottom, "Use Selected Seat", C["success"], apply_selected).pack(side="right")

    def refresh_passenger_trips(self):
        rows = self.repo.passenger_bookings(int(self.current_id))
        self._insert_rows(
            self.p_trip_tree,
            rows,
            lambda r: (
                r["Booking_ID"], r["PNR"], r["Ticket_No"] or "-", r["Flight_No"], f"{r['Take_Off_point']} → {r['Destination']}", r["Flight_date"], r["Seat_No"], self._status_icon(r["Booking_Status"]), r["Addons"] or "-", f"{r['Amount']:,.2f}", r["Payment_Type"] or "-",
            ),
        )
        self.refresh_booking_combo()

    def refresh_booking_combo(self):
        rows = self.repo.booking_options_for_passenger(int(self.current_id))
        labels = [f"{r['PNR']} | {r['Flight_No']} | {r['Take_Off_point']}→{r['Destination']} | Seat {r['Seat_No']} | {r['Booking_Status']}" for r in rows]
        self.booking_map = {labels[i]: int(rows[i]["Booking_ID"]) for i in range(len(rows))}
        if hasattr(self, "p_req_booking"):
            self.p_req_booking["values"] = labels
            if labels and not self.p_req_booking.get():
                self.p_req_booking.set(labels[0])

    def submit_passenger_special_request(self):
        label = self.p_req_booking.get().strip()
        booking_id = self.booking_map.get(label)
        if booking_id is None:
            messagebox.showwarning("Special Request", "Select a booking.")
            return
        try:
            self.repo.submit_special_request(int(self.current_id), booking_id, self.p_req_type.get(), self.p_req_note.get())
        except Exception as exc:
            messagebox.showerror("Special Request", str(exc))
            return
        self.p_req_note.delete(0, tk.END)
        self.refresh_passenger_special_requests()
        messagebox.showinfo("Special Request", "Request submitted. Admin will review it.")

    def refresh_passenger_special_requests(self):
        if hasattr(self, "p_req_tree"):
            rows = self.repo.passenger_special_requests(int(self.current_id))
            self._insert_rows(
                self.p_req_tree,
                rows,
                lambda r: (r["Request_ID"], r["PNR"] or "-", r["Request_Type"], self._status_icon(r["Status"]), r["Note"] or "", r["Created_At"], r["Decided_At"] or "-"),
            )

    # ── Admin screens ─────────────────────────────────────────────
    def build_admin_screen(self):
        wrap = tk.Frame(self.container, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        kpi = self.repo.kpi_admin()
        kpi_row = tk.Frame(wrap, bg=C["bg"])
        kpi_row.pack(fill="x", pady=(0, 14))
        for i, (color, title, value) in enumerate([
            (C["accent"], "Total Flights", str(kpi["flights"])),
            (C["success"], "Ticketed Bookings", str(kpi["bookings"])),
            (C["warning"], "Pending Special Requests", str(kpi["special_pending"])),
            (C["primary"], "Captured Revenue (₺)", f"{kpi['revenue']:,.0f}"),
        ]):
            kpi_row.columnconfigure(i, weight=1)
            self._kpi_card(kpi_row, title, value, color, i)
        notebook = ttk.Notebook(wrap)
        notebook.pack(fill="both", expand=True)
        flights_tab = tk.Frame(notebook, bg=C["bg"])
        bookings_tab = tk.Frame(notebook, bg=C["bg"])
        special_tab = tk.Frame(notebook, bg=C["bg"])
        tx_tab = tk.Frame(notebook, bg=C["bg"])
        notebook.add(flights_tab, text=" ✈ Flights ")
        notebook.add(bookings_tab, text=" 🎫 Bookings ")
        notebook.add(special_tab, text=" 📝 Special Requests ")
        notebook.add(tx_tab, text=" 💳 Transactions ")
        self._admin_flights_tab(flights_tab)
        self._admin_bookings_tab(bookings_tab)
        self._admin_special_tab(special_tab)
        self._admin_transactions_tab(tx_tab)
        self.refresh_admin_flights()
        self.refresh_admin_bookings()
        self.refresh_admin_special_requests()
        self.refresh_admin_transactions()

    def _load_flight_form_options(self):
        routes = self.repo.list_routes()
        planes = self.repo.list_airplanes()
        fares = self.repo.list_airfares()
        route_labels = [f"{r['Route_ID']} | {r['Take_Off_point']} → {r['Destination']} ({r['R_type']})" for r in routes]
        plane_labels = [f"{p['A_ID']} | {p['Company']} | cap:{p['Capacity']}" for p in planes]
        fare_labels = [f"{f['Fare_ID']} | {f['Charge_Amount']:,.2f} | {f['Description']}" for f in fares]
        self.route_map = {route_labels[i]: int(routes[i]["Route_ID"]) for i in range(len(routes))}
        self.airplane_map = {plane_labels[i]: int(planes[i]["A_ID"]) for i in range(len(planes))}
        self.fare_map = {fare_labels[i]: int(fares[i]["Fare_ID"]) for i in range(len(fares))}
        self.a_route["values"] = route_labels
        self.a_plane["values"] = plane_labels
        self.a_fare["values"] = fare_labels
        if route_labels and not self.a_route.get():
            self.a_route.set(route_labels[0])
        if plane_labels and not self.a_plane.get():
            self.a_plane.set(plane_labels[0])
        if fare_labels and not self.a_fare.get():
            self.a_fare.set(fare_labels[0])

    def _admin_flights_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)
        form = tk.Frame(parent, bg=C["card"], padx=14, pady=14)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)
        widgets = []
        for i, (label, attr) in enumerate([("Flight No", "a_no"), ("Departure HH:MM", "a_dep"), ("Arrival HH:MM", "a_arr"), ("Flight Date YYYY-MM-DD", "a_date")]):
            self._label(form, label, fg=C["muted"]).grid(row=i * 2, column=0, sticky="w", pady=(6, 2))
            e = ttk.Entry(form)
            e.grid(row=i * 2 + 1, column=0, sticky="ew")
            setattr(self, attr, e)
            widgets.append(e)
        for row, (label, attr) in enumerate([("Route", "a_route"), ("Aircraft", "a_plane"), ("Fare", "a_fare")], start=8):
            self._label(form, label, fg=C["muted"]).grid(row=row, column=0, sticky="w", pady=(6, 2))
            combo = ttk.Combobox(form, state="readonly")
            combo.grid(row=row + 1, column=0, sticky="ew")
            setattr(self, attr, combo)
        btns = tk.Frame(form, bg=C["card"])
        btns.grid(row=15, column=0, sticky="ew", pady=(14, 0))
        for i, (txt, color, cmd) in enumerate([
            ("Add", C["success"], self.add_admin_flight),
            ("Update", C["accent"], self.update_admin_flight),
            ("Delete", C["danger"], self.delete_admin_flight),
            ("Clear", C["muted"], self.clear_admin_flight_form),
        ]):
            btns.columnconfigure(i, weight=1)
            self._button(btns, txt, color, cmd).grid(row=0, column=i, sticky="ew", padx=3)
        self._load_flight_form_options()
        tbl, self.a_flight_tree = self._make_tree(
            parent,
            ("ID", "No", "Route", "Date", "Dep", "Arr", "Aircraft", "Seats", "Fare"),
            [("ID", "ID"), ("No", "No"), ("Route", "Route"), ("Date", "Date"), ("Dep", "Dep"), ("Arr", "Arr"), ("Aircraft", "Aircraft"), ("Seats", "Booked"), ("Fare", "Fare")],
            {"ID": 50, "No": 80, "Route": 180, "Date": 100, "Dep": 65, "Arr": 65, "Aircraft": 120, "Seats": 90, "Fare": 90},
        )
        tbl.grid(row=0, column=1, sticky="nsew", pady=10)
        self.a_flight_tree.bind("<<TreeviewSelect>>", self.on_select_admin_flight)

    def refresh_admin_flights(self):
        rows = self.repo.list_flights()
        self._insert_rows(
            self.a_flight_tree,
            rows,
            lambda r: (r["Flight_ID"], r["Flight_No"], f"{r['Take_Off_point']} → {r['Destination']}", r["Flight_date"], r["Departure"], r["Arrival"], r["Company"], f"{r['Booked_Count']} / {r['Capacity']}", f"{r['Charge_Amount']:,.2f}"),
        )

    def on_select_admin_flight(self, _event=None):
        sel = self.a_flight_tree.selection()
        if not sel:
            return
        values = self.a_flight_tree.item(sel[0], "values")
        self.selected_flight_id = int(values[0])
        self.a_no.delete(0, tk.END); self.a_no.insert(0, values[1])
        self.a_date.delete(0, tk.END); self.a_date.insert(0, values[3])
        self.a_dep.delete(0, tk.END); self.a_dep.insert(0, values[4])
        self.a_arr.delete(0, tk.END); self.a_arr.insert(0, values[5])

    def clear_admin_flight_form(self):
        self.selected_flight_id = None
        for e in [self.a_no, self.a_dep, self.a_arr, self.a_date]:
            e.delete(0, tk.END)
        self.a_route.set(""); self.a_plane.set(""); self.a_fare.set("")
        self._load_flight_form_options()

    def _flight_form_values(self):
        return (
            self.a_no.get().strip(),
            self.a_dep.get().strip(),
            self.a_arr.get().strip(),
            self.a_date.get().strip(),
            self.route_map[self.a_route.get()],
            self.airplane_map[self.a_plane.get()],
            self.fare_map[self.a_fare.get()],
        )

    def add_admin_flight(self):
        try:
            self.repo.add_flight(*self._flight_form_values())
        except Exception as exc:
            messagebox.showerror("Flights", str(exc)); return
        self.clear_admin_flight_form(); self.refresh_admin_flights()

    def update_admin_flight(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Flights", "Select a flight first."); return
        try:
            self.repo.update_flight(self.selected_flight_id, *self._flight_form_values())
        except Exception as exc:
            messagebox.showerror("Flights", str(exc)); return
        self.refresh_admin_flights()

    def delete_admin_flight(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Flights", "Select a flight first."); return
        if not messagebox.askyesno("Flights", "Delete selected flight?"):
            return
        try:
            self.repo.delete_flight(self.selected_flight_id)
        except Exception as exc:
            messagebox.showerror("Flights", str(exc)); return
        self.clear_admin_flight_form(); self.refresh_admin_flights()

    def _admin_bookings_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        self._button(ctrl, "Refresh", C["muted"], self.refresh_admin_bookings).pack(side="left")
        self._button(ctrl, "Cancel Selected", C["danger"], lambda: self.admin_cancel_or_refund(False)).pack(side="left", padx=(8, 0))
        self._button(ctrl, "Refund Selected", C["warning"], lambda: self.admin_cancel_or_refund(True)).pack(side="left", padx=(8, 0))
        tbl, self.a_booking_tree = self._make_tree(
            parent,
            ("Booking", "PNR", "Passenger", "Ticket", "Flight", "Route", "Date", "Seat", "Status", "Addons", "Amount", "Payment"),
            [("Booking", "Booking"), ("PNR", "PNR"), ("Passenger", "Passenger"), ("Ticket", "Ticket"), ("Flight", "Flight"), ("Route", "Route"), ("Date", "Date"), ("Seat", "Seat"), ("Status", "Status"), ("Addons", "Add-ons"), ("Amount", "Amount"), ("Payment", "Payment")],
            {"Booking": 70, "PNR": 80, "Passenger": 140, "Ticket": 110, "Flight": 80, "Route": 160, "Date": 100, "Seat": 60, "Status": 110, "Addons": 250, "Amount": 90, "Payment": 90},
        )
        tbl.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.a_booking_tree.bind("<<TreeviewSelect>>", self.on_select_admin_booking)

    def refresh_admin_bookings(self):
        rows = self.repo.all_bookings()
        self._insert_rows(
            self.a_booking_tree,
            rows,
            lambda r: (r["Booking_ID"], r["PNR"], r["Passenger_Name"], r["Ticket_No"] or "-", r["Flight_No"], f"{r['Take_Off_point']} → {r['Destination']}", r["Flight_date"], r["Seat_No"], self._status_icon(r["Booking_Status"]), r["Addons"] or "-", f"{r['Amount']:,.2f}", r["Payment_Type"] or "-"),
        )

    def on_select_admin_booking(self, _event=None):
        sel = self.a_booking_tree.selection()
        if sel:
            self.selected_booking_id = int(self.a_booking_tree.item(sel[0], "values")[0])

    def admin_cancel_or_refund(self, refund: bool):
        if self.selected_booking_id is None:
            messagebox.showwarning("Bookings", "Select a booking first."); return
        action = "refund" if refund else "cancel"
        if not messagebox.askyesno("Bookings", f"Are you sure you want to {action} this booking?"):
            return
        try:
            self.repo.cancel_booking_admin(self.selected_booking_id, refund=refund)
        except Exception as exc:
            messagebox.showerror("Bookings", str(exc)); return
        self.refresh_admin_bookings(); self.refresh_admin_transactions()

    def _admin_special_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        self._button(ctrl, "Refresh", C["muted"], self.refresh_admin_special_requests).pack(side="left")
        self._button(ctrl, "Approve", C["success"], self.approve_admin_special_request).pack(side="left", padx=(8, 0))
        self._button(ctrl, "Reject", C["danger"], self.reject_admin_special_request).pack(side="left", padx=(8, 0))
        tbl, self.a_req_tree = self._make_tree(
            parent,
            ("ID", "PNR", "Passenger", "Type", "Status", "Note", "Created", "Decided"),
            [("ID", "ID"), ("PNR", "PNR"), ("Passenger", "Passenger"), ("Type", "Type"), ("Status", "Status"), ("Note", "Note"), ("Created", "Created"), ("Decided", "Decided")],
            {"ID": 55, "PNR": 90, "Passenger": 140, "Type": 170, "Status": 110, "Note": 260, "Created": 140, "Decided": 140},
        )
        tbl.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.a_req_tree.bind("<<TreeviewSelect>>", self.on_select_admin_request)

    def refresh_admin_special_requests(self):
        rows = self.repo.all_special_requests()
        self._insert_rows(
            self.a_req_tree,
            rows,
            lambda r: (r["Request_ID"], r["PNR"] or "-", r["Passenger_Name"], r["Request_Type"], self._status_icon(r["Status"]), r["Note"] or "", r["Created_At"], r["Decided_At"] or "-"),
        )

    def on_select_admin_request(self, _event=None):
        sel = self.a_req_tree.selection()
        if sel:
            self.selected_request_id = int(self.a_req_tree.item(sel[0], "values")[0])

    def approve_admin_special_request(self):
        if self.selected_request_id is None:
            messagebox.showwarning("Special Requests", "Select a request first."); return
        try:
            self.repo.approve_special_request(self.selected_request_id, int(self.current_id))
        except Exception as exc:
            messagebox.showerror("Special Requests", str(exc)); return
        self.refresh_admin_special_requests(); self.refresh_admin_bookings(); self.refresh_admin_transactions()

    def reject_admin_special_request(self):
        if self.selected_request_id is None:
            messagebox.showwarning("Special Requests", "Select a request first."); return
        try:
            self.repo.reject_special_request(self.selected_request_id, int(self.current_id))
        except Exception as exc:
            messagebox.showerror("Special Requests", str(exc)); return
        self.refresh_admin_special_requests()

    def _admin_transactions_tab(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        self._button(ctrl, "Refresh", C["muted"], self.refresh_admin_transactions).pack(side="left")
        tbl, self.a_tx_tree = self._make_tree(
            parent,
            ("TS", "PNR", "Passenger", "Employee", "Flight", "Route", "Booking", "Departure", "Type", "Amount"),
            [("TS", "TS"), ("PNR", "PNR"), ("Passenger", "Passenger"), ("Employee", "Employee"), ("Flight", "Flight"), ("Route", "Route"), ("Booking", "Booking"), ("Departure", "Departure"), ("Type", "Type"), ("Amount", "Amount")],
            {"TS": 60, "PNR": 90, "Passenger": 140, "Employee": 150, "Flight": 70, "Route": 160, "Booking": 100, "Departure": 100, "Type": 90, "Amount": 90},
        )
        tbl.grid(row=1, column=0, sticky="nsew", pady=(0, 10))

    def refresh_admin_transactions(self):
        rows = self.repo.all_transactions()
        self._insert_rows(
            self.a_tx_tree,
            rows,
            lambda r: (r["TS_ID"], r["PNR"] or "-", r["Passenger_Name"], r["Employee_Name"], r["Flight_ID"], f"{r['Take_Off_point']} → {r['Destination']}", r["Booking_Date"], r["Departure_Date"], r["Type"], f"{r['Charge_Amount']:,.2f}"),
        )


def main():
    app = AirlineApp()
    app.mainloop()


if __name__ == "__main__":
    main()
