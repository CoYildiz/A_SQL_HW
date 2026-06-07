PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- =====================================================
-- Airline Management System SQLite setup
-- Compatible with the uploaded app.py
--
-- No external SQL plugin/extension is required.
-- This script resets the demo database schema and seeds
-- more passengers/admins/flights/bookings for testing.
-- Paid add-ons such as extra baggage are selected during booking
-- and are added to ticket/payment/transaction totals immediately.
--
-- Default password for every seeded account: 1234
-- SHA256("1234") = 03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
-- =====================================================

DROP VIEW IF EXISTS v_booking_overview;

DROP TRIGGER IF EXISTS trg_booking_seat_conflict;
DROP TRIGGER IF EXISTS trg_booking_capacity_check;
DROP TRIGGER IF EXISTS trg_booking_seat_conflict_update;
DROP TRIGGER IF EXISTS trg_ts_departure_after_booking;

DROP TABLE IF EXISTS Special_Requests;
DROP TABLE IF EXISTS Transactions;
DROP TABLE IF EXISTS Tickets;
DROP TABLE IF EXISTS Payments;
DROP TABLE IF EXISTS Booking_Addons;
DROP TABLE IF EXISTS Bookings;
DROP TABLE IF EXISTS Addon_Catalog;
DROP TABLE IF EXISTS Auth_Accounts;
DROP TABLE IF EXISTS Employees;
DROP TABLE IF EXISTS Passengers;
DROP TABLE IF EXISTS Flight;
DROP TABLE IF EXISTS AirFare;
DROP TABLE IF EXISTS Route;
DROP TABLE IF EXISTS Airplane_type;
DROP TABLE IF EXISTS Airport;
DROP TABLE IF EXISTS Countries;

-- Old/simple-model tables from previous setup versions.
DROP VIEW IF EXISTS v_request_overview;
DROP VIEW IF EXISTS v_flight_summary;
DROP TRIGGER IF EXISTS trg_request_seat_conflict;
DROP TRIGGER IF EXISTS trg_request_capacity_check;
DROP TABLE IF EXISTS reservation_requests;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS users;

PRAGMA foreign_keys = ON;

CREATE TABLE Countries (
    Country_code TEXT PRIMARY KEY,
    Country_Name TEXT NOT NULL UNIQUE
);

CREATE TABLE Airport (
    Air_Code TEXT PRIMARY KEY,
    Air_Name TEXT NOT NULL,
    City TEXT NOT NULL,
    State TEXT,
    Country_code TEXT NOT NULL,
    FOREIGN KEY (Country_code) REFERENCES Countries(Country_code) ON DELETE RESTRICT
);

CREATE TABLE Airplane_type (
    A_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Capacity INTEGER NOT NULL CHECK (Capacity > 0),
    A_weight REAL,
    Company TEXT NOT NULL
);

CREATE TABLE Route (
    Route_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Destination TEXT NOT NULL,
    Take_Off_point TEXT NOT NULL,
    R_type TEXT NOT NULL,
    FOREIGN KEY (Destination) REFERENCES Airport(Air_Code) ON DELETE RESTRICT,
    FOREIGN KEY (Take_Off_point) REFERENCES Airport(Air_Code) ON DELETE RESTRICT,
    CHECK (Destination <> Take_Off_point)
);

CREATE TABLE AirFare (
    Fare_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Charge_Amount REAL NOT NULL CHECK (Charge_Amount >= 0),
    Description TEXT
);

CREATE TABLE Flight (
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

CREATE TABLE Passengers (
    Ps_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Address TEXT,
    Age INTEGER CHECK (Age >= 0),
    Sex TEXT,
    Contacts TEXT
);

CREATE TABLE Employees (
    Emp_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Address TEXT,
    Age INTEGER CHECK (Age >= 18),
    Email_ID TEXT UNIQUE,
    Contacts TEXT,
    Air_Code TEXT,
    FOREIGN KEY (Air_Code) REFERENCES Airport(Air_Code) ON DELETE SET NULL
);

CREATE TABLE Auth_Accounts (
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

CREATE UNIQUE INDEX idx_auth_ps
ON Auth_Accounts(Ps_ID)
WHERE Ps_ID IS NOT NULL;

CREATE UNIQUE INDEX idx_auth_emp
ON Auth_Accounts(Emp_ID)
WHERE Emp_ID IS NOT NULL;

CREATE TABLE Addon_Catalog (
    Addon_Code TEXT PRIMARY KEY,
    Addon_Name TEXT NOT NULL UNIQUE,
    Price REAL NOT NULL CHECK (Price >= 0),
    Is_Active INTEGER NOT NULL DEFAULT 1 CHECK (Is_Active IN (0, 1))
);

CREATE TABLE Bookings (
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

CREATE TABLE Booking_Addons (
    Booking_Addon_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_ID INTEGER NOT NULL,
    Addon_Code TEXT NOT NULL,
    Price_At_Booking REAL NOT NULL CHECK (Price_At_Booking >= 0),
    FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE,
    FOREIGN KEY (Addon_Code) REFERENCES Addon_Catalog(Addon_Code) ON DELETE RESTRICT,
    UNIQUE (Booking_ID, Addon_Code)
);

CREATE TABLE Payments (
    Payment_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_ID INTEGER NOT NULL,
    Payment_Type TEXT NOT NULL CHECK (Payment_Type IN ('Card','Cash','Transfer','Online','Google Pay','Credit Card')),
    Amount REAL NOT NULL CHECK (Amount >= 0),
    Status TEXT NOT NULL CHECK (Status IN ('Authorized','Captured','Failed','Refunded')),
    Paid_At TEXT,
    FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE
);

CREATE TABLE Tickets (
    Ticket_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_ID INTEGER NOT NULL UNIQUE,
    Ticket_No TEXT NOT NULL UNIQUE,
    Issued_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Booking_ID) REFERENCES Bookings(Booking_ID) ON DELETE CASCADE
);

CREATE TABLE Transactions (
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

CREATE TABLE Special_Requests (
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

-- =====================================================
-- Seed data
-- =====================================================

INSERT INTO Countries (Country_code, Country_Name) VALUES
    ('TR', 'Turkiye'),
    ('DE', 'Germany'),
    ('GB', 'United Kingdom'),
    ('US', 'United States'),
    ('FR', 'France'),
    ('NL', 'Netherlands'),
    ('IT', 'Italy');

INSERT INTO Airport (Air_Code, Air_Name, City, State, Country_code) VALUES
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

INSERT INTO Airplane_type (A_ID, Capacity, A_weight, Company) VALUES
    (1, 180, 73500, 'Airbus A320'),
    (2, 160, 70500, 'Boeing 737'),
    (3, 260, 125000, 'Airbus A330'),
    (4, 300, 145000, 'Boeing 777'),
    (5, 220, 98000, 'Airbus A321neo'),
    (6, 280, 138000, 'Boeing 787');

INSERT INTO Route (Route_ID, Destination, Take_Off_point, R_type) VALUES
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

INSERT INTO AirFare (Fare_ID, Charge_Amount, Description) VALUES
    (1, 1499.90, 'Economy Base Fare'),
    (2, 2399.50, 'Flexible Fare'),
    (3, 3499.00, 'Domestic Business'),
    (4, 12999.00, 'International Economy'),
    (5, 24999.00, 'International Business'),
    (6, 6999.00, 'Promo International'),
    (7, 4999.00, 'Premium Domestic');

INSERT INTO Addon_Catalog (Addon_Code, Addon_Name, Price, Is_Active) VALUES
    ('BAG10', 'Extra Baggage 10 kg', 650.00, 1),
    ('BAG20', 'Extra Baggage 20 kg', 1150.00, 1),
    ('PETCABIN', 'Pet in Cabin', 900.00, 1);

INSERT INTO Flight (Flight_ID, Flight_No, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID) VALUES
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

INSERT INTO Passengers (Ps_ID, Name, Address, Age, Sex, Contacts) VALUES
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

INSERT INTO Employees (Emp_ID, Name, Address, Age, Email_ID, Contacts, Air_Code) VALUES
    (1, 'Online Sales System', 'Istanbul', 30, 'online.sales@demo.local', '+90-555-000-0001', 'IST');

INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash)
SELECT 'Passenger', Ps_ID, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'
FROM Passengers;

INSERT INTO Auth_Accounts (Role, Emp_ID, Password_Hash)
SELECT 'Admin', Emp_ID, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'
FROM Employees
WHERE Emp_ID = 1;

INSERT INTO Bookings (
    Booking_ID, PNR, Ps_ID, Flight_ID, Seat_No, Status, Fare_ID, Amount, Created_At, Confirmed_At, Cancelled_At, Refunded_At
) VALUES
    (1, 'DEMOA1', 1, 1, '12A', 'Ticketed', 1, 2149.90, datetime('now', '-10 days'), datetime('now', '-10 days'), NULL, NULL),
    (2, 'DEMOB2', 2, 2, '9C', 'Ticketed', 2, 2399.50, datetime('now', '-9 days'), datetime('now', '-9 days'), NULL, NULL),
    (3, 'DEMOC3', 3, 3, '7B', 'Ticketed', 1, 2649.90, datetime('now', '-8 days'), datetime('now', '-8 days'), NULL, NULL),
    (4, 'DEMOD4', 4, 4, '14D', 'Ticketed', 2, 2399.50, datetime('now', '-7 days'), datetime('now', '-7 days'), NULL, NULL),
    (5, 'DEMOE5', 5, 5, '3A', 'Ticketed', 3, 4399.00, datetime('now', '-7 days'), datetime('now', '-7 days'), NULL, NULL),
    (6, 'DEMOF6', 6, 6, '18F', 'Ticketed', 1, 1499.90, datetime('now', '-6 days'), datetime('now', '-6 days'), NULL, NULL),
    (7, 'DEMOG7', 7, 7, '21C', 'Ticketed', 4, 13649.00, datetime('now', '-6 days'), datetime('now', '-6 days'), NULL, NULL),
    (8, 'DEMOH8', 8, 8, '5D', 'Ticketed', 5, 26149.00, datetime('now', '-5 days'), datetime('now', '-5 days'), NULL, NULL),
    (9, 'DEMOI9', 9, 9, '10A', 'Ticketed', 6, 6999.00, datetime('now', '-5 days'), datetime('now', '-5 days'), NULL, NULL),
    (10, 'DEMOJ10', 10, 10, '11B', 'Ticketed', 6, 6999.00, datetime('now', '-4 days'), datetime('now', '-4 days'), NULL, NULL),
    (11, 'DEMOK11', 11, 11, '2C', 'Ticketed', 4, 13649.00, datetime('now', '-4 days'), datetime('now', '-4 days'), NULL, NULL),
    (12, 'DEMOL12', 12, 12, '16E', 'Ticketed', 6, 6999.00, datetime('now', '-3 days'), datetime('now', '-3 days'), NULL, NULL),
    (13, 'DEMOM13', 13, 13, '8A', 'Ticketed', 5, 25899.00, datetime('now', '-3 days'), datetime('now', '-3 days'), NULL, NULL),
    (14, 'DEMON14', 14, 14, '22F', 'Ticketed', 4, 14149.00, datetime('now', '-2 days'), datetime('now', '-2 days'), NULL, NULL),
    (15, 'DEMOO15', 15, 15, '6A', 'Cancelled', 1, 1499.90, datetime('now', '-12 days'), datetime('now', '-12 days'), datetime('now', '-1 days'), NULL),
    (16, 'DEMOP16', 16, 16, '4C', 'Refunded', 2, 2399.50, datetime('now', '-11 days'), datetime('now', '-11 days'), NULL, datetime('now', '-1 days')),
    (17, 'DEMOQ17', 17, 17, '13D', 'Confirmed', 3, 4149.00, datetime('now', '-2 days'), datetime('now', '-2 days'), NULL, NULL),
    (18, 'DEMOR18', 18, 18, '15B', 'PendingPayment', 7, 4999.00, datetime('now', '-1 days'), NULL, NULL, NULL),
    (19, 'DEMOS19', 19, 1, '12B', 'Ticketed', 1, 1499.90, datetime('now', '-1 days'), datetime('now', '-1 days'), NULL, NULL),
    (20, 'DEMOT20', 20, 2, '10A', 'Ticketed', 2, 3049.50, datetime('now', '-1 days'), datetime('now', '-1 days'), NULL, NULL);

INSERT INTO Booking_Addons (Booking_ID, Addon_Code, Price_At_Booking) VALUES
    (1, 'BAG10', 650.00),
    (3, 'BAG20', 1150.00),
    (5, 'PETCABIN', 900.00),
    (7, 'BAG10', 650.00),
    (8, 'BAG20', 1150.00),
    (11, 'BAG10', 650.00),
    (13, 'PETCABIN', 900.00),
    (14, 'BAG20', 1150.00),
    (17, 'BAG10', 650.00),
    (20, 'BAG10', 650.00);

INSERT INTO Payments (Payment_ID, Booking_ID, Payment_Type, Amount, Status, Paid_At) VALUES
    (1, 1, 'Card', 2149.90, 'Captured', datetime('now', '-10 days')),
    (2, 2, 'Online', 2399.50, 'Captured', datetime('now', '-9 days')),
    (3, 3, 'Credit Card', 2649.90, 'Captured', datetime('now', '-8 days')),
    (4, 4, 'Transfer', 2399.50, 'Captured', datetime('now', '-7 days')),
    (5, 5, 'Card', 4399.00, 'Captured', datetime('now', '-7 days')),
    (6, 6, 'Cash', 1499.90, 'Captured', datetime('now', '-6 days')),
    (7, 7, 'Google Pay', 13649.00, 'Captured', datetime('now', '-6 days')),
    (8, 8, 'Credit Card', 26149.00, 'Captured', datetime('now', '-5 days')),
    (9, 9, 'Online', 6999.00, 'Captured', datetime('now', '-5 days')),
    (10, 10, 'Card', 6999.00, 'Captured', datetime('now', '-4 days')),
    (11, 11, 'Transfer', 13649.00, 'Captured', datetime('now', '-4 days')),
    (12, 12, 'Online', 6999.00, 'Captured', datetime('now', '-3 days')),
    (13, 13, 'Credit Card', 25899.00, 'Captured', datetime('now', '-3 days')),
    (14, 14, 'Card', 14149.00, 'Captured', datetime('now', '-2 days')),
    (15, 15, 'Card', 1499.90, 'Captured', datetime('now', '-12 days')),
    (16, 16, 'Online', 2399.50, 'Refunded', datetime('now', '-11 days')),
    (17, 17, 'Cash', 4149.00, 'Captured', datetime('now', '-2 days')),
    (18, 19, 'Card', 1499.90, 'Captured', datetime('now', '-1 days')),
    (19, 20, 'Online', 3049.50, 'Captured', datetime('now', '-1 days'));

INSERT INTO Tickets (Ticket_ID, Booking_ID, Ticket_No, Issued_At) VALUES
    (1, 1, '1000000000001', datetime('now', '-10 days')),
    (2, 2, '1000000000002', datetime('now', '-9 days')),
    (3, 3, '1000000000003', datetime('now', '-8 days')),
    (4, 4, '1000000000004', datetime('now', '-7 days')),
    (5, 5, '1000000000005', datetime('now', '-7 days')),
    (6, 6, '1000000000006', datetime('now', '-6 days')),
    (7, 7, '1000000000007', datetime('now', '-6 days')),
    (8, 8, '1000000000008', datetime('now', '-5 days')),
    (9, 9, '1000000000009', datetime('now', '-5 days')),
    (10, 10, '1000000000010', datetime('now', '-4 days')),
    (11, 11, '1000000000011', datetime('now', '-4 days')),
    (12, 12, '1000000000012', datetime('now', '-3 days')),
    (13, 13, '1000000000013', datetime('now', '-3 days')),
    (14, 14, '1000000000014', datetime('now', '-2 days')),
    (15, 15, '1000000000015', datetime('now', '-12 days')),
    (16, 16, '1000000000016', datetime('now', '-11 days')),
    (17, 17, '1000000000017', datetime('now', '-2 days')),
    (18, 19, '1000000000019', datetime('now', '-1 days')),
    (19, 20, '1000000000020', datetime('now', '-1 days'));

INSERT INTO Transactions (
    TS_ID, Booking_ID, Booking_Date, Departure_Date, Type, Emp_ID, Ps_ID, Flight_ID, Charge_Amount
) VALUES
    (1, 1, date('now', '-10 days'), date('now', '+30 days'), 'Card', 1, 1, 1, 2149.90),
    (2, 2, date('now', '-9 days'), date('now', '+31 days'), 'Online', 1, 2, 2, 2399.50),
    (3, 3, date('now', '-8 days'), date('now', '+34 days'), 'Credit Card', 1, 3, 3, 2649.90),
    (4, 4, date('now', '-7 days'), date('now', '+37 days'), 'Transfer', 1, 4, 4, 2399.50),
    (5, 5, date('now', '-7 days'), date('now', '+40 days'), 'Card', 1, 5, 5, 4399.00),
    (6, 6, date('now', '-6 days'), date('now', '+41 days'), 'Cash', 1, 6, 6, 1499.90),
    (7, 7, date('now', '-6 days'), date('now', '+45 days'), 'Google Pay', 1, 7, 7, 13649.00),
    (8, 8, date('now', '-5 days'), date('now', '+50 days'), 'Credit Card', 1, 8, 8, 26149.00),
    (9, 9, date('now', '-5 days'), date('now', '+52 days'), 'Online', 1, 9, 9, 6999.00),
    (10, 10, date('now', '-4 days'), date('now', '+54 days'), 'Card', 1, 10, 10, 6999.00),
    (11, 11, date('now', '-4 days'), date('now', '+56 days'), 'Transfer', 1, 11, 11, 13649.00),
    (12, 12, date('now', '-3 days'), date('now', '+58 days'), 'Online', 1, 12, 12, 6999.00),
    (13, 13, date('now', '-3 days'), date('now', '+60 days'), 'Credit Card', 1, 13, 13, 25899.00),
    (14, 14, date('now', '-2 days'), date('now', '+62 days'), 'Card', 1, 14, 14, 14149.00),
    (15, 15, date('now', '-12 days'), date('now', '+65 days'), 'Card', 1, 15, 15, 1499.90),
    (16, 16, date('now', '-11 days'), date('now', '+66 days'), 'Online', 1, 16, 16, 2399.50),
    (17, 17, date('now', '-2 days'), date('now', '+68 days'), 'Cash', 1, 17, 17, 4149.00),
    (18, 19, date('now', '-1 days'), date('now', '+30 days'), 'Card', 1, 19, 1, 1499.90),
    (19, 20, date('now', '-1 days'), date('now', '+31 days'), 'Online', 1, 20, 2, 3049.50);

INSERT INTO Special_Requests (
    Request_ID, Booking_ID, Ps_ID, Request_Type, Note, Status, Reviewed_By_Emp_ID, Created_At, Decided_At
) VALUES
    (1, 3, 3, 'Seat Change', 'Prefer window seat if available.', 'Rejected', 1, datetime('now', '-5 days'), datetime('now', '-4 days')),
    (2, 4, 4, 'Wheelchair Assistance', 'Assistance needed at boarding gate.', 'Pending', NULL, datetime('now', '-4 days'), NULL),
    (3, 8, 8, 'Refund Request', 'Travel plan changed.', 'Pending', NULL, datetime('now', '-3 days'), NULL),
    (4, 15, 15, 'Cancellation Request', 'Cancelled by passenger.', 'Approved', 1, datetime('now', '-2 days'), datetime('now', '-1 days')),
    (5, 16, 16, 'Refund Request', 'Refund completed.', 'Approved', 1, datetime('now', '-2 days'), datetime('now', '-1 days')),
    (6, NULL, 21, 'Other', 'Question about international baggage rules.', 'Pending', NULL, datetime('now'), NULL),
    (7, 2, 2, 'Meal Preference', 'Vegetarian meal preferred.', 'Pending', NULL, datetime('now'), NULL);

COMMIT;

PRAGMA foreign_keys = ON;
