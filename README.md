# ✈ Airline Management System

> A role-based airline management system demo built with **Python** and **SQLite**.  
> Real-life booking flow: passengers pay and receive tickets immediately; admins manage flights, refunds, and special requests.

---

## 📌 Project Overview

This project simulates the core functionality of an airline management system. Users are separated into two roles — **Passenger** and **Admin** — each with their own interface and permissions.

- **Passengers** can search for available flights, book and pay for tickets, select paid add-ons (extra baggage, pet cabin, meal preference), view their trip history, and submit special requests (seat change, wheelchair assistance, refund, etc.).
- **Admins** can manage flights, handle special requests (approve/reject), cancel or refund bookings, and view all transactions and booking records.

Authentication is handled through the `Auth_Accounts` table with SHA-256 password hashing.

---

## 🗂 General Structure

- On first launch, the application automatically creates the `airline.db` database and seeds it with demo data.
- Two separate login flows: **Passenger** and **Admin**.
- All logins are password-protected via the `Auth_Accounts` table.
- New Passenger accounts can be registered directly from the login screen.
- The application works directly with the main ER diagram tables:  
  `Flight`, `Route`, `Passengers`, `Employees`, `Transactions`, `AirFare`, `Airplane_type`, `Airport`, `Countries`, `Bookings`, `Tickets`, `Payments`, `Special_Requests`, `Booking_Addons`.

### Passenger Interface
- Search and filter available flights
- Select seats via interactive seat map
- Choose paid add-ons at booking time
- Simulated payment screen (card details)
- View personal trip history and ticket numbers
- Submit and track special requests

### Admin Interface
- Add, update, and delete flights
- View all bookings and transactions
- Approve or reject special requests
- Cancel or refund bookings

---

## ▶ Running the Application

```bash
python3 app.py
```

The database (`airline.db`) is created automatically on first run — no manual setup required.

> **Tkinter note:** If Tkinter is not available in your Python environment, the application will not start.  
> See `requirements.txt` for platform-specific installation instructions.

---

## 🔐 Login Information

| Role | Source | Default Password |
|---|---|---|
| Passenger | Seeded demo accounts (26 passengers) | `1234` |
| Admin | Online Sales System only | `1234` |

- Both roles are authenticated through the `Auth_Accounts` table.
- New Passenger accounts can be created from the login screen with a custom password.

---

## 🧪 Clean Reset

If an existing `airline.db` file is present, old schema or seed data may interfere.  
To perform a clean reset:

```bash
rm -f airline.db
python3 app.py
```

The application will recreate the database from scratch on next launch.

Alternatively, you can initialise the database manually using the SQL script:

```bash
sqlite3 airline.db < setup.sql
python3 app.py
```

---

## 🗄 Database

The full schema, triggers, views, and seed data are defined in `setup.sql`.

| File | Purpose |
|---|---|
| `setup.sql` | Schema definition + seed data |
| `airline.db` | Auto-generated SQLite database file |
| `app.py` | Main application (GUI + business logic) |
| `requirements.txt` | Dependency notes (stdlib only) |

**Default password for all seeded accounts:** `1234`

---

## 🛠 Requirements

- Python >= 3.9
- Tkinter (system package — not available via pip)
- SQLite (bundled with Python)

See `requirements.txt` for full details.
