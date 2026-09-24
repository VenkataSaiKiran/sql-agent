"""
Database Seeding Script: Creates and seeds demo.db with sample data matching
the reference schema: Customer, Product, and Order tables using US names and cities.
"""
import sqlite3
import random
from datetime import date, timedelta

DB_PATH = "demo.db"

CITIES = ["Austin", "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Seattle"]
FIRST_NAMES = [
    "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
    "Alexander", "Mia", "William", "Isabella", "Benjamin", "Charlotte", "Mason", "Amelia"
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson"
]
PRODUCTS = [
    ("Wireless Mouse", 29.99, "Electronics"),
    ("Mechanical Keyboard", 129.99, "Electronics"),
    ("USB-C Hub", 49.99, "Electronics"),
    ("Office Chair", 299.99, "Furniture"),
    ("Standing Desk", 599.99, "Furniture"),
    ("Notebook Set", 14.99, "Stationery"),
    ("Fountain Pen", 24.99, "Stationery"),
    ("Bluetooth Speaker", 79.99, "Electronics"),
    ("Desk Lamp", 39.99, "Furniture"),
    ("Water Bottle", 19.99, "Accessories"),
]
STATUSES = ["completed", "pending", "cancelled", "completed", "completed"]


def seed():
    """
    Drops existing tables, creates Customer, Product, and Order schema,
    and populates them with sample customer, product, and order records.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS "Order";
    DROP TABLE IF EXISTS Product;
    DROP TABLE IF EXISTS Customer;

    CREATE TABLE Customer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        city TEXT NOT NULL,
        joined_date TEXT NOT NULL
    );

    CREATE TABLE Product (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        category TEXT NOT NULL
    );

    CREATE TABLE "Order" (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES Customer(id),
        FOREIGN KEY (product_id) REFERENCES Product(id)
    );
    """)

    # Seed customers (weighted towards Austin for default demo question)
    start = date(2023, 1, 1)
    customers = []
    for i in range(60):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        city = "Austin" if i < 11 else random.choice(CITIES)
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        joined = start + timedelta(days=random.randint(0, 800))
        customers.append((name, email, city, joined.isoformat()))
    cur.executemany("INSERT INTO Customer (name, email, city, joined_date) VALUES (?, ?, ?, ?)", customers)

    cur.executemany("INSERT INTO Product (name, price, category) VALUES (?, ?, ?)", PRODUCTS)

    cur.execute("SELECT id FROM Customer")
    customer_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM Product")
    product_ids = [r[0] for r in cur.fetchall()]

    # Seed order records
    orders = []
    for _ in range(200):
        cid = random.choice(customer_ids)
        pid = random.choice(product_ids)
        qty = random.randint(1, 5)
        odate = start + timedelta(days=random.randint(0, 800))
        status = random.choice(STATUSES)
        orders.append((cid, pid, qty, odate.isoformat(), status))
    cur.executemany(
        'INSERT INTO "Order" (customer_id, product_id, quantity, order_date, status) VALUES (?, ?, ?, ?, ?)',
        orders,
    )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with {len(customers)} customers, {len(PRODUCTS)} products, {len(orders)} orders.")


if __name__ == "__main__":
    seed()