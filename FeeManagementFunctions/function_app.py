
import azure.functions as func
import pyodbc
import json
import os

from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation


# All endpoints require a Function key by default.
# The health endpoint overrides this and remains anonymous.
app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)


def make_json_safe(value):
    """Convert SQL date and Decimal values into JSON-safe values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    return value


def get_fee_status(total_fee, paid_amount, due_date):
    """Calculate whether a student's fee is Paid, Overdue, or Pending."""

    balance = total_fee - paid_amount

    if balance <= 0:
        return "Paid"

    if due_date:
        due_day = due_date.date() if isinstance(due_date, datetime) else due_date

        if due_day < date.today():
            return "Overdue"

    return "Pending"


# ---------------------------------------------------------
# 1. HEALTH CHECK
# GET /api/health
# ---------------------------------------------------------

@app.route(
    route="health",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def health_check(req: func.HttpRequest) -> func.HttpResponse:

    response = {
        "status": "healthy",
        "service": "FeeManagement API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    return func.HttpResponse(
        json.dumps(response),
        status_code=200,
        mimetype="application/json"
    )


# ---------------------------------------------------------
# 2. GET STUDENT FEE STATUS
# GET /api/students/{student_id}/status
# ---------------------------------------------------------

@app.route(
    route="students/{student_id}/status",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION
)
def student_status(req: func.HttpRequest) -> func.HttpResponse:

    student_id = req.route_params.get("student_id")

    try:
        student_id = int(student_id)

        if student_id <= 0:
            raise ValueError()

    except (TypeError, ValueError):
        return func.HttpResponse(
            json.dumps({"error": "Invalid student ID"}),
            status_code=400,
            mimetype="application/json"
        )

    connection_string = os.getenv("SQL_CONNECTION_STRING")

    if not connection_string:
        return func.HttpResponse(
            json.dumps({"error": "SQL connection is not configured"}),
            status_code=500,
            mimetype="application/json"
        )

    try:
        with pyodbc.connect(connection_string, timeout=15) as connection:

            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    StudentID,
                    Name,
                    Email,
                    Course,
                    TotalFee,
                    PaidAmount,
                    DueDate
                FROM dbo.Students
                WHERE StudentID = ?
                """,
                student_id
            )

            row = cursor.fetchone()

            if row is None:
                return func.HttpResponse(
                    json.dumps({"error": "Student not found"}),
                    status_code=404,
                    mimetype="application/json"
                )

            total_fee = Decimal(str(row.TotalFee or 0))
            paid_amount = Decimal(str(row.PaidAmount or 0))
            balance = total_fee - paid_amount

            response = {
                "studentId": row.StudentID,
                "name": row.Name,
                "email": row.Email,
                "course": row.Course,
                "totalFee": float(total_fee),
                "paidAmount": float(paid_amount),
                "balance": float(balance),
                "dueDate": make_json_safe(row.DueDate),
                "status": get_fee_status(
                    total_fee,
                    paid_amount,
                    row.DueDate
                )
            }

            return func.HttpResponse(
                json.dumps(response),
                status_code=200,
                mimetype="application/json"
            )

    except pyodbc.Error:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to retrieve student details from database"
            }),
            status_code=500,
            mimetype="application/json"
        )


# ---------------------------------------------------------
# 3. GET OVERDUE STUDENTS
# GET /api/overdue?top=100&skip=0
# ---------------------------------------------------------

@app.route(
    route="overdue",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION
)
def overdue_students(req: func.HttpRequest) -> func.HttpResponse:

    connection_string = os.getenv("SQL_CONNECTION_STRING")

    if not connection_string:
        return func.HttpResponse(
            json.dumps({"error": "SQL connection is not configured"}),
            status_code=500,
            mimetype="application/json"
        )

    try:
        top = int(req.params.get("top", "100"))
        skip = int(req.params.get("skip", "0"))

        if top < 1 or top > 500 or skip < 0:
            return func.HttpResponse(
                json.dumps({
                    "error": "top must be 1-500 and skip must be non-negative"
                }),
                status_code=400,
                mimetype="application/json"
            )

        with pyodbc.connect(connection_string, timeout=15) as connection:

            cursor = connection.cursor()

            cursor.execute("EXEC dbo.sp_GetOverdueStudents")

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()

            students = []

            for row in rows:
                student = {
                    columns[i]: make_json_safe(row[i])
                    for i in range(len(columns))
                }

                students.append(student)

            total = len(students)

            paginated_students = students[skip:skip + top]

            response = {
                "total": total,
                "top": top,
                "skip": skip,
                "students": paginated_students
            }

            return func.HttpResponse(
                json.dumps(response),
                status_code=200,
                mimetype="application/json"
            )

    except ValueError:
        return func.HttpResponse(
            json.dumps({
                "error": "top and skip must be integers"
            }),
            status_code=400,
            mimetype="application/json"
        )

    except pyodbc.Error:
        return func.HttpResponse(
            json.dumps({
                "error": "Unable to retrieve overdue students"
            }),
            status_code=500,
            mimetype="application/json"
        )


# ---------------------------------------------------------
# 4. ADMIN UPDATE STUDENT FEES
# PUT /api/fees/update
#
# Request JSON:
# {
#     "studentId": 9,
#     "paidAmount": 5000
# }
# ---------------------------------------------------------

@app.route(
    route="fees/update",
    methods=["PUT"],
    auth_level=func.AuthLevel.FUNCTION
)
def admin_update(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()

        student_id = int(data.get("studentId"))
        paid_amount = Decimal(str(data.get("paidAmount")))

        if student_id <= 0 or not paid_amount.is_finite():
            raise ValueError()

        if paid_amount < 0:
            return func.HttpResponse(
                json.dumps({
                    "error": "Paid amount cannot be negative"
                }),
                status_code=400,
                mimetype="application/json"
            )

    except (
        ValueError,
        TypeError,
        InvalidOperation,
        AttributeError
    ):
        return func.HttpResponse(
            json.dumps({
                "error": "Provide a valid studentId and paidAmount"
            }),
            status_code=400,
            mimetype="application/json"
        )

    connection_string = os.getenv("SQL_CONNECTION_STRING")

    if not connection_string:
        return func.HttpResponse(
            json.dumps({"error": "SQL connection is not configured"}),
            status_code=500,
            mimetype="application/json"
        )

    try:
        with pyodbc.connect(connection_string, timeout=15) as connection:

            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT TotalFee
                FROM dbo.Students
                WHERE StudentID = ?
                """,
                student_id
            )

            row = cursor.fetchone()

            if row is None:
                return func.HttpResponse(
                    json.dumps({"error": "Student not found"}),
                    status_code=404,
                    mimetype="application/json"
                )

            total_fee = Decimal(str(row.TotalFee))

            if paid_amount > total_fee:
                return func.HttpResponse(
                    json.dumps({
                        "error": "Paid amount cannot exceed total fee",
                        "totalFee": float(total_fee)
                    }),
                    status_code=400,
                    mimetype="application/json"
                )

            cursor.execute(
                """
                UPDATE dbo.Students
                SET PaidAmount = ?
                WHERE StudentID = ?
                """,
                paid_amount,
                student_id
            )

            cursor.execute(
                """
                SELECT TotalFee, PaidAmount, DueDate
                FROM dbo.Students
                WHERE StudentID = ?
                """,
                student_id
            )

            updated = cursor.fetchone()

            total = Decimal(str(updated.TotalFee))
            paid = Decimal(str(updated.PaidAmount))
            balance = total - paid

            response = {
                "message": "Student fee updated successfully",
                "studentId": student_id,
                "totalFee": float(total),
                "paidAmount": float(paid),
                "balance": float(balance),
                "status": get_fee_status(
                    total,
                    paid,
                    updated.DueDate
                )
            }

            return func.HttpResponse(
                json.dumps(response),
                status_code=200,
                mimetype="application/json"
            )

    except pyodbc.Error:
        return func.HttpResponse(
            json.dumps({
                "error": "Database update failed"
            }),
            status_code=500,
            mimetype="application/json"
        )
