# Azure API Management (APIM) Policies

This directory contains Azure API Management policy definitions for securing and governing the Student Fee Management microservice endpoints.

---

## 1. Gateway Architecture & Files in this Directory

### API Gateway URL & Routing Convention
- **Function App Backend URL**: `https://<function-app-name>.azurewebsites.net/api`
- **APIM API URL Suffix**: `fee-management`
- **Full Client Gateway URL Prefix**: `https://<apim-instance-name>.azure-api.net/fee-management`

### Policy Files

| File | Target Operation Path | Full Gateway URL | Description |
|---|---|---|---|
| [`student-status-policy.xml`](./student-status-policy.xml) | `GET /students/{studentId}/status` | `https://<apim-name>.azure-api.net/fee-management/students/{studentId}/status` | Inbound rate limiting (10 calls/60s by Subscription ID), Function key injection (`x-functions-key`), and CORS policy for local frontend development. |
| [`admin-update-policy.xml`](./admin-update-policy.xml) | `PUT /admin/students/{studentId}/fees` | `https://<apim-name>.azure-api.net/fee-management/admin/students/{studentId}/fees` | Entra ID JWT validation (401 for invalid/missing tokens, accepting both GUID and `api://GUID` audiences), token extraction to `jwt` variable, safe RBAC role check (403 if missing `Admin` role or missing `roles` claim), Authorization header preservation, rate limiting, and Function key injection. |

---

## 2. Named Values Configuration

Before applying the policies, you must create three **Named Values** in your Azure API Management instance. Named values decouple environment-specific secrets from policy XML.

### Required Named Values

| Named Value Key | Type | Description | Example / Placeholder |
|---|---|---|---|
| `function-key` | **Secret** | Host/Function key for the Azure Functions backend (`auth_level=FUNCTION`). Injected into the `x-functions-key` request header. | `{{function-key}}` *(retrieve from Function App -> App keys)* |
| `tenant-id` | **Plain / Secret** | Microsoft Entra ID (Azure AD) Directory / Tenant ID GUID. Used to fetch OpenID metadata and validate token issuer. | `{{tenant-id}}` *(e.g., `00000000-0000-0000-0000-000000000000`)* |
| `api-app-id` | **Plain / Secret** | Application (Client) ID **GUID only** (do **NOT** include the `api://` prefix). Used to validate token audiences. | `{{api-app-id}}` *(e.g., `11111111-2222-3333-4444-555555555555`)* |

> [!IMPORTANT]
> **Audience Matching (`api-app-id` Named Value)**:  
> The `api-app-id` Named Value **must contain the Application (Client) ID GUID only**, without the `api://` prefix.  
> 
> In `admin-update-policy.xml`, the policy automatically configures two audiences:
> ```xml
> <audiences>
>     <audience>{{api-app-id}}</audience>
>     <audience>api://{{api-app-id}}</audience>
> </audiences>
> ```
> This allows the gateway to seamlessly accept tokens issued for **either audience format** (the bare GUID or the Application ID URI `api://<GUID>`). If you include `api://` inside the Named Value itself, the second audience would expand to `api://api://<GUID>`, causing token validation to fail.

### How to Add Named Values in the Azure Portal

1. Open the [Azure Portal](https://portal.azure.com) and navigate to your **API Management service**.
2. In the left navigation menu under **APIs**, select **Named values**.
3. Click **+ Add**.
4. For each named value:
   - **Display name**: enter the key name (`function-key`, `tenant-id`, or `api-app-id`).
   - **Name**: automatically matches display name.
   - **Type**: select **Secret** for `function-key`, and **Plain** or **Secret** for `tenant-id` and `api-app-id`.
   - **Value**: enter the corresponding identifier or secret value (remember: `api-app-id` must be the bare GUID).
5. Click **Save**.

---

## 3. Where to Paste Each Policy in the Azure Portal

### A. Student Fee Status Endpoint (`GET /students/{studentId}/status`)

1. In the Azure Portal APIM blade, click **APIs** under the **APIs** section in the left menu.
2. Select your API (`Fee Management API` with URL suffix `fee-management`).
3. Under the list of operations in the **Design** tab, select the operation:
   - **Method / URL**: `GET /students/{studentId}/status`.
4. In the center editor panel, locate the **Inbound processing** box and click the **`</>` (Code editor)** icon in the upper-right corner.
5. Replace the entire XML content with the contents of [`student-status-policy.xml`](./student-status-policy.xml).
6. Click **Save**.

---

### B. Admin Fee Update Endpoint (`PUT /admin/students/{studentId}/fees`)

1. In the same API design view, select the admin update operation:
   - **Method / URL**: `PUT /admin/students/{studentId}/fees`.
2. In the center editor panel, locate the **Inbound processing** box and click the **`</>` (Code editor)** icon.
3. Replace the entire XML content with the contents of [`admin-update-policy.xml`](./admin-update-policy.xml).
4. Click **Save**.

---

## 4. Policy Details & Behavior

### `student-status-policy.xml`
- **CORS for Localhost**: Allows cross-origin requests from `http://localhost`, `http://localhost:3000`, `http://localhost:5173`, and `http://localhost:8080` with standard preflight caching (`max-age=300`).
- **Rate Limiting**: Enforces a quota of **10 calls per 60 seconds** keyed on `@(context.Subscription.Id)` (with fallback to client IP if unauthenticated). Rejection returns `429 Too Many Requests`.
- **Function Key Injection**: Automatically attaches `x-functions-key: {{function-key}}` so public callers do not need knowledge of the Azure Functions master/host key.

### `admin-update-policy.xml`
- **CORS for Localhost**: Handles browser `OPTIONS` preflight and `PUT` methods for admin portals running locally.
- **Rate Limiting**: Enforces **10 calls per 60 seconds** per subscription.
- **Entra ID JWT Validation (`<validate-jwt>`)**:
  - Dynamically fetches signing keys from:
    `https://login.microsoftonline.com/{{tenant-id}}/v2.0/.well-known/openid-configuration`
  - Accepts both audience formats: `{{api-app-id}}` (bare GUID) and `api://{{api-app-id}}` (Application ID URI).
  - Validates issuer against `https://login.microsoftonline.com/{{tenant-id}}/v2.0`.
  - Validates token expiration (`require-expiration-time="true"`).
  - **401 Unauthorized**: Returns HTTP 401 if the token is missing, malformed, or expired.
  - **Token Extraction**: Stores the validated token into the `jwt` context variable (`output-token-variable-name="jwt"`).
- **Safe RBAC Role Authorization (`<choose>`)**:
  - Evaluates `((Jwt)context.Variables["jwt"]).Claims.GetValueOrDefault("roles", new string[0])`.
  - Safely handles tokens where the `roles` claim is absent by defaulting to an empty array (`new string[0]`).
  - **403 Forbidden**: If the caller lacks the `Admin` role (or has no `roles` claim), immediately halts execution and returns HTTP 403:
    ```json
    {"error": "Forbidden: Caller does not have the required 'Admin' role."}
    ```
- **Preserve HTTP 200 for Authorized Admins**:
  - If the caller possesses the `Admin` role, execution continues normally.
  - Injects `x-functions-key: {{function-key}}` for backend host authorization.
  - Forwards the client's original `Authorization: Bearer <token>` header downstream so `shared/auth.py` can record caller identity (`oid`) in audit logs.
  - Backend updates the database and returns `HTTP 200 OK` with the updated student record.

---

## 5. APIM Testing & Verification Instructions

You can verify the APIM policies using the **Azure Portal APIM Test Console** or via `curl`.

### Testing via the Azure Portal Test Console

1. Navigate to **APIs** -> Select `Fee Management API` -> Select `PUT /admin/students/{studentId}/fees`.
2. Click the **Test** tab at the top.
3. Set template parameter `studentId` to `1`.
4. Under **Headers**:
   - Add `Ocp-Apim-Subscription-Key`: `<your-apim-subscription-key>`
   - Add `Content-Type`: `application/json`
5. Under **Request body**, enter:
   ```json
   {
     "totalFee": 85000.0,
     "paidAmount": 45000.0,
     "dueDate": "2026-12-15"
   }
   ```
6. Follow the test cases below by adjusting the `Authorization` header.

---

### Command-Line Verification (`curl`)

Set your base APIM endpoint and subscription key:
```bash
APIM_URL="https://<your-apim-name>.azure-api.net/fee-management"
SUB_KEY="<your-subscription-key>"
```

#### Test Case 1: Missing Token (Expect HTTP 401)
Request without an `Authorization` header:
```bash
curl -i -X PUT "$APIM_URL/admin/students/1/fees" \
  -H "Ocp-Apim-Subscription-Key: $SUB_KEY" \
  -H "Content-Type: application/json" \
  -d '{"totalFee": 85000.0, "paidAmount": 45000.0, "dueDate": "2026-12-15"}'
```
**Expected Response**:
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

Unauthorized: Missing, invalid, or expired Entra ID token.
```

#### Test Case 2: Invalid or Expired Token (Expect HTTP 401)
Request with a bogus Bearer token:
```bash
curl -i -X PUT "$APIM_URL/admin/students/1/fees" \
  -H "Authorization: Bearer invalid.jwt.token" \
  -H "Ocp-Apim-Subscription-Key: $SUB_KEY" \
  -H "Content-Type: application/json" \
  -d '{"totalFee": 85000.0, "paidAmount": 45000.0, "dueDate": "2026-12-15"}'
```
**Expected Response**:
```http
HTTP/1.1 401 Unauthorized
```

#### Test Case 3: Valid Token Without Admin Role (Expect HTTP 403)
Request with a valid Entra ID token that contains a different role (e.g., `Student`) or lacks the `roles` claim entirely:
```bash
curl -i -X PUT "$APIM_URL/admin/students/1/fees" \
  -H "Authorization: Bearer <valid-non-admin-token>" \
  -H "Ocp-Apim-Subscription-Key: $SUB_KEY" \
  -H "Content-Type: application/json" \
  -d '{"totalFee": 85000.0, "paidAmount": 45000.0, "dueDate": "2026-12-15"}'
```
**Expected Response**:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"error": "Forbidden: Caller does not have the required 'Admin' role."}
```

#### Test Case 4: Authorized Admin Caller (Expect HTTP 200)
Request with a valid Entra ID token containing the `Admin` role (issued for audience `<api-app-id-guid>` or `api://<api-app-id-guid>`):
```bash
curl -i -X PUT "$APIM_URL/admin/students/1/fees" \
  -H "Authorization: Bearer <valid-admin-token>" \
  -H "Ocp-Apim-Subscription-Key: $SUB_KEY" \
  -H "Content-Type: application/json" \
  -d '{"totalFee": 85000.0, "paidAmount": 45000.0, "dueDate": "2026-12-15"}'
```
**Expected Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "studentId": 1,
  "name": "Aarav Sharma",
  "totalFee": 85000.0,
  "paidAmount": 45000.0,
  "balance": 40000.0,
  "dueDate": "2026-12-15",
  "status": "Partially Paid"
}
```

#### Test Case 5: Rate Limiting Enforcement (Expect HTTP 429)
Send 11 rapid requests within 60 seconds with the same subscription key:
```bash
for i in {1..11}; do
  curl -s -o /dev/null -w "%{http_code}\n" -X GET "$APIM_URL/students/1/status" \
    -H "Ocp-Apim-Subscription-Key: $SUB_KEY"
done
```
**Expected Output**: The first 10 requests return `200`; the 11th request returns `429 Too Many Requests`.
