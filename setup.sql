PRAGMA foreign_keys = ON;

-- =====================================================
-- SIMPLE MODEL  (raporlama için: users, flights)
-- NOT: reservation_requests tablosu KALDIRILDI.
--      Uygulama ER katmanındaki Reservation_Requests
--      tablosunu kullandığından çakışma engellendi.
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('Passenger', 'Admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flights (
    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_no TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    flight_date TEXT NOT NULL,
    flight_time TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0)
);

-- Simple model seed data (raporlama / demo amacıyla tutuldu)
INSERT OR IGNORE INTO users (user_id, full_name, email, role) VALUES
    (1, 'Buse Yilmaz', 'buse.yilmaz@demo.local', 'Passenger'),
    (2, 'Mert Kaya', 'mert.kaya@demo.local', 'Passenger'),
    (3, 'Aylin Demir', 'aylin.demir@demo.local', 'Passenger'),
    (10, 'Admin User', 'admin@demo.local', 'Admin');

INSERT OR IGNORE INTO flights (flight_id, flight_no, origin, destination, flight_date, flight_time, capacity) VALUES
    (1, 'TK100', 'Istanbul', 'Ankara',    '2026-07-15', '09:30', 120),
    (2, 'TK204', 'Izmir',    'Antalya',   '2026-07-15', '13:10', 150),
    (3, 'TK311', 'Istanbul', 'Trabzon',   '2026-07-18', '18:20', 110),
    (4, 'TK420', 'Bursa',    'Adana',     '2026-07-20', '08:45',  90),
    (5, 'TK512', 'Gaziantep','Istanbul',  '2026-07-22', '16:00', 130);

-- =====================================================
-- ER-DIAGRAM COMPATIBILITY LAYER
-- (Uygulamanın tüm işlemleri bu tablolar üzerinden yürür)
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
    Charge_Amount REAL NOT NULL UNIQUE CHECK (Charge_Amount >= 0),
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

CREATE TABLE IF NOT EXISTS Transactions (
    TS_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Booking_Date TEXT NOT NULL,
    Departure_Date TEXT NOT NULL,
    Type TEXT NOT NULL CHECK (Type IN ('Card', 'Cash', 'Transfer', 'Online', 'Google Pay', 'Paytm', 'PhonePe', 'Credit Card')),
    Emp_ID INTEGER NOT NULL,
    Ps_ID INTEGER NOT NULL,
    Flight_ID INTEGER NOT NULL,
    Charge_Amount REAL NOT NULL,
    FOREIGN KEY (Emp_ID) REFERENCES Employees(Emp_ID) ON DELETE RESTRICT,
    FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE RESTRICT,
    FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE RESTRICT,
    FOREIGN KEY (Charge_Amount) REFERENCES AirFare(Charge_Amount) ON DELETE RESTRICT
);

-- =====================================================
-- Reservation_Requests (ER katmanı - Ana tablo)
-- DÜZELTME: simple modeldeki reservation_requests
-- kaldırıldığı için artık bu tablo çakışmıyor.
-- =====================================================
CREATE TABLE IF NOT EXISTS Reservation_Requests (
    Request_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Ps_ID INTEGER NOT NULL,
    Flight_ID INTEGER NOT NULL,
    Seat_No TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'Pending'
        CHECK (Status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')),
    Note TEXT,
    Reviewed_By_Emp_ID INTEGER,
    Created_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Decided_At TEXT,
    FOREIGN KEY (Ps_ID) REFERENCES Passengers(Ps_ID) ON DELETE CASCADE,
    FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE CASCADE,
    FOREIGN KEY (Reviewed_By_Emp_ID) REFERENCES Employees(Emp_ID) ON DELETE SET NULL
);

-- Trigger: aynı uçuşta aynı koltuk çakışmasını önle
CREATE TRIGGER IF NOT EXISTS trg_er_seat_conflict
BEFORE INSERT ON Reservation_Requests
WHEN NEW.Status IN ('Pending', 'Approved')
AND EXISTS (
    SELECT 1 FROM Reservation_Requests
    WHERE Flight_ID = NEW.Flight_ID
      AND Seat_No = NEW.Seat_No
      AND Status IN ('Pending', 'Approved')
)
BEGIN
    SELECT RAISE(ABORT, 'This seat is already reserved for this flight');
END;

-- Trigger: uçuş kapasitesi kontrolü
CREATE TRIGGER IF NOT EXISTS trg_er_capacity_check
BEFORE INSERT ON Reservation_Requests
WHEN NEW.Status IN ('Pending', 'Approved')
AND (
    SELECT COUNT(*) FROM Reservation_Requests
    WHERE Flight_ID = NEW.Flight_ID AND Status IN ('Pending', 'Approved')
) >= (
    SELECT at.Capacity FROM Flight f
    JOIN Airplane_type at ON at.A_ID = f.A_ID
    WHERE f.Flight_ID = NEW.Flight_ID
)
BEGIN
    SELECT RAISE(ABORT, 'Flight capacity is full');
END;

CREATE TABLE IF NOT EXISTS Can_Land (
    Air_Code TEXT NOT NULL,
    Flight_ID INTEGER NOT NULL,
    PRIMARY KEY (Air_Code, Flight_ID),
    FOREIGN KEY (Air_Code) REFERENCES Airport(Air_Code) ON DELETE CASCADE,
    FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Travels_on (
    Route_ID INTEGER NOT NULL,
    Flight_ID INTEGER NOT NULL,
    PRIMARY KEY (Route_ID, Flight_ID),
    FOREIGN KEY (Route_ID) REFERENCES Route(Route_ID) ON DELETE CASCADE,
    FOREIGN KEY (Flight_ID) REFERENCES Flight(Flight_ID) ON DELETE CASCADE
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_ps  ON Auth_Accounts(Ps_ID) WHERE Ps_ID IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_emp ON Auth_Accounts(Emp_ID) WHERE Emp_ID IS NOT NULL;

-- ER transaction rapor view'ı
CREATE VIEW IF NOT EXISTS v_er_transaction_report AS
SELECT
    t.TS_ID,
    t.Booking_Date,
    t.Departure_Date,
    t.Type,
    p.Name AS Passenger_Name,
    e.Name AS Employee_Name,
    f.Flight_ID,
    r.Take_Off_point,
    r.Destination,
    af.Charge_Amount
FROM Transactions t
JOIN Passengers p  ON p.Ps_ID     = t.Ps_ID
JOIN Employees e   ON e.Emp_ID    = t.Emp_ID
JOIN Flight f      ON f.Flight_ID = t.Flight_ID
JOIN Route r       ON r.Route_ID  = f.Route_ID
JOIN AirFare af    ON af.Fare_ID  = f.Fare_ID;

-- Trigger: hareket tarihi booking'den önce olamaz
CREATE TRIGGER IF NOT EXISTS trg_ts_departure_after_booking
BEFORE INSERT ON Transactions
WHEN date(NEW.Departure_Date) < date(NEW.Booking_Date)
BEGIN
    SELECT RAISE(ABORT, 'Departure date cannot be earlier than booking date');
END;

-- =====================================================
-- SEED DATA — ER Layer
-- =====================================================

INSERT OR IGNORE INTO Countries (Country_code, Country_Name) VALUES
    ('TR', 'Turkiye'),
    ('DE', 'Germany');

INSERT OR IGNORE INTO Airport (Air_Code, Air_Name, City, State, Country_code) VALUES
    ('IST', 'Istanbul Airport',      'Istanbul', 'Marmara',         'TR'),
    ('ESB', 'Esenboga Airport',      'Ankara',   'Central Anatolia','TR'),
    ('ADB', 'Adnan Menderes Airport','Izmir',    'Aegean',          'TR'),
    ('AYT', 'Antalya Airport',       'Antalya',  'Mediterranean',   'TR');

INSERT OR IGNORE INTO Airplane_type (A_ID, Capacity, A_weight, Company) VALUES
    (1, 180, 73500, 'Airbus'),
    (2, 160, 70500, 'Boeing');

INSERT OR IGNORE INTO Route (Route_ID, Destination, Take_Off_point, R_type) VALUES
    (1, 'ESB', 'IST', 'Domestic'),
    (2, 'AYT', 'ADB', 'Domestic');

INSERT OR IGNORE INTO AirFare (Fare_ID, Charge_Amount, Description) VALUES
    (1, 1499.90, 'Economy Base Fare'),
    (2, 2399.50, 'Flexible Fare');

-- Gelecek tarihli uçuşlar (2026-07)
INSERT OR IGNORE INTO Flight (Flight_ID, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID) VALUES
    (1, '09:00', '10:10', '2026-07-15', 1, 1, 1),
    (2, '14:00', '15:20', '2026-07-15', 2, 2, 2);

INSERT OR IGNORE INTO Passengers (Ps_ID, Name, Address, Age, Sex, Contacts) VALUES
    (1, 'Buse Yilmaz', 'Istanbul', 22, 'F', '+90-555-010-1010'),
    (2, 'Mert Kaya',   'Izmir',    24, 'M', '+90-555-020-2020');

INSERT OR IGNORE INTO Employees (Emp_ID, Name, Address, Age, Email_ID, Contacts) VALUES
    (1, 'Ayse Yilmaz', 'Istanbul', 31, 'ayse.employee@demo.local', '+90-555-111-2233'),
    (2, 'Can Kaya',    'Ankara',   29, 'can.employee@demo.local',  '+90-555-444-5566');

INSERT OR IGNORE INTO Transactions (
    TS_ID, Booking_Date, Departure_Date, Type, Emp_ID, Ps_ID, Flight_ID, Charge_Amount
) VALUES
    (1, '2026-06-20', '2026-07-15', 'Card',   1, 1, 1, 1499.90),
    (2, '2026-06-20', '2026-07-15', 'Online', 2, 2, 2, 2399.50);

-- Reservation_Requests seed (ER katmanı)
INSERT OR IGNORE INTO Reservation_Requests
    (Request_ID, Ps_ID, Flight_ID, Seat_No, Status, Note, Reviewed_By_Emp_ID, Created_At, Decided_At)
VALUES
    (1, 1, 1, '12A', 'Approved', 'Window seat preferred', 1, '2026-06-18 10:00:00', '2026-06-18 10:15:00'),
    (2, 2, 2, '09C', 'Pending',  'Needs extra baggage',  NULL,'2026-06-18 11:20:00', NULL);

-- Default seed şifresi: 1234
-- SHA256("1234") = 03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
INSERT OR IGNORE INTO Auth_Accounts (Role, Ps_ID, Password_Hash) VALUES
    ('Passenger', 1, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'),
    ('Passenger', 2, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4');

INSERT OR IGNORE INTO Auth_Accounts (Role, Emp_ID, Password_Hash) VALUES
    ('Admin', 1, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'),
    ('Admin', 2, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4');

-- =====================================================
-- LEGACY MINIPROJECT DATASET
-- (Orijinal akademik veri seti, tarihler güncellendi)
-- =====================================================

INSERT OR IGNORE INTO Airplane_type (A_ID, Capacity, A_weight, Company) VALUES
    (738, 853, 394, 'Indigo'),
    (777, 800, 380, 'Vistara'),
    (750, 790, 364, 'AirIndia'),
    (790, 850, 390, 'SpiceJet'),
    (745, 770, 405, 'GoAir'),
    (768, 867, 387, 'AirAsia'),
    (821, 790, 355, 'TruJet'),
    (785, 835, 410, 'Alliance Air');

INSERT OR IGNORE INTO Countries (Country_code, Country_Name) VALUES
    ('+44', 'England'),
    ('+1',  'USA'),
    ('+91', 'India'),
    ('+45', 'Kingdom of Denmark'),
    ('+64', 'New Zealand'),
    ('+971','UAE'),
    ('+213','Algeria'),
    ('+55', 'Brazil');

INSERT OR IGNORE INTO Airport (Air_Code, Air_Name, City, State, Country_code) VALUES
    ('DEL', 'Indira Gandhi International Airport',             'Delhi',        'UP',         '+91'),
    ('BOM', 'Chhatrapati Shivaji Maharaj International Airport','Mumbai',      'Maharashtra','+91'),
    ('LCY', 'London City Airport',                             'Newham',       'London',     '+44'),
    ('EWR', 'Newark Liberty International Airport',            'Newark',       'New Jersey', '+1'),
    ('JFK', 'John F. Kennedy International Airport',           'New York City','New York',   '+1'),
    ('CPH', 'Copenhagen Airport',                              'Copenhagen',   'Denmark',    '+45'),
    ('AIP', 'Adampur Airport',                                 'Jalandhar',    'Punjab',     '+91'),
    ('IXJ', 'Satwari Airport',                                 'Jammu',        'Jammu & Kashmir','+91');

INSERT OR IGNORE INTO Route (Route_ID, Destination, Take_Off_point, R_type) VALUES
    (168806, 'LCY', 'DEL', 'Direct'),
    (157306, 'EWR', 'BOM', '2Hr Break'),
    (178916, 'JFK', 'AIP', '3Hr Break'),
    (324567, 'CPH', 'BOM', 'Direct'),
    (452368, 'JFK', 'AIP', '3Hr Break'),
    (894521, 'DEL', 'AIP', 'Direct'),
    (578425, 'AIP', 'CPH', 'Direct'),
    (421523, 'IXJ', 'DEL', 'Direct');

INSERT OR IGNORE INTO AirFare (Fare_ID, Charge_Amount, Description) VALUES
    (101, 27341, 'Standard Single'),
    (102, 34837, 'Standard Return'),
    (103, 42176, 'Key Fare Single'),
    (104, 27373, 'Business Return'),
    (105, 44592, 'Advanced Purchase'),
    (106,  8777, 'Superpex Return'),
    (107,  9578, 'Standard Return'),
    (108,  4459, 'Superpex Return');

-- Legacy uçuşlar: tarihler 2026-08 ve sonrasına taşındı
INSERT OR IGNORE INTO Flight (Flight_ID, Flight_No, Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID) VALUES
    (2014, 'AI2014', '08:45', '22:25', '2026-08-12', 168806, 738, 101),
    (2305, 'QR2305', '12:05', '00:25', '2026-08-26', 157306, 777, 102),
    (1234, 'EY1234', '05:00', '22:30', '2026-09-10', 178916, 750, 103),
    (9876, 'LH9876', '10:15', '23:00', '2026-09-25', 324567, 790, 104),
    (1689, 'BA1689', '02:15', '22:00', '2026-10-02', 452368, 745, 105),
    (4367, 'AA4367', '00:05', '02:15', '2026-10-25', 894521, 768, 106),
    (7812, 'CT7812', '14:15', '20:00', '2026-11-04', 578425, 821, 107),
    (4521, 'PF4521', '17:00', '22:30', '2026-11-25', 421523, 785, 108);

INSERT OR IGNORE INTO Passengers (Ps_ID, Name, Address, Age, Sex, Contacts) VALUES
    (3,  'Steve Smith',    '2230 Northside, Apt 11, London',              30, 'M', '8080367290'),
    (4,  'Ankita Ahir',    '3456 Vikas Apts, Apt 102, New Jersey',        26, 'F', '8080367280'),
    (5,  'Akhilesh Joshi', '345 Chatam courts, Apt 678, Chennai',         29, 'M', '9080369290'),
    (6,  'Khyati Mishra',  '7820 Mccallum courts, Apt 234, Washington',   30, 'F', '8082267280'),
    (7,  'Rom Solanki',    '1234 Baker Apts, Apt 208, Chandigarh',         60, 'M', '9004568903'),
    (8,  'Lakshmi Sharma', '1110 Fir hills, Apt 90, Daman',               30, 'F', '7666190505'),
    (9,  'Manan Lakhani',  '7720 Mccallum Blvd, Apt 77, Beijing',         45, 'M', '8124579635'),
    (10, 'Ria Gupta',      'B-402, Aditya Apt, Hyderabad',                34, 'F', '9819414036');

INSERT OR IGNORE INTO Employees (Emp_ID, Name, Address, Age, Email_ID, Contacts, Air_Code) VALUES
    (1234, 'Rekha Tiwary',  '202-Meeta Apt, Yogi Nagar, Mumbai',         30, 'rekha1234@gmail.com', '+918530324018','DEL'),
    (3246, 'John Dsouza',   '302-Fountain Apt, Elizabeth Street, Newham',26, 'john2346@gmail.com',  '+447911123456','BOM'),
    (9321, 'Sanjay Rathod', '62-Patwa Apt, Pradeep Nagar, Delhi',        36, 'sanjay78@gmail.com',  '+917504681201','LCY'),
    (8512, 'Hafsa Iqmar',   '1023-Prajwal Apt, Newark',                  41, 'hafsa964@gmail.com',  '6465554468',  'EWR'),
    (7512, 'Akshay Sharma', 'Akshay Villa, Queens Street, Copenhagen',   20, 'akshay27@gmail.com',  '+45886443210','JFK'),
    (5123, 'Lara Jen',      '28-Mark road, Victoria street, New York City',31,'jenlara4@gmail.com', '+448000751234','CPH'),
    (2458, 'Johny Paul',    '45-Balaji Apt, Ajit Nagar, Jalandhar',      32, 'johnypaul8@gmail.com','+919785425154','AIP'),
    (4521, 'Nidhi Maroliya','6-Matruchaya Apt, Park Road, Jammu',        31, 'nidhi785@gmail.com',  '+918211954901','IXJ');