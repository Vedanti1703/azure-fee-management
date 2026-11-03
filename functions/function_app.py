"""
Azure Functions Python v2 Programming Model Entrypoint
Fee Management Microservice API
"""

import logging
import json
from decimal import Decimal
from datetime import datetime, timezone
import azure.functions as func

from shared.status import (
    InvoiceStatus,
    PaymentStatus,
    json_response,
    error_response,
)
from shared.auth import authenticate_request, require_role
from shared.db import execute_query, execute_non_query, execute_scalar

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger(__name__)


# ==============================================================================
# Health Check Endpoint
# ==============================================================================
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Verifies service responsiveness and database connectivity."""
    db_status = "UNKNOWN"
    try:
        val = execute_scalar("SELECT 1")
        if val == 1:
            db_status = "HEALTHY"
    except Exception as ex:
        db_status = f"UNHEALTHY ({str(ex)})"

    payload = {
        "service": "azure-fee-management-functions",
        "status": "UP",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return json_response(payload, status_code=200 if "HEALTHY" in db_status else 503)


# ==============================================================================
# Students Endpoints
# ==============================================================================
@app.route(route="students", methods=["GET"])
def list_students(req: func.HttpRequest) -> func.HttpResponse:
    """List students with optional course or status filtering."""
    try:
        claims = authenticate_request(req)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    status_filter = req.params.get("status", "ACTIVE")
    course_filter = req.params.get("course_id")

    sql = """
        SELECT s.student_id, s.student_code, s.first_name, s.last_name, 
               s.email, s.phone, s.current_semester, s.status,
               c.course_code, c.course_name
        FROM dbo.Students s
        INNER JOIN dbo.Courses c ON s.course_id = c.course_id
        WHERE (@status IS NULL OR s.status = @status)
          AND (@course_id IS NULL OR s.course_id = @course_id)
        ORDER BY s.student_id ASC
    """
    try:
        rows = execute_query(sql, (status_filter, course_filter))
        return json_response({"count": len(rows), "data": rows})
    except Exception as ex:
        logger.error(f"Error fetching students: {str(ex)}")
        return error_response("Failed to fetch students.", status_code=500, details=str(ex))


@app.route(route="students/{student_id}", methods=["GET"])
def get_student_details(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch student profile and invoice overview."""
    try:
        claims = authenticate_request(req)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    student_id = req.route_params.get("student_id")
    if not student_id:
        return error_response("student_id route parameter is required.", status_code=400)

    try:
        student_sql = """
            SELECT s.student_id, s.student_code, s.first_name, s.last_name, 
                   s.email, s.phone, s.current_semester, s.status,
                   c.course_id, c.course_code, c.course_name
            FROM dbo.Students s
            INNER JOIN dbo.Courses c ON s.course_id = c.course_id
            WHERE s.student_id = ?
        """
        students = execute_query(student_sql, (student_id,))
        if not students:
            return error_response(f"Student with ID {student_id} not found.", status_code=404)

        invoices_sql = """
            SELECT invoice_id, invoice_number, term_id, total_amount, paid_amount, 
                   due_amount, due_date, status
            FROM dbo.Invoices
            WHERE student_id = ?
            ORDER BY due_date DESC
        """
        invoices = execute_query(invoices_sql, (student_id,))

        result = students[0]
        result["invoices"] = invoices
        return json_response(result)
    except Exception as ex:
        logger.error(f"Error fetching student {student_id}: {str(ex)}")
        return error_response("Error loading student details.", status_code=500, details=str(ex))


# ==============================================================================
# Invoices Endpoints
# ==============================================================================
@app.route(route="invoices", methods=["GET"])
def list_invoices(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch invoices filtered by status (PENDING, OVERDUE, PAID) or student_id."""
    try:
        claims = authenticate_request(req)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    status = req.params.get("status")
    student_id = req.params.get("student_id")

    sql = """
        SELECT i.invoice_id, i.invoice_number, i.student_id, 
               s.student_code, s.first_name + ' ' + s.last_name AS student_name,
               s.email, i.term_id, t.term_name,
               i.total_amount, i.paid_amount, i.due_amount, i.due_date, i.status, i.created_at
        FROM dbo.Invoices i
        INNER JOIN dbo.Students s ON i.student_id = s.student_id
        INNER JOIN dbo.AcademicTerms t ON i.term_id = t.term_id
        WHERE (? IS NULL OR i.status = ?)
          AND (? IS NULL OR i.student_id = ?)
        ORDER BY i.due_date ASC
    """
    try:
        rows = execute_query(sql, (status, status, student_id, student_id))
        return json_response({"count": len(rows), "data": rows})
    except Exception as ex:
        logger.error(f"Error querying invoices: {str(ex)}")
        return error_response("Failed to retrieve invoices.", status_code=500, details=str(ex))


@app.route(route="invoices", methods=["POST"])
def create_invoice(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new fee invoice for a student."""
    try:
        claims = authenticate_request(req)
        if not require_role(claims, ["ADMIN", "BURSAR"]):
            return error_response("Forbidden: Requires BURSAR or ADMIN role.", status_code=403)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    try:
        body = req.get_json()
    except ValueError:
        return error_response("Invalid JSON body.", status_code=400)

    student_id = body.get("student_id")
    term_id = body.get("term_id")
    total_amount = body.get("total_amount")
    due_date = body.get("due_date")
    notes = body.get("notes", "Tuition fee invoice")

    if not all([student_id, term_id, total_amount, due_date]):
        return error_response("student_id, term_id, total_amount, and due_date are required fields.", status_code=400)

    invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{student_id}"

    sql = """
        INSERT INTO dbo.Invoices (invoice_number, student_id, term_id, total_amount, paid_amount, due_date, status, notes)
        VALUES (?, ?, ?, ?, 0.00, ?, 'PENDING', ?)
    """
    try:
        execute_non_query(sql, (invoice_number, student_id, term_id, total_amount, due_date, notes))
        return json_response({
            "message": "Invoice created successfully",
            "invoice_number": invoice_number,
            "status": "PENDING"
        }, status_code=201)
    except Exception as ex:
        logger.error(f"Error creating invoice: {str(ex)}")
        return error_response("Database failure while creating invoice.", status_code=500, details=str(ex))


# ==============================================================================
# Payments Endpoints
# ==============================================================================
@app.route(route="payments", methods=["POST"])
def record_payment(req: func.HttpRequest) -> func.HttpResponse:
    """Record a payment towards an existing invoice."""
    try:
        claims = authenticate_request(req)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    try:
        body = req.get_json()
    except ValueError:
        return error_response("Invalid JSON body.", status_code=400)

    invoice_id = body.get("invoice_id")
    amount_paid = body.get("amount_paid")
    payment_method = body.get("payment_method", "ONLINE_PORTAL")
    txn_ref = body.get("transaction_reference") or f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{invoice_id}"
    notes = body.get("notes", "Fee installment settlement")

    if not invoice_id or not amount_paid or float(amount_paid) <= 0:
        return error_response("invoice_id and positive amount_paid are required.", status_code=400)

    sql = """
        INSERT INTO dbo.Payments (transaction_reference, invoice_id, amount_paid, payment_method, payment_status, notes)
        VALUES (?, ?, ?, ?, 'SUCCESS', ?)
    """
    try:
        execute_non_query(sql, (txn_ref, invoice_id, amount_paid, payment_method, notes))
        return json_response({
            "message": "Payment recorded successfully",
            "transaction_reference": txn_ref,
            "status": "SUCCESS"
        }, status_code=201)
    except Exception as ex:
        logger.error(f"Error recording payment: {str(ex)}")
        return error_response("Failed to record payment.", status_code=500, details=str(ex))


# ==============================================================================
# Reminders Trigger Endpoint (Logic App / Cron / Manual Trigger)
# ==============================================================================
@app.route(route="reminders/trigger", methods=["POST"])
def trigger_reminders(req: func.HttpRequest) -> func.HttpResponse:
    """Finds pending/overdue invoices and returns candidates for notification dispatch."""
    try:
        claims = authenticate_request(req)
        if not require_role(claims, ["ADMIN", "BURSAR", "SYSTEM"]):
            return error_response("Forbidden: Requires BURSAR or SYSTEM role.", status_code=403)
    except ValueError as ex:
        return error_response(str(ex), status_code=401)

    sql = """
        SELECT i.invoice_id, i.invoice_number, i.due_amount, i.due_date, i.status,
               s.student_id, s.student_code, s.first_name, s.last_name, s.email
        FROM dbo.Invoices i
        INNER JOIN dbo.Students s ON i.student_id = s.student_id
        WHERE i.status IN ('PENDING', 'OVERDUE', 'PARTIAL')
          AND i.due_amount > 0
          AND i.due_date <= DATEADD(DAY, 7, CAST(GETUTCDATE() AS DATE))
    """
    try:
        candidates = execute_query(sql)
        return json_response({
            "message": "Reminder candidates identified.",
            "candidates_count": len(candidates),
            "candidates": candidates
        })
    except Exception as ex:
        logger.error(f"Error triggering reminders: {str(ex)}")
        return error_response("Failed to fetch reminder candidates.", status_code=500, details=str(ex))

