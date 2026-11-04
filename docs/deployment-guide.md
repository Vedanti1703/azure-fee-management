# Student Fee Management System - Azure Deployment Guide

This guide is a numbered deployment skeleton for standing up the entire Student Fee Management System in Microsoft Azure.

---

## Deployment Checklist & Resource Overview

- [ ] **Step 1:** Azure Resource Group Setup
- [ ] **Step 2:** Azure SQL Database Provisioning & Schema Migration
- [ ] **Step 3:** Microsoft Entra ID App Registrations & Role Configuration
- [ ] **Step 4:** Azure Function App (Python v2) Deployment
- [ ] **Step 5:** Azure API Management (APIM) Configuration & Policy Import
- [ ] **Step 6:** Azure Logic App (Consumption) Workflow Setup
- [ ] **Step 7:** Observability, Application Insights & Health Alerts

---

## Step 1: Azure Resource Group Setup

Create a centralized Azure Resource Group to host all solution components in the target region.

1. **Log in to Azure CLI**:
   ```bash
   az login
   az account set --subscription "[TODO: <azure-subscription-id>]"
   ```

2. **Create the Resource Group**:
   ```bash
   az group create \
     --name "[TODO: <resource-group-name>]" \
     --location "[TODO: <azure-region>]"
   ```
   *Recommended Name*: `rg-feemanagement-prod`  
   *Recommended Region*: `centralindia` or `eastus`

3. **Portal Verification**:
   - Navigate to **Resource groups** in the Azure Portal.
   - Confirm the resource group appears with status `Succeeded`.

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Resource Group Overview in Azure Portal]`

---

## Step 2: Azure SQL Database Provisioning & Schema Migration

Deploy an Azure SQL Server and database with the required schema, constraints, stored procedures, and initial seed data.

1. **Create the Logical SQL Server**:
   ```bash
   az sql server create \
     --name "[TODO: <sql-server-name>]" \
     --resource-group "[TODO: <resource-group-name>]" \
     --location "[TODO: <azure-region>]" \
     --admin-user "[TODO: <sql-admin-username>]" \
     --admin-password "[TODO: <sql-admin-password>]"
   ```

2. **Configure SQL Firewall (Allow Azure Services)**:
   ```bash
   # Enable internal communication from Azure Functions and Logic Apps
   az sql server firewall-rule create \
     --resource-group "[TODO: <resource-group-name>]" \
     --server "[TODO: <sql-server-name>]" \
     --name "AllowAllWindowsAzureIps" \
     --start-ip-address 0.0.0.0 \
     --end-ip-address 0.0.0.0
   ```

3. **Create the Database (`FeeManagement`)**:
   ```bash
   az sql db create \
     --resource-group "[TODO: <resource-group-name>]" \
     --server "[TODO: <sql-server-name>]" \
     --name "FeeManagement" \
     --service-objective "S0" \
     --edition "Standard"
   ```

4. **Execute Database Scripts**:
   Run the SQL scripts in order using `sqlcmd` or Azure Portal **Query Editor**:
   ```bash
   # 1. Apply Schema, Tables, Constraints & Stored Procedure
   sqlcmd -S "[TODO: <sql-server-name>].database.windows.net" -d FeeManagement -U "[TODO: <sql-admin-username>]" -P "[TODO: <sql-admin-password>]" -i database/schema.sql

   # 2. Seed Initial 20 Realistic Student Rows & Admins
   sqlcmd -S "[TODO: <sql-server-name>].database.windows.net" -d FeeManagement -U "[TODO: <sql-admin-username>]" -P "[TODO: <sql-admin-password>]" -i database/seed.sql

   # 3. (Optional) Seed 5,000 Synthetic Student Records for Load Verification
   sqlcmd -S "[TODO: <sql-server-name>].database.windows.net" -d FeeManagement -U "[TODO: <sql-admin-username>]" -P "[TODO: <sql-admin-password>]" -i database/seed_5000.sql
   ```

5. **Assemble the ODBC Connection String**:
   ```text
   Driver={ODBC Driver 18 for SQL Server};Server=[TODO: <sql-server-name>].database.windows.net,1433;Database=FeeManagement;Uid=[TODO: <sql-admin-username>];Pwd=[TODO: <sql-admin-password>];Encrypt=yes;TrustServerCertificate=no;
   ```

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Azure SQL Database Tables & Query Editor Verification]`

---

## Step 3: Microsoft Entra ID App Registrations & Role Configuration

Register the backend API application, expose the API, and configure the `Admin` App Role for JWT verification.

1. **Register the Backend API Application**:
   - Azure Portal -> **Microsoft Entra ID** -> **App registrations** -> **+ New registration**.
   - **Name**: `FeeManagementAPI`
   - **Supported account types**: `Accounts in this organizational directory only (Single tenant)`.
   - Click **Register**. Note down the **Application (Client) ID**: `[TODO: <api-app-id>]` and **Directory (Tenant) ID**: `[TODO: <tenant-id>]`.

2. **Expose the API**:
   - In `FeeManagementAPI`, go to **Expose an API**.
   - Set **Application ID URI**: `api://[TODO: <api-app-id>]` (or `api://feemanagement`).
   - Add a scope `Fees.ReadWrite` (Admin consent required).

3. **Define the `Admin` App Role**:
   - In `FeeManagementAPI`, go to **App roles** -> **+ Create app role**.
   - **Display name**: `Admin`
   - **Allowed member types**: `Both (Users/Groups + Applications)`
   - **Value**: `Admin`
   - **Description**: `Full administrative access to update student fees`
   - Check **Do you want to enable this app role?** -> Click **Apply**.

4. **Assign Admin Role to Users or Client Applications**:
   - Go to **Enterprise applications** -> `FeeManagementAPI` -> **Users and groups** -> **+ Add user/group**.
   - Select your administrative user or group and assign the `Admin` role.

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Entra ID App Role 'Admin' Configuration]`

---

## Step 4: Azure Function App (Python v2) Deployment

Deploy the serverless Python v2 application to Azure Functions on a Consumption plan.

1. **Create Storage Account for Azure Functions**:
   ```bash
   az storage account create \
     --name "[TODO: <storage-account-name>]" \
     --location "[TODO: <azure-region>]" \
     --resource-group "[TODO: <resource-group-name>]" \
     --sku Standard_LRS
   ```

2. **Create the Function App (Linux / Python 3.11)**:
   ```bash
   az functionapp create \
     --name "[TODO: <function-app-name>]" \
     --resource-group "[TODO: <resource-group-name>]" \
     --storage-account "[TODO: <storage-account-name>]" \
     --consumption-plan-location "[TODO: <azure-region>]" \
     --runtime python \
     --runtime-version 3.11 \
     --os-type Linux \
     --functions-version 4
   ```

3. **Configure Application Settings**:
   ```bash
   az functionapp config appsettings set \
     --name "[TODO: <function-app-name>]" \
     --resource-group "[TODO: <resource-group-name>]" \
     --settings \
       SQL_CONNECTION_STRING="[TODO: <sql-connection-string>]" \
       AUTH_MODE="jwt" \
       TENANT_ID="[TODO: <tenant-id>]" \
       API_AUDIENCE="[TODO: <api-app-id>]" \
       AzureWebJobsFeatureFlags="EnableWorkerIndexing"
   ```

4. **Deploy Application Code**:
   From the repository root:
   ```bash
   cd functions
   func azure functionapp publish "[TODO: <function-app-name>]" --build remote
   cd ..
   ```

5. **Retrieve the Function Host Key**:
   - Azure Portal -> Function App -> **App keys** -> Copy the `default` host key.
   - Note down: `[TODO: <function-key>]`.

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Function App Functions List and App Keys]`

---

## Step 5: Azure API Management (APIM) Configuration & Policy Import

Provision and configure Azure API Management as the single secure entry point.

1. **Create the APIM Instance (Consumption or Developer Tier)**:
   ```bash
   az apim create \
     --name "[TODO: <apim-instance-name>]" \
     --resource-group "[TODO: <resource-group-name>]" \
     --location "[TODO: <azure-region>]" \
     --publisher-name "[TODO: <organization-name>]" \
     --publisher-email "[TODO: <admin-email>]" \
     --sku-name Consumption
   ```

2. **Configure Named Values in APIM**:
   In the Azure Portal -> APIM -> **APIs** -> **Named values** -> **+ Add**:
   - `function-key` (Type: **Secret**, Value: `[TODO: <function-key>]`)
   - `tenant-id` (Type: **Plain**, Value: `[TODO: <tenant-id>]`)
   - `api-app-id` (Type: **Plain**, Value: `[TODO: <api-app-id>]`)

3. **Create the API**:
   - Go to **APIs** -> **+ Add API** -> **HTTP (Manually define an API)**.
   - **Display name**: `Fee Management API`
   - **Name**: `fee-management-api`
   - **Web service URL**: `https://[TODO: <function-app-name>].azurewebsites.net/api`
   - **API URL suffix**: `fee-management` (or blank)

4. **Add Operations & Apply Inbound Policy XML**:
   - **Operation 1: Student Fee Status**:
     - Frontend: `GET /students/{studentId}/status`
     - Inbound Processing -> Click `</>` (Code editor) -> Paste contents of `apim/student-status-policy.xml`.
     - Click **Save**.
   - **Operation 2: Admin Fee Update**:
     - Frontend: `PUT /admin/students/{studentId}/fees`
     - Inbound Processing -> Click `</>` (Code editor) -> Paste contents of `apim/admin-update-policy.xml`.
     - Click **Save**.
   - **Operation 3: Overdue Query (Internal/Logic App)**:
     - Frontend: `GET /overdue`
   - **Operation 4: Health Probe**:
     - Frontend: `GET /health`

> *Screenshot placeholder*:  
> `[TODO: Screenshot - APIM Operation Policy Code Editor for Admin Update]`

---

## Step 6: Azure Logic App (Consumption) Workflow Setup

Create the automated daily overdue reminder workflow.

1. **Provision the Logic App**:
   - Azure Portal -> **Logic Apps** -> **+ Create**.
   - **Name**: `[TODO: <logic-app-name>]` (e.g. `logic-fee-reminders-daily`)
   - **Plan type**: `Consumption`
   - **Resource Group**: `[TODO: <resource-group-name>]`

2. **Configure Workflow in Designer** *(following `logicapp/README.md`)*:
   - **Trigger**: `Recurrence` -> Daily at `09:00 IST` (Hours: `9`, Minutes: `0`, Time Zone: `India Standard Time`).
   - **Variables**: Initialize `Top` = `100`, `Skip` = `0`.
   - **Try Scope (`Try_Scope`)**:
     - Add **Until** loop: Condition `@less(body('HTTP_Get_Overdue_Students')?['count'], variables('Top'))`.
     - Inside Until:
       - **HTTP Action**: `GET https://[TODO: <function-app-name>].azurewebsites.net/api/overdue?top=@{variables('Top')}&skip=@{variables('Skip')}`
         - Add header `x-functions-key: [TODO: <function-key>]`.
         - Settings -> Retry policy: `Exponential`, Count: `4`, Interval: `PT10S`.
       - **For each Student**: Select `@body('HTTP_Get_Overdue_Students')?['students']`.
         - Settings -> **Concurrency Control**: `On`, **Degree of Parallelism**: `5`.
         - Inside For each: **Send an email (V2)** (Office 365 Outlook or SendGrid).
           - Paste the HTML email template from `logicapp/README.md`.
           - Settings -> Retry policy: `Exponential`, Count: `4`, Interval: `PT10S`.
       - **Increment variable**: `Skip` by `100`.
   - **Catch Scope (`Catch_Scope`)**:
     - Configure **Run after**: `Try_Scope` -> Check **has failed**, **has timed out**.
     - Add email alert to `[TODO: <admin-alert-email>]` and a **Terminate** action with status `Failed`.

3. **Authorize Email Connector**:
   - Sign in to the Office 365 Outlook connection or provide your SendGrid API key: `[TODO: <sendgrid-api-key>]`.

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Logic App Designer Workflow Canvas]`

---

## Step 7: Observability, Application Insights & Health Alerts

Configure monitoring, availability tests, and automated alerts for operations teams.

1. **Enable Application Insights**:
   - In Function App -> **Application Insights** -> Turn On -> Create new resource: `[TODO: <app-insights-name>]`.
   - Confirm application logs (`operation`, `studentId`, `duration_ms`) stream into the **Transaction search** and **Logs** blades.

2. **Configure Availability Web Test (Health Check)**:
   - In Application Insights -> **Availability** -> **+ Add Standard test**.
   - **Test name**: `FeeManagementHealthProbe`
   - **URL**: `https://[TODO: <function-app-name>].azurewebsites.net/api/health`
   - **Test frequency**: `5 minutes`
   - **Success criteria**: HTTP status code `200`.

3. **Set Up Azure Monitor Alert Rules**:
   - **Alert 1: Database Health Probe Failure**:
     - Condition: Availability Test `< 100%` for 2 consecutive checks.
     - Action Group: Send email/SMS to `[TODO: <devops-team-email>]`.
   - **Alert 2: High Server Errors (HTTP 5xx)**:
     - Condition: Function App `Http5xx > 5` over a 5-minute evaluation window.
   - **Alert 3: Logic App Batch Failure**:
     - Condition: Logic App `Runs Failed > 0`.

4. **Verify Live Telemetry**:
   - Invoke `GET /api/health` and verify HTTP 200 response.
   - Query Application Insights Logs (`traces | where customDimensions.operation == "get_student_fee_status"`).

> *Screenshot placeholder*:  
> `[TODO: Screenshot - Application Insights Availability Test & Dashboard]`

---

## 8. Post-Deployment Verification Commands

Run the following sanity tests against the deployed gateway endpoints:

```bash
# 1. Health Probe Check
curl -i -X GET "https://[TODO: <apim-instance-name>].azure-api.net/fee-management/health"

# 2. Student Status Query (Student ID: 1)
curl -i -X GET "https://[TODO: <apim-instance-name>].azure-api.net/fee-management/students/1/status" \
  -H "Ocp-Apim-Subscription-Key: [TODO: <apim-subscription-key>]"

# 3. Admin Fee Update (Authorized Admin Token Required)
curl -i -X PUT "https://[TODO: <apim-instance-name>].azure-api.net/fee-management/admin/students/1/fees" \
  -H "Authorization: Bearer [TODO: <admin-jwt-token>]" \
  -H "Ocp-Apim-Subscription-Key: [TODO: <apim-subscription-key>]" \
  -H "Content-Type: application/json" \
  -d '{"totalFee": 85000.0, "paidAmount": 85000.0, "dueDate": "2026-12-01"}'
```
