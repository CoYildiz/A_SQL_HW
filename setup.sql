PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- =====================================================
-- Airline Management System SQLite setup
-- Compatible with app.py Repository._create_schema/_seed_data
--
-- Notes:
-- - The previous simple-model tables (users/flights/reservation_requests)
--   are intentionally not created because app.py does not use them.
-- - Default demo password for all seeded users is: 1234
-- =====================================================

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
    CHECK (
        (Role = 'Passenger' AND Ps_ID IS NOT NULL AND Emp_ID IS NULL)
        OR
        (Role = 'Admin' AND Emp_ID IS NOT NULL AND Ps_ID IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_ps
ON Auth_Accounts(Ps_ID)
WHERE Ps_ID IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_emp
ON Auth_Accounts(Emp_ID)
WHERE Emp_ID IS NOT NULL;

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

-- Recreate app-owned triggers/views so rerunning setup.sql keeps definitions current.
DROP TRIGGER IF EXISTS trg_booking_seat_conflict;
DROP TRIGGER IF EXISTS trg_booking_capacity_check;
DROP TRIGGER IF EXISTS trg_booking_seat_conflict_update;
DROP TRIGGER IF EXISTS trg_ts_departure_after_booking;
DROP VIEW IF EXISTS v_booking_overview;

CREATE TRIGGER trg_booking_seat_conflict
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

CREATE TRIGGER trg_booking_capacity_check
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

CREATE TRIGGER trg_booking_seat_conflict_update
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

CREATE TRIGGER trg_ts_departure_after_booking
BEFORE INSERT ON Transactions
WHEN date(NEW.Departure_Date) < date(NEW.Booking_Date)
BEGIN
    SELECT RAISE(ABORT, 'Departure date cannot be earlier than booking date');
END;

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
    pay.Payment_Type,
    pay.Status AS Payment_Status,
    t.Ticket_No,
    b.Created_At,
    b.Confirmed_At
FROM Bookings b
JOIN Passengers p ON p.Ps_ID = b.Ps_ID
JOIN Flight f ON f.Flight_ID = b.Flight_ID
JOIN Route r ON r.Route_ID = f.Route_ID
LEFT JOIN Payments pay ON pay.Booking_ID = b.Booking_ID
LEFT JOIN Tickets t ON t.Booking_ID = b.Booking_ID;

-- =====================================================
-- Demo seed data
-- =====================================================

INSERT OR IGNORE INTO Countries (Country_code, Country_Name) VALUES
    ('TR', 'Turkiye'),
    ('DE', 'Germany'),
    ('GB', 'United Kingdom'),
    ('US', 'United States');

INSERT OR IGNORE INTO Airport (Air_Code, Air_Name, City, State, Country_code) VALUES
    ('IST', 'Istanbul Airport', 'Istanbul', 'Marmara', 'TR'),
    ('ESB', 'Esenboga Airport', 'Ankara', 'Central Anatolia', 'TR'),
    ('ADB', 'Adnan Menderes Airport', 'Izmir', 'Aegean', 'TR'),
    ('AYT', 'Antalya Airport', 'Antalya', 'Mediterranean', 'TR'),
    ('TZX', 'Trabzon Airport', 'Trabzon', 'Black Sea', 'TR'),
    ('ADA', 'Adana Airport', 'Adana', 'Mediterranean', 'TR'),
    ('LHR', 'Heathrow Airport', 'London', 'England', 'GB'),
    ('JFK', 'John F. Kennedy International Airport', 'New York', 'New York', 'US');

INSERT OR IGNORE INTO Airplane_type (A_ID, Capacity, A_weight, Company) VALUES
    (1, 180, 73500, 'Airbus A320'),
    (2, 160, 70500, 'Boeing 737'),
    (3, 260, 125000, 'Airbus A330'),
    (4, 300, 145000, 'Boeing 777');

INSERT OR IGNORE INTO Route (Route_ID, Destination, Take_Off_point, R_type) VALUES
    (1, 'ESB', 'IST', 'Domestic'),
    (2, 'AYT', 'ADB', 'Domestic'),
    (3, 'TZX', 'IST', 'Domestic'),
    (4, 'ADA', 'IST', 'Domestic'),
    (5, 'LHR', 'IST', 'International'),
    (6, 'JFK', 'IST', 'International');

INSERT OR IGNORE INTO AirFare (Fare_ID, Charge_Amount, Description) VALUES
    (1, 1499.90, 'Economy Base Fare'),
    (2, 2399.50, 'Flexible Fare'),
    (3, 3499.00, 'Domestic Business'),
    (4, 12999.00, 'International Economy'),
    (5, 24999.00, 'International Business');

INSERT OR IGNORE INTO Flight (Flight_ID, Flight_No, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID) VALUES
    (1, 'TK100', '09:00', '10:10', date('now', '+30 days'), 1, 1, 1),
    (2, 'TK204', '14:00', '15:20', date('now', '+31 days'), 2, 2, 2),
    (3, 'TK311', '18:20', '20:05', date('now', '+34 days'), 3, 1, 1),
    (4, 'TK420', '08:45', '10:20', date('now', '+37 days'), 4, 2, 2),
    (5, 'TK512', '11:30', '13:50', date('now', '+50 days'), 5, 3, 4),
    (6, 'TK901', '01:15', '12:45', date('now', '+64 days'), 6, 4, 5);

INSERT OR IGNORE INTO Passengers (Ps_ID, Name, Address, Age, Sex, Contacts) VALUES
    (1, 'Buse Yilmaz', 'Istanbul', 22, 'F', '+90-555-010-1010'),
    (2, 'Mert Kaya', 'Izmir', 24, 'M', '+90-555-020-2020'),
    (3, 'Aylin Demir', 'Ankara', 27, 'F', '+90-555-030-3030');

INSERT OR IGNORE INTO Employees (Emp_ID, Name, Address, Age, Email_ID, Contacts, Air_Code) VALUES
    (1, 'Online Sales System', 'Istanbul', 30, 'online.sales@demo.local', '+90-555-000-0001', 'IST'),
    (2, 'Ayse Yilmaz', 'Istanbul', 31, 'ayse.employee@demo.local', '+90-555-111-2233', 'IST'),
    (3, 'Can Kaya', 'Ankara', 29, 'can.employee@demo.local', '+90-555-444-5566', 'ESB');

-- SHA-256('1234')
INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash)
SELECT 'Passenger', p.Ps_ID, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'
FROM Passengers p
WHERE NOT EXISTS (
    SELECT 1 FROM Auth_Accounts a WHERE a.Ps_ID = p.Ps_ID
);

INSERT INTO Auth_Accounts (Role, Emp_ID, Password_Hash)
SELECT 'Admin', e.Emp_ID, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'
FROM Employees e
WHERE NOT EXISTS (
    SELECT 1 FROM Auth_Accounts a WHERE a.Emp_ID = e.Emp_ID
);

-- Seed two paid/ticketed demo bookings only when the database has no bookings.
INSERT INTO Bookings (
    Booking_ID, PNR, Ps_ID, Flight_ID, Seat_No, Status, Fare_ID, Amount, Created_At, Confirmed_At
)
SELECT 1, 'DEMOA1', 1, f.Flight_ID, '12A', 'Ticketed', f.Fare_ID, af.Charge_Amount, datetime('now'), datetime('now')
FROM Flight f
JOIN AirFare af ON af.Fare_ID = f.Fare_ID
WHERE f.Flight_ID = 1
  AND NOT EXISTS (SELECT 1 FROM Bookings)
UNION ALL
SELECT 2, 'DEMOB2', 2, f.Flight_ID, '9C', 'Ticketed', f.Fare_ID, af.Charge_Amount, datetime('now'), datetime('now')
FROM Flight f
JOIN AirFare af ON af.Fare_ID = f.Fare_ID
WHERE f.Flight_ID = 2
  AND NOT EXISTS (SELECT 1 FROM Bookings);

INSERT INTO Payments (Payment_ID, Booking_ID, Payment_Type, Amount, Status, Paid_At)
SELECT 1, b.Booking_ID, 'Card', b.Amount, 'Captured', datetime('now')
FROM Bookings b
WHERE b.PNR = 'DEMOA1'
  AND NOT EXISTS (SELECT 1 FROM Payments p WHERE p.Booking_ID = b.Booking_ID);

INSERT INTO Payments (Payment_ID, Booking_ID, Payment_Type, Amount, Status, Paid_At)
SELECT 2, b.Booking_ID, 'Online', b.Amount, 'Captured', datetime('now')
FROM Bookings b
WHERE b.PNR = 'DEMOB2'
  AND NOT EXISTS (SELECT 1 FROM Payments p WHERE p.Booking_ID = b.Booking_ID);

INSERT INTO Tickets (Ticket_ID, Booking_ID, Ticket_No, Issued_At)
SELECT 1, b.Booking_ID, '1000000000001', datetime('now')
FROM Bookings b
WHERE b.PNR = 'DEMOA1'
  AND NOT EXISTS (SELECT 1 FROM Tickets t WHERE t.Booking_ID = b.Booking_ID);

INSERT INTO Tickets (Ticket_ID, Booking_ID, Ticket_No, Issued_At)
SELECT 2, b.Booking_ID, '1000000000002', datetime('now')
FROM Bookings b
WHERE b.PNR = 'DEMOB2'
  AND NOT EXISTS (SELECT 1 FROM Tickets t WHERE t.Booking_ID = b.Booking_ID);

INSERT INTO Transactions (
    TS_ID, Booking_ID, Booking_Date, Departure_Date, Type, Emp_ID, Ps_ID, Flight_ID, Charge_Amount
)
SELECT 1, b.Booking_ID, date('now'), f.Flight_date, 'Card', 1, b.Ps_ID, b.Flight_ID, b.Amount
FROM Bookings b
JOIN Flight f ON f.Flight_ID = b.Flight_ID
WHERE b.PNR = 'DEMOA1'
  AND NOT EXISTS (SELECT 1 FROM Transactions t WHERE t.Booking_ID = b.Booking_ID);

INSERT INTO Transactions (
    TS_ID, Booking_ID, Booking_Date, Departure_Date, Type, Emp_ID, Ps_ID, Flight_ID, Charge_Amount
)
SELECT 2, b.Booking_ID, date('now'), f.Flight_date, 'Online', 1, b.Ps_ID, b.Flight_ID, b.Amount
FROM Bookings b
JOIN Flight f ON f.Flight_ID = b.Flight_ID
WHERE b.PNR = 'DEMOB2'
  AND NOT EXISTS (SELECT 1 FROM Transactions t WHERE t.Booking_ID = b.Booking_ID);

COMMIT;
