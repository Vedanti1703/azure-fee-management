"""
Fee status computation and response formatting utilities.
"""

from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, Optional, Union
import json
import azure.functions as func


def compute_status(
    total_fee: Union[Decimal, float, int, str],
    paid_amount: Union[Decimal, float, int, str],
    due_date: Union[date, datetime, str],
    today: Union[date, datetime, str]
) -> str:
    """
    Pure function to determine a student's fee payment status.

    Rules:
    - "Paid": if paid_amount >= total_fee
    - "Overdue": if due_date < today and paid_amount < total_fee
    - "Partially Paid": if 0 < paid_amount < total_fee (and not overdue, i.e. due_date >= today)
    - "Pending": otherwise (e.g. paid_amount == 0 and due_date >= today)
    """
    # Normalize numeric values to Decimal for exact precision
    total = Decimal(str(total_fee))
    paid = Decimal(str(paid_amount))

    # Normalize dates
    if isinstance(due_date, datetime):
        due_d = due_date.date()
    elif isinstance(due_date, str):
        due_d = date.fromisoformat(due_date)
    else:
        due_d = due_date

    if isinstance(today, datetime):
        curr_d = today.date()
    elif isinstance(today, str):
        curr_d = date.fromisoformat(today)
    else:
        curr_d = today

    # 1. Paid in full or overpaid (also covers zero fee when paid == 0)
    if paid >= total:
        return "Paid"

    # 2. Overdue if past due date and not fully paid
    if due_d < curr_d and paid < total:
        return "Overdue"

    # 3. Partially paid if some payment was made and not overdue (due_date >= today)
    if Decimal("0") < paid < total:
        return "Partially Paid"

    # 4. Otherwise pending (e.g. 0 paid and due today or in the future)
    return "Pending"


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes custom Python objects like Decimal, datetime, and date to JSON."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def json_response(
    data: Any,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """Builds a standardized application/json HttpResponse."""
    default_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        default_headers.update(headers)

    body = json.dumps(data, cls=CustomJSONEncoder)
    return func.HttpResponse(body=body, status_code=status_code, headers=default_headers)


def error_response(
    message: str,
    status_code: int = 400,
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """Builds a JSON error HttpResponse."""
    return json_response({"error": message}, status_code=status_code, headers=headers)
