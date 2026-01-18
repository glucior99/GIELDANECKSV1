import sqlite3
from flask import Flask, render_template, request, redirect, session, flash
import statistics

app = Flask(__name__)
app.secret_key = "supersecret"
DB_NAME = "database.db"


def db():
    return sqlite3.connect(DB_NAME, timeout=10)


def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            exchange_id INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            material_id INTEGER,
            price REAL
        )
    """)
    con.commit()
    con.close()


init_db()

# ---------- AUTH ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        if u == "admin" and p == "admin":
            session["user"] = "admin"
            return redirect("/admin")

        con = db()
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        if cur.fetchone():
            session["user"] = u
            return redirect("/user")
        flash("Błędny login lub hasło")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        con = db()
        cur = con.cursor()
        try:
            cur.execute(
                "INSERT INTO users VALUES (NULL,?,?)",
                (request.form["username"], request.form["password"])
            )
            con.commit()
            con.close()
            return redirect("/")
        except:
            con.close()
            return "Użytkownik już istnieje"
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- USER ----------
@app.route("/user")
def user():
    if "user" not in session or session["user"] == "admin":
        return redirect("/")

    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM exchanges")
    exchanges = cur.fetchall()

    exchange_data = []

    for ex in exchanges:
        cur.execute("SELECT * FROM materials WHERE exchange_id=?", (ex[0],))
        mats = cur.fetchall()
        materials = []

        for m in mats:
            cur.execute(
                "SELECT price FROM prices WHERE material_id=? AND user=?",
                (m[0], session["user"])
            )
            row = cur.fetchone()
            my_price = row[0] if row else None

            cur.execute(
                "SELECT price FROM prices WHERE material_id=? ORDER BY price ASC",
                (m[0],)
            )
            all_prices = [r[0] for r in cur.fetchall()]

            rank = "-"
            if my_price and all_prices:
                if all_prices.count(my_price) > 1:
                    rank = "REMIS"
                else:
                    rank = all_prices.index(my_price) + 1

            materials.append((m[0], m[1], my_price, rank))

        exchange_data.append((ex[0], ex[1], materials))

    return render_template("user.html", exchange_data=exchange_data)


@app.route("/add_price/<int:mid>", methods=["POST"])
def add_price(mid):
    try:
        price = float(request.form["price"])
    except:
        return redirect("/user")

    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT * FROM prices WHERE material_id=? AND user=?",
        (mid, session["user"])
    )
    if cur.fetchone():
        cur.execute(
            "UPDATE prices SET price=? WHERE material_id=? AND user=?",
            (price, mid, session["user"])
        )
    else:
        cur.execute(
            "INSERT INTO prices VALUES (NULL,?,?,?)",
            (session["user"], mid, price)
        )

    con.commit()
    con.close()
    return redirect("/user")


# ---------- ADMIN ----------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("user") != "admin":
        return redirect("/")

    con = db()
    cur = con.cursor()

    if "exchange_name" in request.form:
        cur.execute("INSERT INTO exchanges VALUES (NULL,?)", (request.form["exchange_name"],))
        con.commit()

    if "material_name" in request.form:
        cur.execute(
            "INSERT INTO materials VALUES (NULL,?,?)",
            (request.form["material_name"], request.form["exchange_id"])
        )
        con.commit()

    cur.execute("SELECT * FROM exchanges")
    exchanges = cur.fetchall()

    exchange_data = []
    stats_by_exchange = {}

    for ex in exchanges:
        cur.execute("SELECT * FROM materials WHERE exchange_id=?", (ex[0],))
        mats = cur.fetchall()
        exchange_data.append((ex[0], ex[1], mats))

        stats = []
        for m in mats:
            cur.execute("SELECT price FROM prices WHERE material_id=?", (m[0],))
            prices = [p[0] for p in cur.fetchall()]
            if not prices:
                continue

            avg = round(sum(prices) / len(prices), 2)
            std = round(statistics.stdev(prices), 2) if len(prices) > 1 else 0
            max_p = max(prices)
            min_p = min(prices)

            cur.execute("SELECT user, price FROM prices WHERE material_id=?", (m[0],))
            for u, p in cur.fetchall():
                drop = round((max_p - p) / max_p * 100, 2)
                stats.append((m[1], u, p, avg, std, max_p, min_p, drop))

        stats_by_exchange[ex[0]] = stats

    con.close()
    return render_template(
        "admin.html",
        exchange_data=exchange_data,
        stats_by_exchange=stats_by_exchange
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
