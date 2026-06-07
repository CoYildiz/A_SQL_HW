# AIRLINE MANAGEMENT SYSTEM PROJECT

A role-based airline management system demo application built with Python and SQLite.

## Describing Project Idea

This project is designed to simulate the core functionality of an airline management system. It separates users into two main roles: **Passenger** and **Admin**. Passengers can search for flights, create reservation requests, and track their own requests. Admin users can manage operational data such as flights, countries, airports, routes, airplane types, airfares, and transaction records.

The system is connected directly to the main database tables defined in the ER diagram and uses a password-based authentication structure for secure login.

## General Structure

- When the application is launched for the first time, it automatically runs the `setup.sql` file and creates the `airline.db` database.
- There are two separate login flows: **Passenger** and **Admin**.
- All logins are password protected through the `Auth_Accounts` table.
- The Passenger interface includes flight search, reservation request creation, and request tracking features.
- The Admin interface includes management of flights, countries, airports, routes, airplane types, airfares, and transactions.
- New Passenger accounts can be created from the login screen.
- The application works directly with the main tables in the ER diagram: `Flight`, `Route`, `Passengers`, `Employees`, `Transactions`, `AirFare`, `Airplane_type`, `Airport`, and `Countries`.

## Running the Application

Run the following command:

```bash
python3 app.py
```

If Tkinter support is not installed in your Python environment, the application will not start. In that case, you need to install the required system package.

## Login Information

- The system supports two roles: `Passenger` and `Admin`.
- Both roles are authenticated through the `Auth_Accounts` table.
- Default password for seeded accounts: `1234`.
- You can also create a new `Passenger` account directly from the login screen.

## Clean Test (Reset)

If an older database file already exists, the updated schema or seed data may not appear correctly.

For a clean installation, run:

```bash
rm -f airline.db
python3 app.py
```

After this, the application will rerun `setup.sql` and recreate the database from scratch.

## Database

The schema and seed data are defined in [`setup.sql`](setup.sql). The database file is created automatically, so no manual database setup is required.

Default password for seeded users: `1234`.


