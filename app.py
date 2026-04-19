from __future__ import annotations

import sqlite3
import hashlib
from datetime import date
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
SETUP_PATH = BASE_DIR / "setup.sql"


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


class Repository:
    def __init__(self) -> None:
        self.ensure_database()

    def ensure_database(self) -> None:
        needs_setup = not DB_PATH.exists()
        if not needs_setup:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Flight'"
                ).fetchone()
                needs_setup = row is None

        if needs_setup:
            script = SETUP_PATH.read_text(encoding="utf-8")
            with sqlite3.connect(DB_PATH) as conn:
                conn.executescript(script)

        self.ensure_auth_schema()

    def ensure_auth_schema(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
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
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_ps ON Auth_Accounts(Ps_ID) WHERE Ps_ID IS NOT NULL")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_emp ON Auth_Accounts(Emp_ID) WHERE Emp_ID IS NOT NULL")

            default_hash = hash_password("1234")
            conn.execute(
                """
                INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash)
                SELECT 'Passenger', p.Ps_ID, ?
                FROM Passengers p
                WHERE NOT EXISTS (SELECT 1 FROM Auth_Accounts a WHERE a.Ps_ID = p.Ps_ID)
                """,
                (default_hash,),
            )
            conn.execute(
                """
                INSERT INTO Auth_Accounts (Role, Emp_ID, Password_Hash)
                SELECT 'Admin', e.Emp_ID, ?
                FROM Employees e
                WHERE NOT EXISTS (SELECT 1 FROM Auth_Accounts a WHERE a.Emp_ID = e.Emp_ID)
                """,
                (default_hash,),
            )
            conn.commit()

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

    def passenger_options(self):
        return self.fetchall("SELECT Ps_ID, Name FROM Passengers ORDER BY Name")

    def admin_options(self):
        return self.fetchall("SELECT Emp_ID, Name FROM Employees ORDER BY Name")

    def validate_passenger_login(self, ps_id: int, raw_password: str) -> bool:
        row = self.fetchone(
            "SELECT Account_ID FROM Auth_Accounts WHERE Role = 'Passenger' AND Ps_ID = ? AND Password_Hash = ?",
            (ps_id, hash_password(raw_password)),
        )
        return row is not None

    def validate_admin_login(self, emp_id: int, raw_password: str) -> bool:
        row = self.fetchone(
            "SELECT Account_ID FROM Auth_Accounts WHERE Role = 'Admin' AND Emp_ID = ? AND Password_Hash = ?",
            (emp_id, hash_password(raw_password)),
        )
        return row is not None

    def create_passenger_account(self, name: str, address: str, age: int, sex: str, contacts: str, raw_password: str):
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO Passengers (Name, Address, Age, Sex, Contacts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, address, age, sex, contacts),
            )
            ps_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO Auth_Accounts (Role, Ps_ID, Password_Hash)
                VALUES ('Passenger', ?, ?)
                """,
                (ps_id, hash_password(raw_password)),
            )
            conn.commit()

    def list_routes(self):
        return self.fetchall("SELECT Route_ID, Take_Off_point, Destination, R_type FROM Route ORDER BY Route_ID")

    def list_airport_codes(self):
        return self.fetchall("SELECT Air_Code, Air_Name, City FROM Airport ORDER BY Air_Code")

    def list_countries(self):
        return self.fetchall("SELECT Country_code, Country_Name FROM Countries ORDER BY Country_code")

    def list_airports(self):
        return self.fetchall(
            """
            SELECT a.Air_Code, a.Air_Name, a.City, a.State, a.Country_code, c.Country_Name
            FROM Airport a
            JOIN Countries c ON c.Country_code = a.Country_code
            ORDER BY a.Air_Code
            """
        )

    def list_airplanes(self):
        return self.fetchall("SELECT A_ID, Company, Capacity, A_weight FROM Airplane_type ORDER BY A_ID")

    def list_airfares(self):
        return self.fetchall("SELECT Fare_ID, Charge_Amount, Description FROM AirFare ORDER BY Fare_ID")

    def add_route(self, destination: str, take_off_point: str, r_type: str):
        self.execute(
            """
            INSERT INTO Route (Destination, Take_Off_point, R_type)
            VALUES (?, ?, ?)
            """,
            (destination, take_off_point, r_type),
        )

    def update_route(self, route_id: int, destination: str, take_off_point: str, r_type: str):
        self.execute(
            """
            UPDATE Route
            SET Destination = ?, Take_Off_point = ?, R_type = ?
            WHERE Route_ID = ?
            """,
            (destination, take_off_point, r_type, route_id),
        )

    def delete_route(self, route_id: int):
        self.execute("DELETE FROM Route WHERE Route_ID = ?", (route_id,))

    def add_airplane(self, capacity: int, a_weight: float, company: str):
        self.execute(
            """
            INSERT INTO Airplane_type (Capacity, A_weight, Company)
            VALUES (?, ?, ?)
            """,
            (capacity, a_weight, company),
        )

    def update_airplane(self, a_id: int, capacity: int, a_weight: float, company: str):
        self.execute(
            """
            UPDATE Airplane_type
            SET Capacity = ?, A_weight = ?, Company = ?
            WHERE A_ID = ?
            """,
            (capacity, a_weight, company, a_id),
        )

    def delete_airplane(self, a_id: int):
        self.execute("DELETE FROM Airplane_type WHERE A_ID = ?", (a_id,))

    def add_airfare(self, charge_amount: float, description: str):
        self.execute(
            """
            INSERT INTO AirFare (Charge_Amount, Description)
            VALUES (?, ?)
            """,
            (charge_amount, description),
        )

    def update_airfare(self, fare_id: int, charge_amount: float, description: str):
        self.execute(
            """
            UPDATE AirFare
            SET Charge_Amount = ?, Description = ?
            WHERE Fare_ID = ?
            """,
            (charge_amount, description, fare_id),
        )

    def delete_airfare(self, fare_id: int):
        self.execute("DELETE FROM AirFare WHERE Fare_ID = ?", (fare_id,))

    def add_country(self, country_code: str, country_name: str):
        self.execute(
            "INSERT INTO Countries (Country_code, Country_Name) VALUES (?, ?)",
            (country_code, country_name),
        )

    def update_country(self, country_code: str, country_name: str):
        self.execute(
            "UPDATE Countries SET Country_Name = ? WHERE Country_code = ?",
            (country_name, country_code),
        )

    def delete_country(self, country_code: str):
        self.execute("DELETE FROM Countries WHERE Country_code = ?", (country_code,))

    def add_airport(self, air_code: str, air_name: str, city: str, state: str, country_code: str):
        self.execute(
            """
            INSERT INTO Airport (Air_Code, Air_Name, City, State, Country_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (air_code, air_name, city, state, country_code),
        )

    def update_airport(self, air_code: str, air_name: str, city: str, state: str, country_code: str):
        self.execute(
            """
            UPDATE Airport
            SET Air_Name = ?, City = ?, State = ?, Country_code = ?
            WHERE Air_Code = ?
            """,
            (air_name, city, state, country_code, air_code),
        )

    def delete_airport(self, air_code: str):
        self.execute("DELETE FROM Airport WHERE Air_Code = ?", (air_code,))

    def list_flights(self, keyword: str = "", flight_date: str = ""):
        conditions = ["1=1"]
        params: list[str] = []

        if keyword.strip():
            like = f"%{keyword.strip()}%"
            conditions.append("(r.Take_Off_point LIKE ? OR r.Destination LIKE ? OR at.Company LIKE ?)")
            params.extend([like, like, like])

        if flight_date.strip():
            conditions.append("f.Flight_date = ?")
            params.append(flight_date.strip())

        query = f"""
            SELECT
                f.Flight_ID,
                f.Departure,
                f.Arrival,
                f.Flight_date,
                r.Route_ID,
                r.Take_Off_point,
                r.Destination,
                r.R_type,
                at.A_ID,
                at.Company,
                at.Capacity,
                af.Fare_ID,
                af.Charge_Amount,
                COALESCE((
                    SELECT COUNT(*)
                    FROM Transactions t
                    WHERE t.Flight_ID = f.Flight_ID
                ), 0) AS Booked_Count
            FROM Flight f
            JOIN Route r ON r.Route_ID = f.Route_ID
            JOIN Airplane_type at ON at.A_ID = f.A_ID
            JOIN AirFare af ON af.Fare_ID = f.Fare_ID
            WHERE {' AND '.join(conditions)}
            ORDER BY f.Flight_date, f.Departure, f.Flight_ID
        """
        return self.fetchall(query, tuple(params))

    def add_flight(self, departure: str, arrival: str, flight_date: str, route_id: int, a_id: int, fare_id: int):
        self.execute(
            """
            INSERT INTO Flight (Departure, Arrival, Flight_date, Route_ID, A_ID, Fare_ID)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (departure, arrival, flight_date, route_id, a_id, fare_id),
        )

    def update_flight(self, flight_id: int, departure: str, arrival: str, flight_date: str, route_id: int, a_id: int, fare_id: int):
        self.execute(
            """
            UPDATE Flight
            SET Departure = ?, Arrival = ?, Flight_date = ?, Route_ID = ?, A_ID = ?, Fare_ID = ?
            WHERE Flight_ID = ?
            """,
            (departure, arrival, flight_date, route_id, a_id, fare_id, flight_id),
        )

    def delete_flight(self, flight_id: int):
        self.execute("DELETE FROM Flight WHERE Flight_ID = ?", (flight_id,))

    def flight_capacity_and_price(self, flight_id: int):
        return self.fetchone(
            """
            SELECT at.Capacity, af.Charge_Amount, f.Flight_date
            FROM Flight f
            JOIN Airplane_type at ON at.A_ID = f.A_ID
            JOIN AirFare af ON af.Fare_ID = f.Fare_ID
            WHERE f.Flight_ID = ?
            """,
            (flight_id,),
        )

    def bookings_for_flight(self, flight_id: int) -> int:
        row = self.fetchone("SELECT COUNT(*) AS total FROM Transactions WHERE Flight_ID = ?", (flight_id,))
        return int(row["total"]) if row else 0

    def create_booking(self, emp_id: int, ps_id: int, flight_id: int, payment_type: str):
        info = self.flight_capacity_and_price(flight_id)
        if info is None:
            raise ValueError("Flight not found.")

        if self.bookings_for_flight(flight_id) >= int(info["Capacity"]):
            raise ValueError("This flight is full.")

        self.execute(
            """
            INSERT INTO Transactions (
                Booking_Date,
                Departure_Date,
                Type,
                Emp_ID,
                Ps_ID,
                Flight_ID,
                Charge_Amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                date.today().isoformat(),
                info["Flight_date"],
                payment_type,
                emp_id,
                ps_id,
                flight_id,
                info["Charge_Amount"],
            ),
        )

    def passenger_transactions(self, ps_id: int):
        return self.fetchall(
            """
            SELECT
                t.TS_ID,
                t.Booking_Date,
                t.Departure_Date,
                t.Type,
                t.Charge_Amount,
                t.Flight_ID,
                r.Take_Off_point,
                r.Destination,
                e.Name AS Employee_Name
            FROM Transactions t
            JOIN Flight f ON f.Flight_ID = t.Flight_ID
            JOIN Route r ON r.Route_ID = f.Route_ID
            JOIN Employees e ON e.Emp_ID = t.Emp_ID
            WHERE t.Ps_ID = ?
            ORDER BY t.TS_ID DESC
            """,
            (ps_id,),
        )

    def all_transactions(self):
        return self.fetchall(
            """
            SELECT
                t.TS_ID,
                p.Name AS Passenger_Name,
                e.Name AS Employee_Name,
                t.Flight_ID,
                r.Take_Off_point,
                r.Destination,
                t.Booking_Date,
                t.Departure_Date,
                t.Type,
                t.Charge_Amount
            FROM Transactions t
            JOIN Passengers p ON p.Ps_ID = t.Ps_ID
            JOIN Employees e ON e.Emp_ID = t.Emp_ID
            JOIN Flight f ON f.Flight_ID = t.Flight_ID
            JOIN Route r ON r.Route_ID = f.Route_ID
            ORDER BY t.TS_ID DESC
            """
        )


class AirlineApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.repo = Repository()
        self.current_role = None
        self.current_id = None
        self.current_name = None
        self.selected_flight_id = None
        self.selected_route_id = None
        self.selected_airplane_id = None
        self.selected_fare_id = None
        self.selected_country_code = None
        self.selected_air_code = None

        self.passenger_map: dict[str, int] = {}
        self.admin_map: dict[str, int] = {}
        self.route_map: dict[str, int] = {}
        self.airplane_map: dict[str, int] = {}
        self.fare_map: dict[str, int] = {}
        self.country_map: dict[str, str] = {}
        self.airport_map: dict[str, str] = {}

        self.title("Airline Management System")
        self.geometry("1220x760")
        self.minsize(1120, 680)

        self._style()
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_login()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TNotebook", background="#f4f7fb")
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def clear(self):
        for child in self.container.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        header = tk.Frame(self.container, bg="#17363a", height=88)
        header.pack(fill="x", padx=18, pady=(18, 10))
        header.pack_propagate(False)
        tk.Label(header, text="Airline Management System", bg="#17363a", fg="white", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=18, pady=(10, 0))
        tk.Label(
            header,
            text="Role-based Tkinter app directly connected to ER tables in setup.sql",
            bg="#17363a",
            fg="#d6e5e2",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=18, pady=(2, 0))

        main = ttk.Frame(self.container)
        main.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        main.columnconfigure((0, 1), weight=1)

        p_card = self._login_card(main, "Passenger Login", "Passenger", "#1f5a61")
        a_card = self._login_card(main, "Admin Login", "Admin", "#d4683f")
        p_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        a_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def _login_card(self, parent, title: str, role: str, color: str):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.columnconfigure(0, weight=1)

        top = tk.Frame(card, bg=color, height=64)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)
        tk.Label(top, text=title, bg=color, fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=14, pady=(12, 0))

        body = ttk.Frame(card, style="Card.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text="Select seeded account", background="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 6))
        combo = ttk.Combobox(body, state="readonly")
        combo.grid(row=1, column=0, sticky="ew")

        if role == "Passenger":
            options = self.repo.passenger_options()
            labels = [f"{row['Name']} (ID:{row['Ps_ID']})" for row in options]
            self.passenger_map = {labels[i]: int(options[i]["Ps_ID"]) for i in range(len(options))}
            combo["values"] = labels
        else:
            options = self.repo.admin_options()
            labels = [f"{row['Name']} (ID:{row['Emp_ID']})" for row in options]
            self.admin_map = {labels[i]: int(options[i]["Emp_ID"]) for i in range(len(options))}
            combo["values"] = labels

        if combo["values"]:
            combo.set(combo["values"][0])

        ttk.Label(body, text="Password", background="#ffffff").grid(row=2, column=0, sticky="w", pady=(10, 4))
        password_entry = ttk.Entry(body, show="*")
        password_entry.grid(row=3, column=0, sticky="ew")

        ttk.Button(body, text=f"Enter as {role}", command=lambda r=role, c=combo, p=password_entry: self.login(r, c, p)).grid(row=4, column=0, sticky="ew", pady=(10, 0))

        if role == "Passenger":
            ttk.Button(body, text="Create New Passenger Account", command=self.open_passenger_signup).grid(row=5, column=0, sticky="ew", pady=(8, 0))

        ttk.Label(body, text="Seed users default password: 1234", background="#ffffff").grid(row=6, column=0, sticky="w", pady=(8, 0))
        return card

    def login(self, role: str, combo: ttk.Combobox, password_entry: ttk.Entry):
        selected = combo.get().strip()
        password = password_entry.get().strip()
        if not selected:
            messagebox.showwarning("Login", "Select a user.")
            return
        if not password:
            messagebox.showwarning("Login", "Enter password.")
            return

        if role == "Passenger":
            self.current_id = self.passenger_map.get(selected)
            valid = self.current_id is not None and self.repo.validate_passenger_login(int(self.current_id), password)
        else:
            self.current_id = self.admin_map.get(selected)
            valid = self.current_id is not None and self.repo.validate_admin_login(int(self.current_id), password)

        if self.current_id is None:
            messagebox.showerror("Login", "User not found.")
            return
        if not valid:
            messagebox.showerror("Login", "Invalid password.")
            return

        self.current_role = role
        self.current_name = selected.split(" (ID:")[0]
        self.show_dashboard()

    def open_passenger_signup(self):
        window = tk.Toplevel(self)
        window.title("Create Passenger Account")
        window.geometry("420x440")
        window.resizable(False, False)

        wrapper = ttk.Frame(window, style="Card.TFrame")
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)
        wrapper.columnconfigure(0, weight=1)

        ttk.Label(wrapper, text="Name", background="#ffffff").grid(row=0, column=0, sticky="w", pady=(4, 4))
        name = ttk.Entry(wrapper)
        name.grid(row=1, column=0, sticky="ew")

        ttk.Label(wrapper, text="Address", background="#ffffff").grid(row=2, column=0, sticky="w", pady=(10, 4))
        address = ttk.Entry(wrapper)
        address.grid(row=3, column=0, sticky="ew")

        ttk.Label(wrapper, text="Age", background="#ffffff").grid(row=4, column=0, sticky="w", pady=(10, 4))
        age = ttk.Entry(wrapper)
        age.grid(row=5, column=0, sticky="ew")

        ttk.Label(wrapper, text="Sex", background="#ffffff").grid(row=6, column=0, sticky="w", pady=(10, 4))
        sex = ttk.Combobox(wrapper, state="readonly", values=["F", "M", "Other"])
        sex.grid(row=7, column=0, sticky="ew")
        sex.set("F")

        ttk.Label(wrapper, text="Contacts", background="#ffffff").grid(row=8, column=0, sticky="w", pady=(10, 4))
        contacts = ttk.Entry(wrapper)
        contacts.grid(row=9, column=0, sticky="ew")

        ttk.Label(wrapper, text="Password", background="#ffffff").grid(row=10, column=0, sticky="w", pady=(10, 4))
        password = ttk.Entry(wrapper, show="*")
        password.grid(row=11, column=0, sticky="ew")

        ttk.Label(wrapper, text="Confirm Password", background="#ffffff").grid(row=12, column=0, sticky="w", pady=(10, 4))
        confirm = ttk.Entry(wrapper, show="*")
        confirm.grid(row=13, column=0, sticky="ew")

        def create_account():
            try:
                if password.get().strip() != confirm.get().strip():
                    raise ValueError("Passwords do not match.")
                self.repo.create_passenger_account(
                    name.get().strip(),
                    address.get().strip(),
                    int(age.get().strip()),
                    sex.get().strip(),
                    contacts.get().strip(),
                    password.get().strip(),
                )
            except Exception as exc:
                messagebox.showerror("Account", str(exc), parent=window)
                return
            messagebox.showinfo("Account", "Passenger account created.", parent=window)
            window.destroy()
            self.show_login()

        ttk.Button(wrapper, text="Create Account", command=create_account).grid(row=14, column=0, sticky="ew", pady=(14, 0))

    def show_dashboard(self):
        self.clear()
        top = ttk.Frame(self.container)
        top.pack(fill="x", padx=18, pady=(18, 8))
        info = ttk.Frame(top, style="Card.TFrame")
        info.pack(side="left", fill="x", expand=True)
        ttk.Label(info, text=f"{self.current_name}", background="#ffffff", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        ttk.Label(info, text=f"Role: {self.current_role}", background="#ffffff").pack(anchor="w", padx=12, pady=(2, 10))
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")

        if self.current_role == "Passenger":
            self.build_passenger_screen()
        else:
            self.build_admin_screen()

    def build_passenger_screen(self):
        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        flights_tab = ttk.Frame(notebook)
        tx_tab = ttk.Frame(notebook)
        notebook.add(flights_tab, text="Flights")
        notebook.add(tx_tab, text="My Transactions")

        flights_tab.columnconfigure(0, weight=2)
        flights_tab.columnconfigure(1, weight=1)
        flights_tab.rowconfigure(1, weight=1)

        filter_card = ttk.Frame(flights_tab, style="Card.TFrame")
        filter_card.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=10)
        filter_card.columnconfigure((0, 1), weight=1)

        ttk.Label(filter_card, text="Keyword", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.p_keyword = ttk.Entry(filter_card)
        self.p_keyword.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(filter_card, text="Flight Date (YYYY-MM-DD)", background="#ffffff").grid(row=0, column=1, sticky="w", padx=12, pady=(10, 4))
        self.p_date = ttk.Entry(filter_card)
        self.p_date.grid(row=1, column=1, sticky="ew", padx=12)

        btn_row = ttk.Frame(filter_card, style="Card.TFrame")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 12))
        ttk.Button(btn_row, text="Filter", command=self.refresh_passenger_flights).pack(side="left")
        ttk.Button(btn_row, text="Reset", command=self.reset_passenger_filter).pack(side="left", padx=(8, 0))

        table_frame, self.p_flight_tree = self._make_tree(
            flights_tab,
            ("Flight_ID", "Route", "Flight_date", "Departure", "Arrival", "Company", "Capacity", "Booked", "Price"),
            [
                ("Flight_ID", "ID"),
                ("Route", "Route"),
                ("Flight_date", "Date"),
                ("Departure", "Dep"),
                ("Arrival", "Arr"),
                ("Company", "Plane"),
                ("Capacity", "Cap"),
                ("Booked", "Booked"),
                ("Price", "Fare"),
            ],
            {"Flight_ID": 60, "Route": 180, "Flight_date": 100, "Departure": 80, "Arrival": 80, "Company": 110, "Capacity": 70, "Booked": 70, "Price": 90},
        )
        table_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.p_flight_tree.bind("<<TreeviewSelect>>", self.on_select_passenger_flight)

        action = ttk.Frame(flights_tab, style="Card.TFrame")
        action.grid(row=1, column=1, sticky="nsew", pady=(0, 10))
        action.columnconfigure(0, weight=1)
        ttk.Label(action, text="Book Flight", background="#ffffff", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.selected_flight_label = ttk.Label(action, text="No flight selected", background="#ffffff", wraplength=260)
        self.selected_flight_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        ttk.Label(action, text="Payment Type", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(8, 4))
        self.p_payment_type = ttk.Combobox(action, state="readonly", values=["Card", "Cash", "Transfer", "Online"])
        self.p_payment_type.grid(row=3, column=0, sticky="ew", padx=12)
        self.p_payment_type.set("Card")

        ttk.Label(action, text="Handled By Employee", background="#ffffff").grid(row=4, column=0, sticky="w", padx=12, pady=(8, 4))
        self.p_employee_combo = ttk.Combobox(action, state="readonly")
        self.p_employee_combo.grid(row=5, column=0, sticky="ew", padx=12)
        emps = self.repo.admin_options()
        emp_labels = [f"{e['Name']} (ID:{e['Emp_ID']})" for e in emps]
        self.admin_map = {emp_labels[i]: int(emps[i]["Emp_ID"]) for i in range(len(emps))}
        self.p_employee_combo["values"] = emp_labels
        if emp_labels:
            self.p_employee_combo.set(emp_labels[0])

        ttk.Button(action, text="Create Booking", command=self.create_passenger_booking).grid(row=6, column=0, sticky="ew", padx=12, pady=(12, 8))

        tx_frame, self.p_tx_tree = self._make_tree(
            tx_tab,
            ("TS_ID", "Flight_ID", "Route", "Booking_Date", "Departure_Date", "Type", "Charge_Amount", "Employee"),
            [
                ("TS_ID", "TS_ID"),
                ("Flight_ID", "Flight"),
                ("Route", "Route"),
                ("Booking_Date", "Booking"),
                ("Departure_Date", "Departure"),
                ("Type", "Type"),
                ("Charge_Amount", "Amount"),
                ("Employee", "Employee"),
            ],
            {"TS_ID": 70, "Flight_ID": 70, "Route": 180, "Booking_Date": 110, "Departure_Date": 110, "Type": 80, "Charge_Amount": 90, "Employee": 140},
        )
        tx_frame.pack(fill="both", expand=True, pady=10)
        ttk.Button(tx_tab, text="Refresh", command=self.refresh_passenger_transactions).pack(anchor="w", pady=(0, 10))

        self.refresh_passenger_flights()
        self.refresh_passenger_transactions()

    def build_admin_screen(self):
        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        f_tab = ttk.Frame(notebook)
        r_tab = ttk.Frame(notebook)
        c_tab = ttk.Frame(notebook)
        ap_tab = ttk.Frame(notebook)
        p_tab = ttk.Frame(notebook)
        fare_tab = ttk.Frame(notebook)
        t_tab = ttk.Frame(notebook)
        notebook.add(f_tab, text="Manage Flights")
        notebook.add(r_tab, text="Routes")
        notebook.add(c_tab, text="Countries")
        notebook.add(ap_tab, text="Airports")
        notebook.add(p_tab, text="Airplane Types")
        notebook.add(fare_tab, text="AirFares")
        notebook.add(t_tab, text="Transactions")

        self._build_admin_flights_tab(f_tab)
        self._build_admin_routes_tab(r_tab)
        self._build_admin_countries_tab(c_tab)
        self._build_admin_airports_tab(ap_tab)
        self._build_admin_airplanes_tab(p_tab)
        self._build_admin_airfares_tab(fare_tab)
        self._build_admin_transactions_tab(t_tab)
        self.refresh_admin_flights()
        self.refresh_admin_routes()
        self.refresh_admin_countries()
        self.refresh_admin_airports()
        self.refresh_admin_airplanes()
        self.refresh_admin_airfares()
        self.refresh_admin_transactions()

    def _build_admin_flights_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Departure (HH:MM)", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_departure = ttk.Entry(form)
        self.a_departure.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Arrival (HH:MM)", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_arrival = ttk.Entry(form)
        self.a_arrival.grid(row=3, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Flight Date (YYYY-MM-DD)", background="#ffffff").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_date = ttk.Entry(form)
        self.a_date.grid(row=5, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Route", background="#ffffff").grid(row=6, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_route = ttk.Combobox(form, state="readonly")
        self.a_route.grid(row=7, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Airplane Type", background="#ffffff").grid(row=8, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_airplane = ttk.Combobox(form, state="readonly")
        self.a_airplane.grid(row=9, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="AirFare", background="#ffffff").grid(row=10, column=0, sticky="w", padx=12, pady=(10, 4))
        self.a_fare = ttk.Combobox(form, state="readonly")
        self.a_fare.grid(row=11, column=0, sticky="ew", padx=12)

        self._refresh_flight_form_options()

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=12, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_flight),
            ("Update", self.update_admin_flight),
            ("Delete", self.delete_admin_flight),
            ("Clear", self.clear_admin_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        t_frame, self.a_flight_tree = self._make_tree(
            parent,
            ("Flight_ID", "Route", "Flight_date", "Departure", "Arrival", "Company", "Capacity", "Booked", "Fare"),
            [
                ("Flight_ID", "ID"),
                ("Route", "Route"),
                ("Flight_date", "Date"),
                ("Departure", "Dep"),
                ("Arrival", "Arr"),
                ("Company", "Plane"),
                ("Capacity", "Cap"),
                ("Booked", "Booked"),
                ("Fare", "Fare"),
            ],
            {"Flight_ID": 60, "Route": 170, "Flight_date": 100, "Departure": 80, "Arrival": 80, "Company": 110, "Capacity": 70, "Booked": 70, "Fare": 90},
        )
        t_frame.grid(row=0, column=1, sticky="nsew", pady=10)
        self.a_flight_tree.bind("<<TreeviewSelect>>", self.on_select_admin_flight)

    def _build_admin_transactions_tab(self, parent):
        frame, self.a_tx_tree = self._make_tree(
            parent,
            ("TS_ID", "Passenger", "Employee", "Flight_ID", "Route", "Booking_Date", "Departure_Date", "Type", "Amount"),
            [
                ("TS_ID", "TS_ID"),
                ("Passenger", "Passenger"),
                ("Employee", "Employee"),
                ("Flight_ID", "Flight"),
                ("Route", "Route"),
                ("Booking_Date", "Booking"),
                ("Departure_Date", "Departure"),
                ("Type", "Type"),
                ("Amount", "Amount"),
            ],
            {"TS_ID": 70, "Passenger": 140, "Employee": 140, "Flight_ID": 70, "Route": 170, "Booking_Date": 110, "Departure_Date": 110, "Type": 80, "Amount": 90},
        )
        frame.pack(fill="both", expand=True, pady=10)
        ttk.Button(parent, text="Refresh", command=self.refresh_admin_transactions).pack(anchor="w", pady=(0, 10))

    def _build_admin_routes_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Take Off Point", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.r_take_off = ttk.Combobox(form, state="readonly")
        self.r_take_off.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Destination", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.r_destination = ttk.Combobox(form, state="readonly")
        self.r_destination.grid(row=3, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Route Type", background="#ffffff").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 4))
        self.r_type = ttk.Combobox(form, state="readonly", values=["Domestic", "International", "Charter"])
        self.r_type.grid(row=5, column=0, sticky="ew", padx=12)
        self.r_type.set("Domestic")

        self._refresh_airport_choices()

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=6, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_route),
            ("Update", self.update_admin_route),
            ("Delete", self.delete_admin_route),
            ("Clear", self.clear_admin_route_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        table, self.r_tree = self._make_tree(
            parent,
            ("Route_ID", "Take_Off_point", "Destination", "R_type"),
            [("Route_ID", "ID"), ("Take_Off_point", "Take Off"), ("Destination", "Destination"), ("R_type", "Type")],
            {"Route_ID": 60, "Take_Off_point": 140, "Destination": 140, "R_type": 100},
        )
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        self.r_tree.bind("<<TreeviewSelect>>", self.on_select_admin_route)

    def _build_admin_airplanes_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Company", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.pl_company = ttk.Entry(form)
        self.pl_company.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Capacity", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.pl_capacity = ttk.Entry(form)
        self.pl_capacity.grid(row=3, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="A_weight", background="#ffffff").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 4))
        self.pl_weight = ttk.Entry(form)
        self.pl_weight.grid(row=5, column=0, sticky="ew", padx=12)

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=6, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_airplane),
            ("Update", self.update_admin_airplane),
            ("Delete", self.delete_admin_airplane),
            ("Clear", self.clear_admin_airplane_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        table, self.pl_tree = self._make_tree(
            parent,
            ("A_ID", "Company", "Capacity", "A_weight"),
            [("A_ID", "ID"), ("Company", "Company"), ("Capacity", "Capacity"), ("A_weight", "Weight")],
            {"A_ID": 60, "Company": 150, "Capacity": 100, "A_weight": 120},
        )
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        self.pl_tree.bind("<<TreeviewSelect>>", self.on_select_admin_airplane)

    def _build_admin_airfares_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Charge Amount", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.f_amount = ttk.Entry(form)
        self.f_amount.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Description", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.f_desc = ttk.Entry(form)
        self.f_desc.grid(row=3, column=0, sticky="ew", padx=12)

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=4, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_airfare),
            ("Update", self.update_admin_airfare),
            ("Delete", self.delete_admin_airfare),
            ("Clear", self.clear_admin_airfare_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        table, self.f_tree = self._make_tree(
            parent,
            ("Fare_ID", "Charge_Amount", "Description"),
            [("Fare_ID", "ID"), ("Charge_Amount", "Amount"), ("Description", "Description")],
            {"Fare_ID": 60, "Charge_Amount": 120, "Description": 220},
        )
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        self.f_tree.bind("<<TreeviewSelect>>", self.on_select_admin_airfare)

    def _build_admin_countries_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Country Code", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.c_code = ttk.Entry(form)
        self.c_code.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Country Name", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.c_name = ttk.Entry(form)
        self.c_name.grid(row=3, column=0, sticky="ew", padx=12)

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=4, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_country),
            ("Update", self.update_admin_country),
            ("Delete", self.delete_admin_country),
            ("Clear", self.clear_admin_country_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        table, self.c_tree = self._make_tree(
            parent,
            ("Country_code", "Country_Name"),
            [("Country_code", "Code"), ("Country_Name", "Name")],
            {"Country_code": 120, "Country_Name": 220},
        )
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        self.c_tree.bind("<<TreeviewSelect>>", self.on_select_admin_country)

    def _build_admin_airports_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        form = ttk.Frame(parent, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Air Code", background="#ffffff").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.ap_code = ttk.Entry(form)
        self.ap_code.grid(row=1, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Air Name", background="#ffffff").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 4))
        self.ap_name = ttk.Entry(form)
        self.ap_name.grid(row=3, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="City", background="#ffffff").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 4))
        self.ap_city = ttk.Entry(form)
        self.ap_city.grid(row=5, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="State", background="#ffffff").grid(row=6, column=0, sticky="w", padx=12, pady=(10, 4))
        self.ap_state = ttk.Entry(form)
        self.ap_state.grid(row=7, column=0, sticky="ew", padx=12)

        ttk.Label(form, text="Country", background="#ffffff").grid(row=8, column=0, sticky="w", padx=12, pady=(10, 4))
        self.ap_country = ttk.Combobox(form, state="readonly")
        self.ap_country.grid(row=9, column=0, sticky="ew", padx=12)
        self._refresh_country_choices()

        btn = ttk.Frame(form, style="Card.TFrame")
        btn.grid(row=10, column=0, sticky="ew", padx=12, pady=(12, 12))
        for i, (label, cmd) in enumerate([
            ("Add", self.add_admin_airport),
            ("Update", self.update_admin_airport),
            ("Delete", self.delete_admin_airport),
            ("Clear", self.clear_admin_airport_form),
        ]):
            ttk.Button(btn, text=label, command=cmd).grid(row=0, column=i, sticky="ew", padx=3)
            btn.columnconfigure(i, weight=1)

        table, self.ap_tree = self._make_tree(
            parent,
            ("Air_Code", "Air_Name", "City", "State", "Country"),
            [("Air_Code", "Code"), ("Air_Name", "Name"), ("City", "City"), ("State", "State"), ("Country", "Country")],
            {"Air_Code": 90, "Air_Name": 180, "City": 120, "State": 120, "Country": 140},
        )
        table.grid(row=0, column=1, sticky="nsew", pady=10)
        self.ap_tree.bind("<<TreeviewSelect>>", self.on_select_admin_airport)

    def _make_tree(self, parent, columns, headings, widths):
        wrapper = ttk.Frame(parent, style="Card.TFrame")
        tree = ttk.Treeview(wrapper, columns=columns, show="headings", selectmode="browse")
        for key, title in headings:
            tree.heading(key, text=title)
            tree.column(key, width=widths.get(key, 120), anchor="center")
        sb = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        sb.grid(row=0, column=1, sticky="ns", pady=10)
        return wrapper, tree

    def reset_passenger_filter(self):
        self.p_keyword.delete(0, tk.END)
        self.p_date.delete(0, tk.END)
        self.refresh_passenger_flights()

    def refresh_passenger_flights(self):
        rows = self.repo.list_flights(self.p_keyword.get().strip(), self.p_date.get().strip())
        for item in self.p_flight_tree.get_children():
            self.p_flight_tree.delete(item)
        for row in rows:
            route = f"{row['Take_Off_point']} -> {row['Destination']}"
            self.p_flight_tree.insert(
                "",
                "end",
                values=(
                    row["Flight_ID"],
                    route,
                    row["Flight_date"],
                    row["Departure"],
                    row["Arrival"],
                    row["Company"],
                    row["Capacity"],
                    row["Booked_Count"],
                    row["Charge_Amount"],
                ),
            )

    def on_select_passenger_flight(self, _event):
        selection = self.p_flight_tree.selection()
        if not selection:
            return
        values = self.p_flight_tree.item(selection[0], "values")
        self.selected_flight_id = int(values[0])
        self.selected_flight_label.configure(text=f"Selected Flight: {values[0]} | {values[1]} | {values[2]}")

    def create_passenger_booking(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Booking", "Select a flight first.")
            return
        emp_text = self.p_employee_combo.get().strip()
        emp_id = self.admin_map.get(emp_text)
        if emp_id is None:
            messagebox.showwarning("Booking", "Select an employee.")
            return
        try:
            self.repo.create_booking(emp_id, int(self.current_id), self.selected_flight_id, self.p_payment_type.get().strip())
        except Exception as exc:
            messagebox.showerror("Booking", str(exc))
            return
        self.refresh_passenger_flights()
        self.refresh_passenger_transactions()
        messagebox.showinfo("Booking", "Transaction created successfully.")

    def refresh_passenger_transactions(self):
        rows = self.repo.passenger_transactions(int(self.current_id))
        for item in self.p_tx_tree.get_children():
            self.p_tx_tree.delete(item)
        for row in rows:
            route = f"{row['Take_Off_point']} -> {row['Destination']}"
            self.p_tx_tree.insert(
                "",
                "end",
                values=(
                    row["TS_ID"],
                    row["Flight_ID"],
                    route,
                    row["Booking_Date"],
                    row["Departure_Date"],
                    row["Type"],
                    row["Charge_Amount"],
                    row["Employee_Name"],
                ),
            )

    def _refresh_flight_form_options(self):
        routes = self.repo.list_routes()
        planes = self.repo.list_airplanes()
        fares = self.repo.list_airfares()

        route_labels = [f"{r['Route_ID']} | {r['Take_Off_point']} -> {r['Destination']} ({r['R_type']})" for r in routes]
        plane_labels = [f"{p['A_ID']} | {p['Company']} | cap:{p['Capacity']}" for p in planes]
        fare_labels = [f"{f['Fare_ID']} | {f['Charge_Amount']}" for f in fares]

        self.route_map = {route_labels[i]: int(routes[i]["Route_ID"]) for i in range(len(routes))}
        self.airplane_map = {plane_labels[i]: int(planes[i]["A_ID"]) for i in range(len(planes))}
        self.fare_map = {fare_labels[i]: int(fares[i]["Fare_ID"]) for i in range(len(fares))}

        self.a_route["values"] = route_labels
        self.a_airplane["values"] = plane_labels
        self.a_fare["values"] = fare_labels

        if route_labels:
            self.a_route.set(route_labels[0])
        if plane_labels:
            self.a_airplane.set(plane_labels[0])
        if fare_labels:
            self.a_fare.set(fare_labels[0])

    def _refresh_airport_choices(self):
        airports = self.repo.list_airport_codes()
        labels = [f"{a['Air_Code']} | {a['Air_Name']} ({a['City']})" for a in airports]
        self.airport_map = {labels[i]: airports[i]["Air_Code"] for i in range(len(airports))}
        self.r_take_off["values"] = labels
        self.r_destination["values"] = labels
        if labels:
            self.r_take_off.set(labels[0])
            self.r_destination.set(labels[min(1, len(labels) - 1)])

    def _refresh_country_choices(self):
        countries = self.repo.list_countries()
        labels = [f"{c['Country_code']} | {c['Country_Name']}" for c in countries]
        self.country_map = {labels[i]: countries[i]["Country_code"] for i in range(len(countries))}
        self.ap_country["values"] = labels
        if labels:
            self.ap_country.set(labels[0])

    def refresh_admin_flights(self):
        rows = self.repo.list_flights()
        for item in self.a_flight_tree.get_children():
            self.a_flight_tree.delete(item)
        for row in rows:
            route = f"{row['Take_Off_point']} -> {row['Destination']}"
            self.a_flight_tree.insert(
                "",
                "end",
                values=(
                    row["Flight_ID"],
                    route,
                    row["Flight_date"],
                    row["Departure"],
                    row["Arrival"],
                    row["Company"],
                    row["Capacity"],
                    row["Booked_Count"],
                    row["Charge_Amount"],
                ),
            )

    def on_select_admin_flight(self, _event):
        selection = self.a_flight_tree.selection()
        if not selection:
            return
        values = self.a_flight_tree.item(selection[0], "values")
        self.selected_flight_id = int(values[0])
        self.a_date.delete(0, tk.END)
        self.a_date.insert(0, values[2])
        self.a_departure.delete(0, tk.END)
        self.a_departure.insert(0, values[3])
        self.a_arrival.delete(0, tk.END)
        self.a_arrival.insert(0, values[4])

    def clear_admin_form(self):
        self.selected_flight_id = None
        self.a_date.delete(0, tk.END)
        self.a_departure.delete(0, tk.END)
        self.a_arrival.delete(0, tk.END)
        self._refresh_flight_form_options()

    def add_admin_flight(self):
        try:
            self.repo.add_flight(
                self.a_departure.get().strip(),
                self.a_arrival.get().strip(),
                self.a_date.get().strip(),
                self.route_map[self.a_route.get().strip()],
                self.airplane_map[self.a_airplane.get().strip()],
                self.fare_map[self.a_fare.get().strip()],
            )
        except Exception as exc:
            messagebox.showerror("Flights", str(exc))
            return
        self.clear_admin_form()
        self.refresh_admin_flights()

    def update_admin_flight(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Flights", "Select a flight first.")
            return
        try:
            self.repo.update_flight(
                self.selected_flight_id,
                self.a_departure.get().strip(),
                self.a_arrival.get().strip(),
                self.a_date.get().strip(),
                self.route_map[self.a_route.get().strip()],
                self.airplane_map[self.a_airplane.get().strip()],
                self.fare_map[self.a_fare.get().strip()],
            )
        except Exception as exc:
            messagebox.showerror("Flights", str(exc))
            return
        self.refresh_admin_flights()

    def delete_admin_flight(self):
        if self.selected_flight_id is None:
            messagebox.showwarning("Flights", "Select a flight first.")
            return
        if not messagebox.askyesno("Flights", "Delete selected flight?"):
            return
        try:
            self.repo.delete_flight(self.selected_flight_id)
        except Exception as exc:
            messagebox.showerror("Flights", str(exc))
            return
        self.clear_admin_form()
        self.refresh_admin_flights()

    def refresh_admin_transactions(self):
        rows = self.repo.all_transactions()
        for item in self.a_tx_tree.get_children():
            self.a_tx_tree.delete(item)
        for row in rows:
            route = f"{row['Take_Off_point']} -> {row['Destination']}"
            self.a_tx_tree.insert(
                "",
                "end",
                values=(
                    row["TS_ID"],
                    row["Passenger_Name"],
                    row["Employee_Name"],
                    row["Flight_ID"],
                    route,
                    row["Booking_Date"],
                    row["Departure_Date"],
                    row["Type"],
                    row["Charge_Amount"],
                ),
            )

    def refresh_admin_routes(self):
        rows = self.repo.list_routes()
        for item in self.r_tree.get_children():
            self.r_tree.delete(item)
        for row in rows:
            self.r_tree.insert("", "end", values=(row["Route_ID"], row["Take_Off_point"], row["Destination"], row["R_type"]))
        self._refresh_flight_form_options()

    def on_select_admin_route(self, _event):
        selection = self.r_tree.selection()
        if not selection:
            return
        values = self.r_tree.item(selection[0], "values")
        self.selected_route_id = int(values[0])
        for label, code in self.airport_map.items():
            if code == values[1]:
                self.r_take_off.set(label)
            if code == values[2]:
                self.r_destination.set(label)
        self.r_type.set(values[3])

    def clear_admin_route_form(self):
        self.selected_route_id = None
        self.r_type.set("Domestic")
        self._refresh_airport_choices()

    def add_admin_route(self):
        try:
            self.repo.add_route(
                self.airport_map[self.r_destination.get().strip()],
                self.airport_map[self.r_take_off.get().strip()],
                self.r_type.get().strip(),
            )
        except Exception as exc:
            messagebox.showerror("Routes", str(exc))
            return
        self.refresh_admin_routes()

    def update_admin_route(self):
        if self.selected_route_id is None:
            messagebox.showwarning("Routes", "Select a route first.")
            return
        try:
            self.repo.update_route(
                self.selected_route_id,
                self.airport_map[self.r_destination.get().strip()],
                self.airport_map[self.r_take_off.get().strip()],
                self.r_type.get().strip(),
            )
        except Exception as exc:
            messagebox.showerror("Routes", str(exc))
            return
        self.refresh_admin_routes()

    def delete_admin_route(self):
        if self.selected_route_id is None:
            messagebox.showwarning("Routes", "Select a route first.")
            return
        if not messagebox.askyesno("Routes", "Delete selected route?"):
            return
        try:
            self.repo.delete_route(self.selected_route_id)
        except Exception as exc:
            messagebox.showerror("Routes", str(exc))
            return
        self.clear_admin_route_form()
        self.refresh_admin_routes()

    def refresh_admin_airplanes(self):
        rows = self.repo.list_airplanes()
        for item in self.pl_tree.get_children():
            self.pl_tree.delete(item)
        for row in rows:
            self.pl_tree.insert("", "end", values=(row["A_ID"], row["Company"], row["Capacity"], row["A_weight"]))
        self._refresh_flight_form_options()

    def on_select_admin_airplane(self, _event):
        selection = self.pl_tree.selection()
        if not selection:
            return
        values = self.pl_tree.item(selection[0], "values")
        self.selected_airplane_id = int(values[0])
        self.pl_company.delete(0, tk.END)
        self.pl_company.insert(0, values[1])
        self.pl_capacity.delete(0, tk.END)
        self.pl_capacity.insert(0, values[2])
        self.pl_weight.delete(0, tk.END)
        self.pl_weight.insert(0, values[3])

    def clear_admin_airplane_form(self):
        self.selected_airplane_id = None
        self.pl_company.delete(0, tk.END)
        self.pl_capacity.delete(0, tk.END)
        self.pl_weight.delete(0, tk.END)

    def add_admin_airplane(self):
        try:
            self.repo.add_airplane(int(self.pl_capacity.get().strip()), float(self.pl_weight.get().strip()), self.pl_company.get().strip())
        except Exception as exc:
            messagebox.showerror("Airplane", str(exc))
            return
        self.clear_admin_airplane_form()
        self.refresh_admin_airplanes()

    def update_admin_airplane(self):
        if self.selected_airplane_id is None:
            messagebox.showwarning("Airplane", "Select an airplane first.")
            return
        try:
            self.repo.update_airplane(self.selected_airplane_id, int(self.pl_capacity.get().strip()), float(self.pl_weight.get().strip()), self.pl_company.get().strip())
        except Exception as exc:
            messagebox.showerror("Airplane", str(exc))
            return
        self.refresh_admin_airplanes()

    def delete_admin_airplane(self):
        if self.selected_airplane_id is None:
            messagebox.showwarning("Airplane", "Select an airplane first.")
            return
        if not messagebox.askyesno("Airplane", "Delete selected airplane?"):
            return
        try:
            self.repo.delete_airplane(self.selected_airplane_id)
        except Exception as exc:
            messagebox.showerror("Airplane", str(exc))
            return
        self.clear_admin_airplane_form()
        self.refresh_admin_airplanes()

    def refresh_admin_airfares(self):
        rows = self.repo.list_airfares()
        for item in self.f_tree.get_children():
            self.f_tree.delete(item)
        for row in rows:
            self.f_tree.insert("", "end", values=(row["Fare_ID"], row["Charge_Amount"], row["Description"]))
        self._refresh_flight_form_options()

    def refresh_admin_countries(self):
        rows = self.repo.list_countries()
        for item in self.c_tree.get_children():
            self.c_tree.delete(item)
        for row in rows:
            self.c_tree.insert("", "end", values=(row["Country_code"], row["Country_Name"]))
        self._refresh_country_choices()

    def on_select_admin_country(self, _event):
        selection = self.c_tree.selection()
        if not selection:
            return
        values = self.c_tree.item(selection[0], "values")
        self.selected_country_code = values[0]
        self.c_code.delete(0, tk.END)
        self.c_code.insert(0, values[0])
        self.c_code.config(state="disabled")
        self.c_name.delete(0, tk.END)
        self.c_name.insert(0, values[1])

    def clear_admin_country_form(self):
        self.selected_country_code = None
        self.c_code.config(state="normal")
        self.c_code.delete(0, tk.END)
        self.c_name.delete(0, tk.END)

    def add_admin_country(self):
        try:
            self.repo.add_country(self.c_code.get().strip().upper(), self.c_name.get().strip())
        except Exception as exc:
            messagebox.showerror("Countries", str(exc))
            return
        self.clear_admin_country_form()
        self.refresh_admin_countries()

    def update_admin_country(self):
        if self.selected_country_code is None:
            messagebox.showwarning("Countries", "Select a country first.")
            return
        try:
            self.repo.update_country(self.selected_country_code, self.c_name.get().strip())
        except Exception as exc:
            messagebox.showerror("Countries", str(exc))
            return
        self.refresh_admin_countries()

    def delete_admin_country(self):
        if self.selected_country_code is None:
            messagebox.showwarning("Countries", "Select a country first.")
            return
        if not messagebox.askyesno("Countries", "Delete selected country?"):
            return
        try:
            self.repo.delete_country(self.selected_country_code)
        except Exception as exc:
            messagebox.showerror("Countries", str(exc))
            return
        self.clear_admin_country_form()
        self.refresh_admin_countries()

    def refresh_admin_airports(self):
        rows = self.repo.list_airports()
        for item in self.ap_tree.get_children():
            self.ap_tree.delete(item)
        for row in rows:
            self.ap_tree.insert("", "end", values=(row["Air_Code"], row["Air_Name"], row["City"], row["State"], row["Country_Name"]))
        self._refresh_airport_choices()

    def on_select_admin_airport(self, _event):
        selection = self.ap_tree.selection()
        if not selection:
            return
        values = self.ap_tree.item(selection[0], "values")
        self.selected_air_code = values[0]
        code = values[0]
        row = self.repo.fetchone("SELECT Air_Code, Air_Name, City, State, Country_code FROM Airport WHERE Air_Code = ?", (code,))
        if row is None:
            return
        self.ap_code.delete(0, tk.END)
        self.ap_code.insert(0, row["Air_Code"])
        self.ap_code.config(state="disabled")
        self.ap_name.delete(0, tk.END)
        self.ap_name.insert(0, row["Air_Name"])
        self.ap_city.delete(0, tk.END)
        self.ap_city.insert(0, row["City"])
        self.ap_state.delete(0, tk.END)
        self.ap_state.insert(0, row["State"] or "")
        for label, c_code in self.country_map.items():
            if c_code == row["Country_code"]:
                self.ap_country.set(label)
                break

    def clear_admin_airport_form(self):
        self.selected_air_code = None
        self.ap_code.config(state="normal")
        self.ap_code.delete(0, tk.END)
        self.ap_name.delete(0, tk.END)
        self.ap_city.delete(0, tk.END)
        self.ap_state.delete(0, tk.END)
        self._refresh_country_choices()

    def add_admin_airport(self):
        try:
            self.repo.add_airport(
                self.ap_code.get().strip().upper(),
                self.ap_name.get().strip(),
                self.ap_city.get().strip(),
                self.ap_state.get().strip(),
                self.country_map[self.ap_country.get().strip()],
            )
        except Exception as exc:
            messagebox.showerror("Airports", str(exc))
            return
        self.clear_admin_airport_form()
        self.refresh_admin_airports()

    def update_admin_airport(self):
        if self.selected_air_code is None:
            messagebox.showwarning("Airports", "Select an airport first.")
            return
        try:
            self.repo.update_airport(
                self.selected_air_code,
                self.ap_name.get().strip(),
                self.ap_city.get().strip(),
                self.ap_state.get().strip(),
                self.country_map[self.ap_country.get().strip()],
            )
        except Exception as exc:
            messagebox.showerror("Airports", str(exc))
            return
        self.refresh_admin_airports()

    def delete_admin_airport(self):
        if self.selected_air_code is None:
            messagebox.showwarning("Airports", "Select an airport first.")
            return
        if not messagebox.askyesno("Airports", "Delete selected airport?"):
            return
        try:
            self.repo.delete_airport(self.selected_air_code)
        except Exception as exc:
            messagebox.showerror("Airports", str(exc))
            return
        self.clear_admin_airport_form()
        self.refresh_admin_airports()

    def on_select_admin_airfare(self, _event):
        selection = self.f_tree.selection()
        if not selection:
            return
        values = self.f_tree.item(selection[0], "values")
        self.selected_fare_id = int(values[0])
        self.f_amount.delete(0, tk.END)
        self.f_amount.insert(0, values[1])
        self.f_desc.delete(0, tk.END)
        self.f_desc.insert(0, values[2])

    def clear_admin_airfare_form(self):
        self.selected_fare_id = None
        self.f_amount.delete(0, tk.END)
        self.f_desc.delete(0, tk.END)

    def add_admin_airfare(self):
        try:
            self.repo.add_airfare(float(self.f_amount.get().strip()), self.f_desc.get().strip())
        except Exception as exc:
            messagebox.showerror("AirFare", str(exc))
            return
        self.clear_admin_airfare_form()
        self.refresh_admin_airfares()

    def update_admin_airfare(self):
        if self.selected_fare_id is None:
            messagebox.showwarning("AirFare", "Select an airfare first.")
            return
        try:
            self.repo.update_airfare(self.selected_fare_id, float(self.f_amount.get().strip()), self.f_desc.get().strip())
        except Exception as exc:
            messagebox.showerror("AirFare", str(exc))
            return
        self.refresh_admin_airfares()

    def delete_admin_airfare(self):
        if self.selected_fare_id is None:
            messagebox.showwarning("AirFare", "Select an airfare first.")
            return
        if not messagebox.askyesno("AirFare", "Delete selected airfare?"):
            return
        try:
            self.repo.delete_airfare(self.selected_fare_id)
        except Exception as exc:
            messagebox.showerror("AirFare", str(exc))
            return
        self.clear_admin_airfare_form()
        self.refresh_admin_airfares()


if __name__ == "__main__":
    app = AirlineApp()
    app.mainloop()
