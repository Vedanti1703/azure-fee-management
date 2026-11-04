#!/usr/bin/env python3
"""
Local Fee Reminder Dispatcher Script
Queries overdue students via the local /api/overdue endpoint, pages through all results,
and sends reminder emails to Mailpit (localhost:1025) with retries and exponential backoff.
"""

import os
import sys
import time
import smtplib
import argparse
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("FeeReminders")


def load_env():
    """Load configuration from .env in the project root if available."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, ".."))
    env_path = os.path.join(root_dir, ".env")

    if not os.path.exists(env_path):
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # Fallback basic parser
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v


def fetch_all_overdue_students(base_url: str, page_size: int = 100) -> List[Dict[str, Any]]:
    """
    Calls the /api/overdue endpoint and pages through all records until exhausted.
    Returns a list of all overdue student dictionaries.
    """
    skip = 0
    all_students: List[Dict[str, Any]] = []
    page = 1

    logger.info("Fetching overdue students from %s/api/overdue (page size: %d)...", base_url, page_size)

    while True:
        url = f"{base_url.rstrip('/')}/api/overdue"
        params = {"top": page_size, "skip": skip}

        try:
            resp = requests.get(url, params=params, timeout=20)
        except requests.RequestException as ex:
            logger.error("Failed to connect to Functions API at %s: %s", url, ex)
            raise

        if resp.status_code != 200:
            logger.error("API error (%d): %s", resp.status_code, resp.text)
            raise RuntimeError(f"Functions API returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        students = data.get("students", [])

        if not students:
            break

        all_students.extend(students)
        logger.info("  Page %d: fetched %d students (total so far: %d)", page, len(students), len(all_students))

        skip += len(students)
        page += 1

        if len(students) < page_size:
            # Last page reached
            break

    logger.info("Finished fetching: retrieved %d overdue students across %d page(s).", len(all_students), page - 1)
    return all_students


def build_email_message(student: Dict[str, Any], sender_email: str, sender_name: str) -> MIMEMultipart:
    """Builds a multipart (plain text + HTML) reminder email message."""
    recipient_email = student["email"]
    name = student["name"]
    balance = float(student["balance"])
    due_date = student["dueDate"]
    days_overdue = int(student["daysOverdue"])

    formatted_balance = f"${balance:,.2f}"

    subject = f"Friendly Reminder: Outstanding Tuition Balance for {name}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = recipient_email

    text_body = f"""Dear {name},

We hope this message finds you well.

This is a friendly reminder from Student Financial Services regarding your tuition account. Our records indicate that you have an outstanding balance of {formatted_balance}, which was due on {due_date} ({days_overdue} days ago).

Account Summary:
  - Student Name: {name}
  - Outstanding Balance: {formatted_balance}
  - Original Due Date: {due_date}
  - Days Overdue: {days_overdue} day(s)

Please log in to the Student Portal to review your statement and complete your payment. If you require assistance or wish to discuss an installment schedule, please reply directly to this email.

If you have already submitted your payment recently, thank you, and please disregard this notice.

Warm regards,
{sender_name}
{sender_email}
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #2d3748; margin: 0; padding: 20px; }}
    .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
    .header {{ background-color: #2b6cb0; color: #ffffff; padding: 24px; text-align: center; }}
    .header h2 {{ margin: 0; font-size: 20px; font-weight: 600; }}
    .content {{ padding: 28px 24px; }}
    .greeting {{ font-size: 16px; margin-bottom: 16px; }}
    .summary-box {{ background-color: #f7fafc; border: 1px solid #edf2f7; border-radius: 6px; padding: 18px; margin: 20px 0; }}
    .summary-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #edf2f7; }}
    .summary-row:last-child {{ border-bottom: none; }}
    .summary-label {{ font-weight: 500; color: #718096; }}
    .summary-value {{ font-weight: 600; color: #1a202c; }}
    .balance-highlight {{ color: #c53030; font-size: 18px; }}
    .footer {{ background-color: #edf2f7; padding: 16px 24px; text-align: center; font-size: 12px; color: #718096; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2>Student Account Payment Reminder</h2>
    </div>
    <div class="content">
      <p class="greeting">Dear <strong>{name}</strong>,</p>
      <p>We hope this message finds you well. This is a gentle reminder from Student Financial Services regarding your tuition account.</p>

      <div class="summary-box">
        <table style="width: 100%; border-collapse: collapse;">
          <tr>
            <td style="padding: 6px 0; color: #718096; font-weight: 500;">Student Name:</td>
            <td style="padding: 6px 0; text-align: right; font-weight: 600;">{name}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #718096; font-weight: 500;">Outstanding Balance:</td>
            <td style="padding: 6px 0; text-align: right; font-weight: 700; color: #c53030; font-size: 16px;">{formatted_balance}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #718096; font-weight: 500;">Due Date:</td>
            <td style="padding: 6px 0; text-align: right; font-weight: 600;">{due_date}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #718096; font-weight: 500;">Days Overdue:</td>
            <td style="padding: 6px 0; text-align: right; font-weight: 600; color: #dd6b20;">{days_overdue} day(s)</td>
          </tr>
        </table>
      </div>

      <p>Please log in to the Student Portal to review your account and submit payment. If you need assistance or wish to discuss an installment schedule, please reply directly to this email.</p>
      <p style="font-size: 13px; color: #718096; margin-top: 24px;">If you have recently submitted this payment, thank you, and please disregard this notice.</p>
    </div>
    <div class="footer">
      &copy; Student Financial Services &bull; Powered by Azure Fee Management
    </div>
  </div>
</body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_email_with_retry(
    student: Dict[str, Any],
    smtp_host: str,
    smtp_port: int,
    sender_email: str,
    sender_name: str,
    dry_run: bool = False
) -> bool:
    """
    Sends a reminder email to a single student via SMTP.
    Retries up to 3 times with exponential backoff on failure.
    Returns True if sent successfully, False otherwise.
    """
    recipient = student.get("email", "unknown")
    name = student.get("name", "Student")
    balance = float(student.get("balance", 0.0))
    due_date = student.get("dueDate", "N/A")
    days_overdue = int(student.get("daysOverdue", 0))

    if dry_run:
        logger.info(
            "[DRY-RUN] Would email %s <%s> | Balance: $%.2f | Due: %s (%d days overdue)",
            name, recipient, balance, due_date, days_overdue
        )
        return True

    msg = build_email_message(student, sender_email, sender_name)
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.send_message(msg)
            logger.info("Sent reminder to %s <%s>", name, recipient)
            return True
        except Exception as ex:
            if attempt < max_retries:
                backoff = (2 ** (attempt - 1)) * 0.5  # 0.5s, 1.0s
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                    attempt, max_retries, recipient, ex, backoff
                )
                time.sleep(backoff)
            else:
                logger.error(
                    "Failed to deliver reminder to %s after %d attempts: %s. Skipping to next student.",
                    recipient, max_retries, ex
                )
                return False

    return False


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Dispatch overdue student fee reminder emails via local Mailpit.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without sending SMTP messages.")
    parser.add_argument("--base-url", default=os.environ.get("FUNCTIONS_BASE_URL", "http://localhost:7071"),
                        help="Azure Functions base URL (default: http://localhost:7071).")
    parser.add_argument("--page-size", type=int, default=100,
                        help="Number of records to fetch per page (default: 100, max: 500).")
    parser.add_argument("--smtp-host", default=os.environ.get("SMTP_HOST", "localhost"),
                        help="SMTP server hostname (default: localhost).")
    parser.add_argument("--smtp-port", type=int, default=int(os.environ.get("SMTP_PORT", "1025")),
                        help="SMTP server port (default: 1025).")
    parser.add_argument("--sender-email", default=os.environ.get("SENDER_EMAIL", "billing@university.edu"),
                        help="From email address.")
    parser.add_argument("--sender-name", default=os.environ.get("SENDER_NAME", "Student Financial Services"),
                        help="From sender display name.")

    args = parser.parse_args()

    page_size = min(max(args.page_size, 1), 500)

    print("=" * 65)
    print("Azure Student Fee Management - Local Reminder Dispatcher")
    print("=" * 65)
    print(f"Functions API : {args.base_url}")
    print(f"SMTP Target   : {args.smtp_host}:{args.smtp_port}")
    print(f"Page Size     : {page_size}")
    print(f"Dry Run Mode  : {'ACTIVE (No emails will be sent)' if args.dry_run else 'OFF (Sending to Mailpit)'}")
    print("=" * 65)

    try:
        students = fetch_all_overdue_students(args.base_url, page_size=page_size)
    except Exception as ex:
        logger.error("Could not retrieve overdue students: %s", ex)
        sys.exit(1)

    if not students:
        logger.info("No overdue students found. No reminders to dispatch.")
        sys.exit(0)

    logger.info("Starting reminder dispatch for %d student(s)...", len(students))

    sent_count = 0
    failed_count = 0

    for idx, student in enumerate(students, start=1):
        success = send_email_with_retry(
            student=student,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            sender_email=args.sender_email,
            sender_name=args.sender_name,
            dry_run=args.dry_run
        )
        if success:
            sent_count += 1
        else:
            failed_count += 1

    print("\n" + "=" * 65)
    print("Reminder Dispatch Summary")
    print("=" * 65)
    print(f"Total Overdue Students : {len(students):,}")
    print(f"Successfully Sent      : {sent_count:,}")
    print(f"Failed / Skipped       : {failed_count:,}")
    if not args.dry_run:
        print(f"Inspect emails at      : http://{args.smtp_host}:8025 (Mailpit Web UI)")
    print("=" * 65)


if __name__ == "__main__":
    main()
