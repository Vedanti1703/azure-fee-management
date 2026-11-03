#!/usr/bin/env python3
"""
Local Fee Reminder Dispatcher Script
Queries overdue or upcoming fee invoices and sends reminder emails via Mailpit SMTP.
Configuration is loaded strictly from environment variables.
"""

import os
import sys
import smtplib
import argparse
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import List, Dict, Any

# Ensure functions/ is in the python path to reuse shared db helpers if available
script_dir = os.path.dirname(os.path.abspath(__file__))
functions_dir = os.path.join(script_dir, "..", "functions")
if functions_dir not in sys.path:
    sys.path.insert(0, functions_dir)

try:
    from shared.db import execute_query, execute_non_query
except ImportError:
    execute_query = None
    execute_non_query = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("FeeReminderScript")

# Environment Configurations
SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "false").lower() in ("true", "1", "yes")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "billing@university.edu")
SENDER_NAME = os.environ.get("SENDER_NAME", "Student Accounts Office")


def fetch_candidates_from_db(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Query invoices that are overdue or due within the specified window."""
    if execute_query is None:
        raise RuntimeError("shared.db module could not be imported. Ensure pyodbc is installed.")

    sql = """
        SELECT i.invoice_id, i.invoice_number, i.due_amount, i.total_amount, i.paid_amount,
               i.due_date, i.status, s.student_id, s.student_code, s.first_name, s.last_name, s.email
        FROM dbo.Invoices i
        INNER JOIN dbo.Students s ON i.student_id = s.student_id
        WHERE i.status IN ('PENDING', 'OVERDUE', 'PARTIAL')
          AND i.due_amount > 0
          AND i.due_date <= DATEADD(DAY, ?, CAST(GETUTCDATE() AS DATE))
        ORDER BY i.due_date ASC
    """
    return execute_query(sql, (days_ahead,))


def build_email_message(student: Dict[str, Any], dry_run: bool = False) -> MIMEMultipart:
    """Builds multipart MIME email message with HTML and plain text bodies."""
    recipient_email = student["email"]
    student_name = f"{student['first_name']} {student['last_name']}"
    invoice_number = student["invoice_number"]
    due_amount = f"${float(student['due_amount']):,.2f}"
    due_date = str(student["due_date"])
    is_overdue = student["status"] == "OVERDUE"

    subject_prefix = "[URGENT OVERDUE]" if is_overdue else "[PAYMENT REMINDER]"
    subject = f"{subject_prefix} Tuition Fee Invoice #{invoice_number} Due Date: {due_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = recipient_email

    text_body = f"""Dear {student_name},

This is an automated notification regarding your tuition and fees account.

Invoice Number: {invoice_number}
Outstanding Balance: {due_amount}
Due Date: {due_date}
Status: {student['status']}

Please log in to the Student Portal to settle your balance promptly to avoid late penalties or registration holds.

If you have already submitted this payment, please allow 1-2 business days for banking settlement.

Sincerely,
{SENDER_NAME}
    """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 20px auto; border: 1px solid #e1e4e8; border-radius: 8px; overflow: hidden; }}
        .header {{ background-color: {'#d9381e' if is_overdue else '#0052cc'}; color: #ffffff; padding: 20px; text-align: center; }}
        .content {{ padding: 25px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 13px; background: {'#ffebe6' if is_overdue else '#deebff'}; color: {'#bf2600' if is_overdue else '#0747a6'}; }}
        .details-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .details-table td {{ padding: 10px; border-bottom: 1px solid #f0f0f0; }}
        .details-table td.label {{ font-weight: 600; color: #5e6c84; width: 40%; }}
        .button {{ display: inline-block; background-color: #0052cc; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 4px; font-weight: bold; margin-top: 15px; }}
        .footer {{ background-color: #f4f5f7; padding: 15px; text-align: center; font-size: 12px; color: #6b778c; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h2>{'Action Required: Overdue Fee Balance' if is_overdue else 'Upcoming Tuition Fee Due'}</h2>
        </div>
        <div class="content">
          <p>Dear <strong>{student_name}</strong>,</p>
          <p>Please review your outstanding student account balance below:</p>
          
          <table class="details-table">
            <tr>
              <td class="label">Invoice Number</td>
              <td><strong>{invoice_number}</strong></td>
            </tr>
            <tr>
              <td class="label">Outstanding Amount</td>
              <td><strong style="color: {'#bf2600' if is_overdue else '#172b4d'}; font-size: 18px;">{due_amount}</strong></td>
            </tr>
            <tr>
              <td class="label">Due Date</td>
              <td>{due_date}</td>
            </tr>
            <tr>
              <td class="label">Status</td>
              <td><span class="badge">{student['status']}</span></td>
            </tr>
          </table>

          <p style="text-align: center;">
            <a href="http://localhost:7071/api/invoices/{student['invoice_id']}" class="button">View & Pay Invoice</a>
          </p>

          <p style="font-size: 13px; color: #6b778c;">If you have recently made this payment, please disregard this notice. For installment requests or bursar inquiries, reply directly to this email.</p>
        </div>
        <div class="footer">
          &copy; {datetime.now().year} University Student Financial Services &bull; Powered by Azure Fee Management
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def record_reminder_log(student: Dict[str, Any], status: str, error_msg: str = None):
    """Logs sent reminder into dbo.RemindersLog."""
    if execute_non_query is None:
        return

    sql = """
        INSERT INTO dbo.RemindersLog (invoice_id, student_id, recipient_email, reminder_type, channel, delivery_status, error_details)
        VALUES (?, ?, ?, ?, 'EMAIL', ?, ?)
    """
    reminder_type = "OVERDUE_FIRST" if student["status"] == "OVERDUE" else "UPCOMING_DUE"
    try:
        execute_non_query(sql, (
            student["invoice_id"],
            student["student_id"],
            student["email"],
            reminder_type,
            status,
            error_msg
        ))
    except Exception as ex:
        logger.warning(f"Could not persist reminder log in database: {str(ex)}")


def send_reminders(days_ahead: int = 7, dry_run: bool = False):
    """Main execution function to query and dispatch reminder emails."""
    logger.info(f"Checking fee invoices due within {days_ahead} days (dry_run={dry_run})...")
    candidates = fetch_candidates_from_db(days_ahead)
    logger.info(f"Found {len(candidates)} candidate invoices needing reminders.")

    if not candidates:
        logger.info("No candidates found. Exiting.")
        return

    sent_count = 0
    failed_count = 0

    smtp_client = None
    if not dry_run:
        try:
            logger.info(f"Connecting to SMTP server at {SMTP_HOST}:{SMTP_PORT}...")
            smtp_client = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            if SMTP_USE_TLS:
                smtp_client.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                smtp_client.login(SMTP_USER, SMTP_PASSWORD)
        except Exception as ex:
            logger.error(f"Failed to connect to SMTP server ({SMTP_HOST}:{SMTP_PORT}): {str(ex)}")
            return

    for item in candidates:
        email_msg = build_email_message(item, dry_run=dry_run)
        recipient = item["email"]

        if dry_run:
            logger.info(f"[DRY-RUN] Would send reminder to {recipient} for invoice {item['invoice_number']} (Balance: {item['due_amount']})")
            sent_count += 1
            continue

        try:
            smtp_client.send_message(email_msg)
            logger.info(f"Dispatched reminder to {recipient} for invoice {item['invoice_number']}.")
            record_reminder_log(item, "SENT")
            sent_count += 1
        except Exception as ex:
            logger.error(f"Error sending email to {recipient}: {str(ex)}")
            record_reminder_log(item, "FAILED", str(ex))
            failed_count += 1

    if smtp_client:
        try:
            smtp_client.quit()
        except Exception:
            pass

    logger.info("=" * 60)
    logger.info(f"Reminder dispatch completed: {sent_count} sent, {failed_count} failed.")
    logger.info(f"Verify emails locally in Mailpit Web UI: http://{SMTP_HOST}:8025")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Student Fee Payment Reminders via Local Mailpit SMTP.")
    parser.add_argument("--days-ahead", type=int, default=7, help="Invoices due within this many days (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without sending emails")
    args = parser.parse_args()

    send_reminders(days_ahead=args.days_ahead, dry_run=args.dry_run)

