# Azure Logic App - Student Fee Reminders & Notification Workflow

This directory outlines the orchestration workflow for automated fee reminders and payment alerts in the Azure Student Fee Management System.

---

## 1. Overview

The **Fee Reminder Logic App** acts as a scheduled cloud orchestrator that triggers recurring checks for upcoming and overdue tuition invoices, formats email communications, and dispatches them to students and financial administrators.

```
[ Azure Logic App (Standard / Consumption) ]
       |
       |-- 1. Daily Recurrence Trigger (08:00 UTC)
       |
       |-- 2. HTTP POST -> APIM Gateway / Azure Functions (/api/reminders/trigger)
       |
       |-- 3. Parse JSON Array (Candidate Invoices)
       |
       |-- 4. For Each Candidate:
       |        |-- Branch A: If Overdue > 14 days -> Notify Student + Escalation to Bursar
       |        |-- Branch B: Standard Due Reminder -> Send Office 365 / SendGrid Email
       |        \-- Branch C: Log Result back to dbo.RemindersLog
```

---

## 2. Trigger & Action Specifications

### Trigger: Recurrence
- **Frequency:** Day
- **Interval:** 1
- **Schedule:** 08:00 UTC daily

### Action 1: Query Pending & Overdue Invoices
- **Type:** HTTP Action
- **Method:** `POST`
- **URI:** `https://<apim-instance-name>.azure-api.net/fee-management/reminders/trigger`
- **Headers:**
  - `Ocp-Apim-Subscription-Key`: `@appsetting('APIM_SUBSCRIPTION_KEY')`
  - `Authorization`: `Bearer @{body('Get_Managed_Identity_Token')?['access_token']}`
- **Body:**
  ```json
  {
    "days_ahead": 7,
    "escalate_overdue": true
  }
  ```

### Action 2: Parse Candidates Response
- **Schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "message": { "type": "string" },
      "candidates_count": { "type": "integer" },
      "candidates": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "invoice_id": { "type": "integer" },
            "invoice_number": { "type": "string" },
            "due_amount": { "type": "number" },
            "due_date": { "type": "string" },
            "status": { "type": "string" },
            "student_id": { "type": "integer" },
            "first_name": { "type": "string" },
            "last_name": { "type": "string" },
            "email": { "type": "string" }
          }
        }
      }
    }
  }
  ```

### Action 3: ForEach Candidate
- **Email Connector:**
  - **Dev/Local:** `scripts/send_reminders_local.py` (Mailpit SMTP)
  - **Azure Production:** Office 365 Outlook connector (`Send_an_email_(V2)`) or Azure SendGrid connector.
- **Subject:** `Payment Reminder: Invoice @{items('ForEach')?['invoice_number']}`

---

## 3. Workflow Parameters & Configuration

| Parameter Name | Description | Example / Placeholder |
| :--- | :--- | :--- |
| `APIM_GATEWAY_URL` | Base APIM URL | `https://apim-fee-mgmt.azure-api.net/fee-management` |
| `APIM_SUBSCRIPTION_KEY` | APIM Subscription Key | `@Microsoft.KeyVault(...)` |
| `EMAIL_SENDER_ADDRESS` | Official billing email address | `billing@university.edu` |
| `BURSAR_ESCALATION_EMAIL`| Staff alert recipient | `bursar-alerts@university.edu` |

---

## 4. Local Development vs. Azure Production

- **Local Development:**
  In local development, the Logic App workflow is simulated using the python script:
  ```bash
  python scripts/send_reminders_local.py --days-ahead 7
  ```
  The script directly reads from the local database and dispatches messages to the **Mailpit** container (`http://localhost:8025`).

- **Azure Production:**
  Deploy using Azure Bicep / ARM template (`logicapp/workflow.json` or Bicep module) into Azure Logic Apps Standard or Consumption tier, secured with Azure Managed Identity.

