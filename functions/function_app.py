"""
Azure Functions Python v2 Programming Model Entrypoint
Student Fee Management Microservice API with Structured Observability
"""

import uuid
import time
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Tuple, Dict, Any, Optional

import azure.functions as func

from shared.status import compute_status, json_response, error_response
from shared.db import execute_one, execute_non_query, execute_query, execute_scalar
from shared.auth import get_caller

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

logger = logging.getLogger("FeeManagement.App")
audit_logger = logging.getLogger("FeeManagement.Audit")


def _get_request_id(req: func.HttpRequest) -> str:
    """Extracts client tracking ID from request headers or generates a new UUID."""
    req_id = (
        req.headers.get("x-ms-client-tracking-id")
        or req.headers.get("X-MS-Client-Tracking-Id")
        or req.headers.get("x-correlation-id")
        or req.headers.get("X-Correlation-Id")
    )
    if not req_id:
        req_id = str(uuid.uuid4())
    return req_id


def _log_structured(
    level: int,
    request_id: str,
    operation: str,
    duration_ms: Optional[float] = None,
    student_id: Optional[Any] = None,
    status_code: Optional[int] = None,
    message: Optional[str] = None,
    **extra_fields
):
    """
    Emits a structured log line using the standard logging module.
    Guarantees operation, studentId (if present), duration_ms (if present), and request_id.
    Strict privacy: Connection strings, tokens, and emails are NEVER logged.
    """
    parts = [f"request_id={request_id}", f"operation={operation}"]
    if student_id is not None:
        parts.append(f"studentId={student_id}")
    if status_code is not None:
        parts.append(f"status={status_code}")
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms:.2f}")
    if message:
        parts.append(f"msg='{message}'")
    for k, v in extra_fields.items():
        parts.append(f"{k}={v}")

    log_line = " ".join(parts)
    extra_dims = {
        "request_id": request_id,
        "operation": operation,
        "studentId": student_id,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "status_code": status_code,
    }
    logger.log(level, log_line, extra=extra_dims)


def _validate_fee_payload(
    body: Any
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """
    Validates totalFee, paidAmount, and dueDate.
    Returns (cleaned_dict, errors_dict).
    """
    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    if not isinstance(body, dict):
        return None, {"body": "Request body must be a JSON object."}

    # 1. Validate totalFee (number >= 0)
    if "totalFee" not in body or body["totalFee"] is None:
        errors["totalFee"] = "totalFee is required."
    else:
        try:
            total_fee = Decimal(str(body["totalFee"]))
            if total_fee < 0:
                errors["totalFee"] = "totalFee must be a non-negative number."
            else:
                cleaned["totalFee"] = total_fee
        except Exception:
            errors["totalFee"] = "totalFee must be a valid number."

    # 2. Validate paidAmount (number >= 0 and <= totalFee)
    if "paidAmount" not in body or body["paidAmount"] is None:
        errors["paidAmount"] = "paidAmount is required."
    else:
        try:
            paid_amount = Decimal(str(body["paidAmount"]))
            if paid_amount < 0:
                errors["paidAmount"] = "paidAmount must be a non-negative number."
            else:
                cleaned["paidAmount"] = paid_amount
        except Exception:
            errors["paidAmount"] = "paidAmount must be a valid number."

    # Cross-field check: paidAmount <= totalFee
    if "totalFee" in cleaned and "paidAmount" in cleaned:
        if cleaned["paidAmount"] > cleaned["totalFee"]:
            errors["paidAmount"] = "paidAmount cannot exceed totalFee."

    # 3. Validate dueDate (valid ISO date format YYYY-MM-DD)
    if "dueDate" not in body or body["dueDate"] is None:
        errors["dueDate"] = "dueDate is required."
    else:
        raw_date = str(body["dueDate"]).strip()
        try:
            parsed_date = date.fromisoformat(raw_date)
            cleaned["dueDate"] = parsed_date
        except Exception:
            errors["dueDate"] = "dueDate must be a valid ISO date (YYYY-MM-DD)."

    return cleaned, errors


# ==============================================================================
# Health Check Endpoint
# GET /api/health (Auth Level: ANONYMOUS)
# ==============================================================================
@app.route(
    route="health",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Anonymous health check probe running SELECT 1 against the database.
    Returns 200 if connected, 503 if database connectivity fails.
    """
    start_time = time.perf_counter()
    request_id = _get_request_id(req)
    operation = "health_check"

    try:
        val = execute_scalar("SELECT 1")
        duration_ms = (time.perf_counter() - start_time) * 1000

        if val == 1:
            _log_structured(
                logging.INFO, request_id, operation,
                duration_ms=duration_ms, status_code=200, message="Healthy"
            )
            return json_response(
                {"status": "healthy", "database": "connected"},
                status_code=200,
                headers={"x-ms-client-tracking-id": request_id}
            )
        else:
            _log_structured(
                logging.WARNING, request_id, operation,
                duration_ms=duration_ms, status_code=503, message="Unexpected DB scalar value"
            )
            return json_response(
                {"status": "unhealthy", "error": "Database connectivity check failed."},
                status_code=503,
                headers={"x-ms-client-tracking-id": request_id}
            )

    except Exception as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_id=%s operation=%s status=503 duration_ms=%.2f msg='Database health check failed: %s'",
            request_id, operation, duration_ms, str(ex)
        )
        return json_response(
            {"status": "unhealthy", "error": "Database connectivity check failed."},
            status_code=503,
            headers={"x-ms-client-tracking-id": request_id}
        )


# ==============================================================================
# Student Fee Status Endpoint
# GET /api/students/{studentId}/status (Auth Level: FUNCTION)
# ==============================================================================
@app.route(
    route="students/{studentId}/status",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION
)
def get_student_fee_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retrieves the fee status of a specific student.

    Returns JSON:
      studentId, name, totalFee, paidAmount, balance, dueDate, status

    Error responses:
      400 - If studentId is non-integer
      404 - If student is not found
      500 - Generic error message on DB/unexpected errors (logs stack trace internally)
    """
    start_time = time.perf_counter()
    request_id = _get_request_id(req)
    operation = "get_student_fee_status"
    student_id = None

    try:
        raw_student_id = req.route_params.get("studentId")

        # Validate integer student ID
        try:
            student_id = int(raw_student_id)
        except (ValueError, TypeError):
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_structured(
                logging.WARNING, request_id, operation,
                duration_ms=duration_ms, student_id=raw_student_id,
                status_code=400, message="Invalid student ID parameter"
            )
            return error_response(
                "Invalid student ID. Must be an integer.",
                status_code=400,
                headers={"x-ms-client-tracking-id": request_id}
            )

        sql = """
            SELECT StudentID, Name, TotalFee, PaidAmount, DueDate
            FROM dbo.Students
            WHERE StudentID = ?
        """
        student = execute_one(sql, (student_id,))

        duration_ms = (time.perf_counter() - start_time) * 1000

        if not student:
            _log_structured(
                logging.INFO, request_id, operation,
                duration_ms=duration_ms, student_id=student_id,
                status_code=404, message="Student not found"
            )
            return error_response(
                f"Student with ID {student_id} not found.",
                status_code=404,
                headers={"x-ms-client-tracking-id": request_id}
            )

        total_fee = student["TotalFee"]
        paid_amount = student["PaidAmount"]
        due_date = student["DueDate"]

        status = compute_status(
            total_fee=total_fee,
            paid_amount=paid_amount,
            due_date=due_date,
            today=date.today()
        )
        balance = Decimal(str(total_fee)) - Decimal(str(paid_amount))

        _log_structured(
            logging.INFO, request_id, operation,
            duration_ms=duration_ms, student_id=student_id,
            status_code=200, fee_status=status
        )

        response_payload = {
            "studentId": student["StudentID"],
            "name": student["Name"],
            "totalFee": float(total_fee),
            "paidAmount": float(paid_amount),
            "balance": float(balance),
            "dueDate": (
                due_date.isoformat()
                if hasattr(due_date, "isoformat")
                else str(due_date)
            ),
            "status": status,
        }
        return json_response(
            response_payload,
            status_code=200,
            headers={"x-ms-client-tracking-id": request_id}
        )

    except Exception as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_id=%s operation=%s studentId=%s status=500 duration_ms=%.2f msg='Unexpected exception in get_student_fee_status'",
            request_id, operation, student_id, duration_ms
        )
        return error_response(
            "An internal error occurred while processing your request.",
            status_code=500,
            headers={"x-ms-client-tracking-id": request_id}
        )


# ==============================================================================
# Admin Student Fees Update Endpoint
# PUT /api/admin/students/{studentId}/fees (Auth Level: FUNCTION)
# ==============================================================================
@app.route(
    route="admin/students/{studentId}/fees",
    methods=["PUT"],
    auth_level=func.AuthLevel.FUNCTION
)
def update_student_fees(req: func.HttpRequest) -> func.HttpResponse:
    """
    Updates totalFee, paidAmount, and dueDate for a student.

    Permissions:
      - 401 if no valid caller
      - 403 unless caller roles contain 'Admin'

    Validation:
      - numbers >= 0, paidAmount <= totalFee, dueDate valid ISO date
      - 400 with field-level errors

    Database:
      - Parameterized UPDATE
      - 404 if no row found
      - Writes audit log line (admin oid, studentId, old values, new values) with NO PII beyond IDs
      - Returns updated record with recomputed status
    """
    start_time = time.perf_counter()
    request_id = _get_request_id(req)
    operation = "update_student_fees"
    student_id = None

    try:
        # 1. Caller Authentication
        try:
            admin_oid, roles = get_caller(req)
        except Exception as ex:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("request_id=%s operation=%s status=401 msg='Authentication failure: %s'", request_id, operation, ex)
            return error_response(
                "Unauthorized: Invalid credentials.",
                status_code=401,
                headers={"x-ms-client-tracking-id": request_id}
            )

        if not admin_oid:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("request_id=%s operation=%s status=401 msg='Missing or invalid caller'", request_id, operation)
            return error_response(
                "Unauthorized: Missing or invalid authentication.",
                status_code=401,
                headers={"x-ms-client-tracking-id": request_id}
            )

        # 2. Role Check: Must contain 'Admin'
        if "Admin" not in roles:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("request_id=%s operation=%s admin_oid=%s status=403 msg='Missing Admin role'", request_id, operation, admin_oid)
            return error_response(
                "Forbidden: Requires 'Admin' role.",
                status_code=403,
                headers={"x-ms-client-tracking-id": request_id}
            )

        # 3. Route Parameter Validation
        raw_student_id = req.route_params.get("studentId")
        try:
            student_id = int(raw_student_id)
        except (ValueError, TypeError):
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_structured(
                logging.WARNING, request_id, operation,
                duration_ms=duration_ms, student_id=raw_student_id,
                status_code=400, message="Non-integer student ID in route"
            )
            return json_response({
                "error": "Validation failed",
                "errors": {"studentId": "studentId must be an integer."}
            }, status_code=400, headers={"x-ms-client-tracking-id": request_id})

        # 4. Request Body Parsing & Field-Level Validation
        try:
            body = req.get_json()
        except ValueError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_structured(
                logging.WARNING, request_id, operation,
                duration_ms=duration_ms, student_id=student_id,
                status_code=400, message="Malformed JSON body"
            )
            return error_response(
                "Invalid JSON in request body.",
                status_code=400,
                headers={"x-ms-client-tracking-id": request_id}
            )

        cleaned_data, errors = _validate_fee_payload(body)
        if errors:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_structured(
                logging.WARNING, request_id, operation,
                duration_ms=duration_ms, student_id=student_id,
                status_code=400, message="Fee payload validation failed"
            )
            return json_response({
                "error": "Validation failed",
                "errors": errors
            }, status_code=400, headers={"x-ms-client-tracking-id": request_id})

        total_fee: Decimal = cleaned_data["totalFee"]
        paid_amount: Decimal = cleaned_data["paidAmount"]
        due_date: date = cleaned_data["dueDate"]

        # 5. Fetch existing student record
        select_sql = """
            SELECT StudentID, Name, TotalFee, PaidAmount, DueDate
            FROM dbo.Students
            WHERE StudentID = ?
        """
        old_row = execute_one(select_sql, (student_id,))

        if not old_row:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_structured(
                logging.INFO, request_id, operation,
                duration_ms=duration_ms, student_id=student_id,
                status_code=404, message="Student not found for fee update"
            )
            return error_response(
                f"Student with ID {student_id} not found.",
                status_code=404,
                headers={"x-ms-client-tracking-id": request_id}
            )

        # 6. Parameterized UPDATE
        update_sql = """
            UPDATE dbo.Students
            SET TotalFee = ?, PaidAmount = ?, DueDate = ?
            WHERE StudentID = ?
        """
        execute_non_query(update_sql, (total_fee, paid_amount, due_date, student_id))

        # 7. Write Audit Log Line (Admin OID, StudentID, Old Values, New Values - NO PII beyond IDs)
        old_due = old_row["DueDate"]
        old_due_str = old_due.isoformat() if hasattr(old_due, "isoformat") else str(old_due)

        old_values = {
            "totalFee": float(old_row["TotalFee"]),
            "paidAmount": float(old_row["PaidAmount"]),
            "dueDate": old_due_str
        }
        new_values = {
            "totalFee": float(total_fee),
            "paidAmount": float(paid_amount),
            "dueDate": due_date.isoformat()
        }

        audit_logger.info(
            "request_id=%s operation=%s admin_oid=%s studentId=%d old_values=%s new_values=%s",
            request_id, operation, admin_oid, student_id, old_values, new_values
        )

        # 8. Recompute Status & Return
        status = compute_status(
            total_fee=total_fee,
            paid_amount=paid_amount,
            due_date=due_date,
            today=date.today()
        )
        balance = total_fee - paid_amount

        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_structured(
            logging.INFO, request_id, operation,
            duration_ms=duration_ms, student_id=student_id,
            status_code=200, fee_status=status
        )

        response_payload = {
            "studentId": student_id,
            "name": old_row["Name"],
            "totalFee": float(total_fee),
            "paidAmount": float(paid_amount),
            "balance": float(balance),
            "dueDate": due_date.isoformat(),
            "status": status,
        }
        return json_response(
            response_payload,
            status_code=200,
            headers={"x-ms-client-tracking-id": request_id}
        )

    except Exception as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_id=%s operation=%s studentId=%s status=500 duration_ms=%.2f msg='Unexpected exception in update_student_fees'",
            request_id, operation, student_id, duration_ms
        )
        return error_response(
            "An internal error occurred while processing your request.",
            status_code=500,
            headers={"x-ms-client-tracking-id": request_id}
        )


# ==============================================================================
# Overdue Students Query Endpoint
# GET /api/overdue (Auth Level: FUNCTION)
# ==============================================================================
@app.route(
    route="overdue",
    methods=["GET"],
    auth_level=func.AuthLevel.FUNCTION
)
def get_overdue_students(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns paginated list of overdue students via sp_GetOverdueStudents.
    Query parameters:
      top: default 100, max 500
      skip: default 0
    Returns JSON:
      { count, students: [{ studentId, name, email, balance, dueDate, daysOverdue }] }
    """
    start_time = time.perf_counter()
    request_id = _get_request_id(req)
    operation = "get_overdue_students"

    try:
        raw_top = req.params.get("top")
        raw_skip = req.params.get("skip")

        top = 100
        if raw_top is not None:
            try:
                top = int(raw_top)
                if top <= 0:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    _log_structured(
                        logging.WARNING, request_id, operation,
                        duration_ms=duration_ms, status_code=400, message="Non-positive top parameter"
                    )
                    return error_response(
                        "Query parameter 'top' must be a positive integer.",
                        status_code=400,
                        headers={"x-ms-client-tracking-id": request_id}
                    )
                if top > 500:
                    top = 500
            except (ValueError, TypeError):
                duration_ms = (time.perf_counter() - start_time) * 1000
                _log_structured(
                    logging.WARNING, request_id, operation,
                    duration_ms=duration_ms, status_code=400, message="Invalid top parameter"
                )
                return error_response(
                    "Query parameter 'top' must be an integer.",
                    status_code=400,
                    headers={"x-ms-client-tracking-id": request_id}
                )

        skip = 0
        if raw_skip is not None:
            try:
                skip = int(raw_skip)
                if skip < 0:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    _log_structured(
                        logging.WARNING, request_id, operation,
                        duration_ms=duration_ms, status_code=400, message="Negative skip parameter"
                    )
                    return error_response(
                        "Query parameter 'skip' must be greater than or equal to 0.",
                        status_code=400,
                        headers={"x-ms-client-tracking-id": request_id}
                    )
            except (ValueError, TypeError):
                duration_ms = (time.perf_counter() - start_time) * 1000
                _log_structured(
                    logging.WARNING, request_id, operation,
                    duration_ms=duration_ms, status_code=400, message="Invalid skip parameter"
                )
                return error_response(
                    "Query parameter 'skip' must be an integer.",
                    status_code=400,
                    headers={"x-ms-client-tracking-id": request_id}
                )

        sql = "EXEC dbo.sp_GetOverdueStudents @Top = ?, @Skip = ?"
        rows = execute_query(sql, (top, skip))

        today = date.today()
        students_list = []

        for row in rows:
            raw_due = row["DueDate"]
            if isinstance(raw_due, datetime):
                due_d = raw_due.date()
            elif isinstance(raw_due, str):
                due_d = date.fromisoformat(raw_due)
            else:
                due_d = raw_due

            days_overdue = max(0, (today - due_d).days)
            balance = float(row.get("BalanceAmount", Decimal(str(row["TotalFee"])) - Decimal(str(row["PaidAmount"]))))

            students_list.append({
                "studentId": row["StudentID"],
                "name": row["Name"],
                "email": row["Email"],
                "balance": balance,
                "dueDate": due_d.isoformat(),
                "daysOverdue": days_overdue
            })

        duration_ms = (time.perf_counter() - start_time) * 1000
        # Privacy: Never log individual student emails or PII in the structured log
        _log_structured(
            logging.INFO, request_id, operation,
            duration_ms=duration_ms, status_code=200, count=len(students_list)
        )

        return json_response({
            "count": len(students_list),
            "students": students_list
        }, status_code=200, headers={"x-ms-client-tracking-id": request_id})

    except Exception as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_id=%s operation=%s status=500 duration_ms=%.2f msg='Unexpected exception in get_overdue_students'",
            request_id, operation, duration_ms
        )
        return error_response(
            "An internal error occurred while processing your request.",
            status_code=500,
            headers={"x-ms-client-tracking-id": request_id}
        )
