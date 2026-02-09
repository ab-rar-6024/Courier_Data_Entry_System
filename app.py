from flask import Flask, render_template, request, redirect, session, send_file
from db import get_db_connection
import pandas as pd

app = Flask(__name__)
app.secret_key = "secretkey123"


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (request.form["username"], request.form["password"])
        )
        user = cursor.fetchone()

        if user:
            session["user"] = request.form["username"]
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid Login")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")


# ---------------- ZONE ENTRY ----------------
@app.route("/zone-entry", methods=["GET", "POST"])
def zone_entry():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        cursor.execute(
            "INSERT INTO zones (district, rate_zone) VALUES (%s,%s)",
            (request.form["district"], request.form["rate_zone"])
        )
        db.commit()
        return redirect("/zone-entry")

    cursor.execute("SELECT * FROM zones ORDER BY id DESC")
    zones = cursor.fetchall()
    return render_template("zone_entry.html", zones=zones)


# ---------------- RATE ENTRY ----------------
@app.route("/rate-entry", methods=["GET", "POST"])
def rate_entry():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        cursor.execute("""
            INSERT INTO rates
            (code, code_fullform, place, rate_250g, rate_500g, rate_500g_1,
             rate_1_to_3kg, rate_3_to_10kg, rate_above_10kg, fuel)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["code"],
            request.form["code_fullform"],
            request.form["place"],
            request.form["rate_250g"],
            request.form["rate_500g"],
            request.form["rate_500g_1"],
            request.form["rate_1_to_3kg"],
            request.form["rate_3_to_10kg"],
            request.form["rate_above_10kg"],
            request.form["fuel"]
        ))
        db.commit()
        return redirect("/rate-entry")

    cursor.execute("SELECT * FROM rates ORDER BY id DESC")
    rates = cursor.fetchall()
    return render_template("rate_entry.html", rates=rates)


# ---------------- BOOKING ENTRY ----------------
@app.route("/booking-entry", methods=["GET", "POST"])
def booking_entry():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        auto_amount = float(request.form["auto_amount"] or 0)
        fuel = float(request.form["fuel"] or 0)
        total_amount = auto_amount + fuel

        cursor.execute("""
            INSERT INTO bookings
            (code, booking_date, awb_no, destination, weight, courier, zone,
             auto_amount, fuel, total_amount, client_name, inv_no, inv_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["code"],
            request.form["booking_date"],
            request.form["awb_no"],
            request.form["destination"],
            float(request.form["weight"] or 0),
            request.form["courier"],
            request.form["zone"],
            auto_amount,
            fuel,
            total_amount,
            request.form["client_name"],
            request.form["inv_no"],
            request.form["inv_date"]
        ))

        db.commit()
        return redirect("/booking-entry")

    cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC")
    bookings = cursor.fetchall()
    return render_template("booking_entry.html", bookings=bookings)


# ---------------- INVOICE / STATEMENT ----------------
@app.route("/invoice", methods=["GET", "POST"])
def invoice():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    from_date = request.form.get("from_date")
    to_date = request.form.get("to_date")
    code = request.form.get("code")

    query = """
        SELECT booking_date, destination, awb_no, weight, total_amount
        FROM bookings WHERE 1=1
    """
    params = []

    if from_date and to_date:
        query += " AND booking_date BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    if code and code != "ALL":
        query += " AND code=%s"
        params.append(code)

    query += " ORDER BY booking_date"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_sum = sum(r["total_amount"] for r in rows)

    cursor.execute("SELECT DISTINCT code FROM bookings")
    codes = cursor.fetchall()

    return render_template(
        "invoice.html",
        rows=rows,
        total_sum=total_sum,
        codes=codes,
        from_date=from_date,
        to_date=to_date,
        selected_code=code
    )

# ---------------- SALES CHECKING ----------------
@app.route("/sales-checking", methods=["GET", "POST"])
def sales_checking():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    client_name = request.form.get("client_name")
    awb_no = request.form.get("awb_no")
    destination = request.form.get("destination")
    from_date = request.form.get("from_date")
    to_date = request.form.get("to_date")

    query = """
        SELECT
            client_name,
            awb_no,
            destination,
            COUNT(*) AS sum_count,
            SUM(total_amount) AS amount
        FROM bookings
        WHERE 1=1
    """
    params = []

    if client_name:
        query += " AND client_name LIKE %s"
        params.append(f"%{client_name}%")

    if awb_no:
        query += " AND awb_no LIKE %s"
        params.append(f"%{awb_no}%")

    if destination:
        query += " AND destination LIKE %s"
        params.append(f"%{destination}%")

    if from_date and to_date:
        query += " AND booking_date BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    query += """
        GROUP BY client_name, awb_no, destination
        ORDER BY client_name
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_amount = sum(r["amount"] for r in rows) if rows else 0

    return render_template(
        "sales_checking.html",
        rows=rows,
        total_amount=total_amount,
        filters=request.form
    )

# ---------------- DAY WISE ----------------
@app.route("/day-wise", methods=["GET", "POST"])
def day_wise():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # SAVE MANUAL ENTRY
    if request.method == "POST" and "save" in request.form:
        entry_date = request.form["entry_date"]
        total_weight = float(request.form["total_weight"] or 0)
        total_sales = float(request.form["total_sales"] or 0)

        cursor.execute("""
            INSERT INTO day_wise (entry_date, total_weight, total_sales)
            VALUES (%s,%s,%s)
        """, (entry_date, total_weight, total_sales))
        db.commit()

        return redirect("/day-wise")

    # FILTER
    from_date = request.form.get("from_date")
    to_date = request.form.get("to_date")

    query = "SELECT * FROM day_wise WHERE 1=1"
    params = []

    if from_date and to_date:
        query += " AND entry_date BETWEEN %s AND %s"
        params.extend([from_date, to_date])

    query += " ORDER BY entry_date"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    grand_weight = sum(r["total_weight"] for r in rows) if rows else 0
    grand_sales = sum(r["total_sales"] for r in rows) if rows else 0

    return render_template(
        "day_wise.html",
        rows=rows,
        from_date=from_date,
        to_date=to_date,
        grand_weight=grand_weight,
        grand_sales=grand_sales
    )

# ---------------- DAY BOOK ----------------
@app.route("/day-book", methods=["GET", "POST"])
def day_book():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    entry_date = request.form.get("entry_date")
    weight = request.form.get("weight")
    awb_no = request.form.get("awb_no")
    destination = request.form.get("destination")

    query = """
        SELECT
            weight,
            awb_no,
            destination,
            total_amount
        FROM bookings
        WHERE 1=1
    """
    params = []

    if entry_date:
        query += " AND booking_date = %s"
        params.append(entry_date)

    if weight:
        query += " AND weight = %s"
        params.append(weight)

    if awb_no:
        query += " AND awb_no LIKE %s"
        params.append(f"%{awb_no}%")

    if destination:
        query += " AND destination LIKE %s"
        params.append(f"%{destination}%")

    query += " ORDER BY awb_no"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_sum = sum(r["total_amount"] for r in rows) if rows else 0

    return render_template(
        "day_book.html",
        rows=rows,
        total_sum=total_sum,
        entry_date=entry_date,
        weight=weight,
        awb_no=awb_no,
        destination=destination
    )


# ---------------- INVOICE EXPORT ----------------
@app.route("/invoice-export", methods=["POST"])
def invoice_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            booking_date AS `DATE`,
            destination AS `DESTINATION`,
            awb_no AS `AWB NO`,
            weight AS `WEIGHT`,
            total_amount AS `Total`
        FROM bookings WHERE 1=1
    """
    params = []

    if request.form.get("from_date") and request.form.get("to_date"):
        query += " AND booking_date BETWEEN %s AND %s"
        params.extend([request.form["from_date"], request.form["to_date"]])

    if request.form.get("code") and request.form["code"] != "ALL":
        query += " AND code=%s"
        params.append(request.form["code"])

    cursor.execute(query, params)
    data = cursor.fetchall()

    df = pd.DataFrame(data)
    file_name = "Invoice_Statement.xlsx"
    df.to_excel(file_name, index=False)

    return send_file(file_name, as_attachment=True)


# ---------------- EXPORTS ----------------
@app.route("/zone-export")
def zone_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT district, rate_zone FROM zones")
    df = pd.DataFrame(cursor.fetchall())
    df.to_excel("Zone_Data.xlsx", index=False)
    return send_file("Zone_Data.xlsx", as_attachment=True)


@app.route("/rate-export")
def rate_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            code AS `CODE`,
            code_fullform AS `CODE FULL FORM`,
            place AS `PLACE`,
            rate_250g AS `250 G Dx`,
            rate_500g AS `0.500 g`,
            rate_500g_1 AS `0.500 g 1`,
            rate_1_to_3kg AS `Add 1 to 3 Kg`,
            rate_3_to_10kg AS `Above 3-10 Kg`,
            rate_above_10kg AS `Above 10 Kg`,
            fuel AS `Fuel`
        FROM rates
    """)
    df = pd.DataFrame(cursor.fetchall())
    df.to_excel("Rate_Entry.xlsx", index=False)
    return send_file("Rate_Entry.xlsx", as_attachment=True)


@app.route("/booking-export")
def booking_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            code AS `CODE`,
            booking_date AS `DATE`,
            awb_no AS `AWB NO`,
            destination AS `DESTINATION`,
            weight AS `WEIGHT`,
            courier AS `COURIER`,
            zone AS `ZONE`,
            auto_amount AS `Auto Amount`,
            fuel AS `Fuel`,
            total_amount AS `Total Amount`,
            client_name AS `Client Name`,
            inv_no AS `INV NO`,
            inv_date AS `INV DATE`
        FROM bookings
    """)
    df = pd.DataFrame(cursor.fetchall())
    df.to_excel("Booking_Data.xlsx", index=False)
    return send_file("Booking_Data.xlsx", as_attachment=True)

@app.route("/sales-export", methods=["POST"])
def sales_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            client_name AS `Client Name`,
            awb_no AS `AWB No`,
            destination AS `Destination`,
            COUNT(*) AS `Sum`,
            SUM(total_amount) AS `Amount`
        FROM bookings
        WHERE 1=1
    """
    params = []

    if request.form.get("client_name"):
        query += " AND client_name LIKE %s"
        params.append(f"%{request.form['client_name']}%")

    if request.form.get("awb_no"):
        query += " AND awb_no LIKE %s"
        params.append(f"%{request.form['awb_no']}%")

    if request.form.get("destination"):
        query += " AND destination LIKE %s"
        params.append(f"%{request.form['destination']}%")

    if request.form.get("from_date") and request.form.get("to_date"):
        query += " AND booking_date BETWEEN %s AND %s"
        params.extend([request.form["from_date"], request.form["to_date"]])

    query += " GROUP BY client_name, awb_no, destination"

    cursor.execute(query, params)
    data = cursor.fetchall()

    df = pd.DataFrame(data)
    file_name = "Sales_Checking.xlsx"
    df.to_excel(file_name, index=False)

    return send_file(file_name, as_attachment=True)

@app.route("/day-wise-export", methods=["POST"])
def day_wise_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            entry_date AS `DATE`,
            total_weight AS `Total Weight`,
            total_sales AS `Total Sales Amount`
        FROM day_wise
        WHERE 1=1
    """
    params = []

    if request.form.get("from_date") and request.form.get("to_date"):
        query += " AND entry_date BETWEEN %s AND %s"
        params.extend([request.form["from_date"], request.form["to_date"]])

    query += " ORDER BY entry_date"

    cursor.execute(query, params)
    data = cursor.fetchall()

    df = pd.DataFrame(data)
    file_name = "Day_Wise_Manual.xlsx"
    df.to_excel(file_name, index=False)

    return send_file(file_name, as_attachment=True)

@app.route("/day-book-export", methods=["POST"])
def day_book_export():
    if "user" not in session:
        return redirect("/")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            weight AS `WEIGHT`,
            awb_no AS `AWB NO`,
            destination AS `DESTINATION`,
            total_amount AS `Total`
        FROM bookings
        WHERE 1=1
    """
    params = []

    if request.form.get("entry_date"):
        query += " AND booking_date = %s"
        params.append(request.form["entry_date"])

    if request.form.get("weight"):
        query += " AND weight = %s"
        params.append(request.form["weight"])

    if request.form.get("awb_no"):
        query += " AND awb_no LIKE %s"
        params.append(f"%{request.form['awb_no']}%")

    if request.form.get("destination"):
        query += " AND destination LIKE %s"
        params.append(f"%{request.form['destination']}%")

    cursor.execute(query, params)
    data = cursor.fetchall()

    import pandas as pd
    df = pd.DataFrame(data)
    file_name = "Day_Book.xlsx"
    df.to_excel(file_name, index=False)

    from flask import send_file
    return send_file(file_name, as_attachment=True)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
