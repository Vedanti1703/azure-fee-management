# Azure API Management (APIM) Policies

This directory contains Azure API Management policy definitions for securing and governing the Student Fee Management microservice endpoints.

---

## 1. Files in this Directory

| File | Target Endpoint | Description |
|---|---|---|
| [`student-status-policy.xml`](./student-status-policy.xml) | `GET /api/students/{studentId}/status` | Inbound rate limiting (10 calls/60s by Subscription ID), Function key injection (`x-functions-key`), and CORS policy for local frontend development. |
| [`admin-update-policy.xml`](./admin-update-policy.xml) | `PUT /api/admin/students/{studentId}/fees` | Entra ID JWT validation via OpenID configuration, `Admin` role claim enforcement, 401 error mapping, Authorization header preservation to backend, rate limiting, and Function key injection. |

---

## 2. Named Values Configuration

Before applying the policies, you must create three **Named Values** in your Azure API Management instance. Named values decouple environment-specific secrets from policy XML.

### Required Named Values

| Named Value Key | Type | Description | Example / Placeholder |
|---|---|---|---|
| `function-key` | **Secret** | Host/Function key for the Azure Functions backend (`auth_level=FUNCTION`). Injected into the `x-functions-key` request header. | `{{function-key}}` *(retrieve from Function App -> App keys)* |
| `tenant-id` | **Plain / Secret** | Microsoft Entra ID (Azure AD) Directory / Tenant ID GUID. Used to fetch OpenID metadata and validate token issuer. | `{{tenant-id}}` *(e.g., `00000000-0000-0000-0000-000000000000`)* |
| `api-app-id` | **Plain / Secret** | Application (Client) ID or Application ID URI registered in Entra ID representing the backend API audience. | `{{api-app-id}}` *(e.g., `api://fee-management-api` or GUID)* |

### How to Add Named Values in the Azure Portal

1. Open the [Azure Portal](https://portal.azure.com) and navigate to your **API Management service**.
2. In the left navigation menu under **APIs**, select **Named values**.
3. Click **+ Add**.
4. For each named value:
   - **Display name**: enter the key name (`function-key`, `tenant-id`, or `api-app-id`).
   - **Name**: automatically matches display name.
   - **Type**: select **Secret** for `function-key`, and **Plain** or **Secret** for `tenant-id` and `api-app-id`.
   - **Value**: enter the corresponding identifier or secret value.
5. Click **Save**.

---

## 3. Where to Paste Each Policy in the Azure Portal

### A. Student Fee Status Endpoint (`GET /api/students/{studentId}/status`)

1. In the Azure Portal APIM blade, click **APIs** under the **APIs** section in the left menu.
2. Select your API (e.g., `Fee Management API`).
3. Under the list of operations in the **Design** tab, select the operation:
   - **Method / URL**: `GET /students/{studentId}/status` (or `GET /api/students/{studentId}/status`).
4. In the center editor panel, locate the **Inbound processing** box and click the **`</>` (Code editor)** icon in the upper-right corner.
5. Replace the entire XML content with the contents of [`student-status-policy.xml`](./student-status-policy.xml).
6. Click **Save**.

---

### B. Admin Fee Update Endpoint (`PUT /api/admin/students/{studentId}/fees`)

1. In the same API design view, select the admin update operation:
   - **Method / URL**: `PUT /admin/students/{studentId}/fees` (or `PUT /api/admin/students/{studentId}/fees`).
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
- **Rate Limiting**: Same rate limit policy (10 calls / 60 seconds per subscription).
- **Entra ID JWT Validation (`validate-jwt`)**:
  - Dynamically fetches signing keys from:
    `https://login.microsoftonline.com/{{tenant-id}}/v2.0/.well-known/openid-configuration`
  - Validates audience against `{{api-app-id}}`.
  - Validates issuer against `https://login.microsoftonline.com/{{tenant-id}}/v2.0`.
  - Validates token expiration (`require-expiration-time="true"`).
  - Validates that the `roles` claim contains `"Admin"`.
  - If token is missing, expired, invalid, or lacks the `"Admin"` role, rejects immediately with `HTTP 401 Unauthorized`.
- **Authorization Forwarding**: Retains and passes the caller's incoming `Authorization: Bearer <token>` header downstream to the Python Azure Function, allowing `shared/auth.py` to inspect the caller's `oid` for non-PII audit logging.
- **Function Key Injection**: Attaches `x-functions-key: {{function-key}}` for backend function host authorization.
