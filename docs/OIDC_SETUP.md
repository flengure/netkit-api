# OIDC Authentication Setup

netkit-api supports OpenID Connect (OIDC) authentication for secure, scalable API access. OIDC provides token-based authentication using industry-standard protocols.

## Benefits

- **No Shared Secrets**: Uses public key cryptography (JWKS) instead of shared secrets
- **Automatic Key Rotation**: Supports provider key rotation without API restarts
- **Standard Protocol**: Works with any OIDC-compliant provider
- **Scope-Based Authorization**: Fine-grained access control via OAuth2 scopes
- **Centralized Auth**: Single sign-on across multiple services

## Supported Providers

- **Authentik** (recommended open-source)
- **Auth0**
- **Keycloak**
- **Azure AD / Entra ID**
- **Google Identity**
- **Okta**
- Any OIDC-compliant provider

---

## Quick Start

### 1. Configure Provider (Example: Authentik)

#### Create OAuth2/OIDC Application

1. Go to Authentik Admin → Applications → Providers → Create
2. Choose **OAuth2/OpenID Provider**
3. Configure:
   - **Name**: `netkit-api`
   - **Client Type**: `Confidential`
   - **Authorization Grant Type**: `Client Credentials`
   - **Client ID**: (auto-generated or custom)
   - **Client Secret**: (auto-generated - save this)
   - **Redirect URIs**: Not needed for client_credentials flow
   - **Scopes**: Create `netkit.exec` scope

#### Get Configuration Details

You need these values:
- **Issuer URL**: `https://auth.u.tomage.net/application/o/netkit/`
- **Client ID**: From provider configuration
- **Client Secret**: From provider configuration
- **Scopes**: `netkit.exec` (or custom scopes)

### 2. Configure netkit-api

#### Option A: Environment Variables

```bash
docker run -d \
  -e OIDC_ENABLED=true \
  -e OIDC_ISSUER=https://auth.u.tomage.net/application/o/netkit/ \
  -e OIDC_AUDIENCE=netkit-api \
  -e OIDC_REQUIRED_SCOPES=netkit.exec \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -p 8090:8090 \
  flengure/netkit-api:latest --http
```

#### Option B: Configuration File

Create `config.yaml`:

```yaml
oidc_enabled: true
oidc_issuer: "https://auth.u.tomage.net/application/o/netkit/"
oidc_audience: "netkit-api"
oidc_required_scopes:
  - "netkit.exec"
```

Mount configuration:

```bash
docker run -d \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  -p 8090:8090 \
  flengure/netkit-api:latest --http
```

### 3. Test Authentication

#### Get Access Token

```bash
# Get token from Authentik
ACCESS_TOKEN=$(curl -sS -X POST \
  -d "grant_type=client_credentials" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "scope=netkit.exec" \
  https://auth.u.tomage.net/application/o/token/ | jq -r .access_token)

echo "Token: $ACCESS_TOKEN"
```

#### Call API with Token

```bash
# Execute command with OIDC token
curl -X POST https://netkit.tomage.net/exec \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"dig example.com +short"}'
```

---

## Configuration Reference

### Required Settings

| Variable | Example | Description |
|----------|---------|-------------|
| `OIDC_ENABLED` | `true` | Enable OIDC authentication |
| `OIDC_ISSUER` | `https://auth.example.com/` | OIDC issuer URL |

### Optional Settings

| Variable | Example | Description |
|----------|---------|-------------|
| `OIDC_AUDIENCE` | `netkit-api` | Validate audience claim in token |
| `OIDC_REQUIRED_SCOPES` | `netkit.exec,admin` | Require specific scopes (comma-separated) |
| `OIDC_JWKS_URI` | `https://auth.example.com/jwks` | JWKS endpoint (auto-discovered if not set) |

---

## Provider-Specific Setup

### Authentik

1. **Create Provider**:
   - Type: OAuth2/OpenID Provider
   - Client Type: Confidential
   - Authorization Grant: Client Credentials
   - Scopes: Create custom scope `netkit.exec`

2. **Create Application**:
   - Name: netkit-api
   - Provider: (select provider created above)

3. **Configuration**:
   ```yaml
   oidc_issuer: "https://auth.u.tomage.net/application/o/netkit/"
   oidc_required_scopes:
     - "netkit.exec"
   ```

4. **Token Endpoint**:
   ```
   POST https://auth.u.tomage.net/application/o/token/
   ```

### Auth0

1. **Create Application**:
   - Type: Machine to Machine
   - Authorized APIs: Create new API with identifier `netkit-api`
   - Permissions: Define scopes (e.g., `exec:tools`)

2. **Configuration**:
   ```yaml
   oidc_issuer: "https://YOUR_TENANT.auth0.com/"
   oidc_audience: "netkit-api"
   oidc_required_scopes:
     - "exec:tools"
   ```

3. **Token Endpoint**:
   ```
   POST https://YOUR_TENANT.auth0.com/oauth/token
   ```

### Keycloak

1. **Create Client**:
   - Client Type: OpenID Connect
   - Access Type: Confidential
   - Service Accounts Enabled: Yes
   - Authorization Enabled: Yes

2. **Create Client Scope**:
   - Name: `netkit.exec`
   - Assign to client

3. **Configuration**:
   ```yaml
   oidc_issuer: "https://keycloak.example.com/realms/master/"
   oidc_audience: "netkit-api"
   oidc_required_scopes:
     - "netkit.exec"
   ```

4. **Token Endpoint**:
   ```
   POST https://keycloak.example.com/realms/master/protocol/openid-connect/token
   ```

### Azure AD / Entra ID

1. **Register Application**:
   - Azure Portal → App Registrations → New registration
   - Supported account types: Single tenant
   - Redirect URI: Not needed for client_credentials

2. **Create Client Secret**:
   - Certificates & secrets → New client secret

3. **Configure API Permissions**:
   - Add application permissions
   - Grant admin consent

4. **Configuration**:
   ```yaml
   oidc_issuer: "https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0"
   oidc_audience: "api://YOUR_CLIENT_ID"
   ```

5. **Token Endpoint**:
   ```
   POST https://login.microsoftonline.com/YOUR_TENANT_ID/oauth2/v2.0/token
   ```

---

## Multiple Authentication Methods

netkit-api supports multiple authentication methods simultaneously:

```yaml
# Enable OIDC
oidc_enabled: true
oidc_issuer: "https://auth.example.com/"
oidc_required_scopes:
  - "netkit.exec"

# Also support API keys
api_keys:
  - "legacy-api-key-here"

# Also support JWT (not recommended with OIDC)
jwt_secret: "jwt-secret-here"
```

**Priority Order**:
1. OIDC Bearer token (if enabled)
2. JWT Bearer token (if configured)
3. API Key (if configured)

---

## Security Best Practices

### 1. Use HTTPS in Production

Always use HTTPS/TLS for production deployments:

```yaml
# Reverse proxy example (Caddy)
netkit.tomage.net {
    reverse_proxy localhost:8090
}
```

### 2. Validate Audience

Prevent token misuse by validating the audience claim:

```yaml
oidc_audience: "netkit-api"  # Must match token's 'aud' claim
```

### 3. Require Scopes

Use scope-based authorization for fine-grained access control:

```yaml
oidc_required_scopes:
  - "netkit.exec"        # Basic execution
  - "netkit.admin"       # Admin operations
  - "netkit.scan"        # Network scanning
```

### 4. Short Token Lifetimes

Configure short token lifetimes in your OIDC provider:
- Access tokens: 5-15 minutes
- Refresh tokens: 1 hour (if using authorization_code flow)

### 5. Monitor Authentication Logs

netkit-api logs all authentication attempts:

```
2025-10-03 18:00:00 - api - INFO - Valid OIDC token for subject: service-account
2025-10-03 18:00:05 - api - WARNING - OIDC token expired
```

---

## Troubleshooting

### Token Validation Fails

**Check issuer URL**:
```bash
# Verify OIDC discovery endpoint
curl https://auth.u.tomage.net/application/o/netkit/.well-known/openid-configuration
```

**Verify JWKS endpoint**:
```bash
curl https://auth.u.tomage.net/application/o/netkit/jwks/
```

**Check token expiration**:
```bash
# Decode token (without verification)
echo "$ACCESS_TOKEN" | jq -R 'split(".") | .[1] | @base64d | fromjson'
```

### Scope Validation Fails

Ensure token contains required scopes:

```bash
# Check token claims
echo "$ACCESS_TOKEN" | jq -R 'split(".") | .[1] | @base64d | fromjson | .scope'
```

Provider must include `scope` claim in token. Request scopes when getting token:

```bash
curl -X POST \
  -d "grant_type=client_credentials" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "scope=netkit.exec" \  # ← Include this
  https://auth.u.tomage.net/application/o/token/
```

### JWKS Auto-Discovery Fails

Manually specify JWKS URI:

```yaml
oidc_jwks_uri: "https://auth.u.tomage.net/application/o/netkit/jwks/"
```

### Audience Validation Fails

Check if provider includes `aud` claim:

```bash
echo "$ACCESS_TOKEN" | jq -R 'split(".") | .[1] | @base64d | fromjson | .aud'
```

If provider doesn't include `aud`, don't require it:

```yaml
# oidc_audience: ""  # Comment out or leave empty
```

---

## Example: Complete Authentik Setup

### 1. Create Scope

```
Admin → Customization → Scopes → Create
Name: netkit.exec
Scope name: netkit.exec
Description: Execute network tools
```

### 2. Create Provider

```
Admin → Applications → Providers → Create
Type: OAuth2/OpenID Provider
Name: netkit-provider
Client Type: Confidential
Authorization Grant Type: Client Credentials
Scopes: openid, profile, email, netkit.exec
```

Save Client ID and Client Secret.

### 3. Create Application

```
Admin → Applications → Create
Name: netkit-api
Provider: netkit-provider
```

### 4. Configure netkit-api

```yaml
# config.yaml
oidc_enabled: true
oidc_issuer: "https://auth.u.tomage.net/application/o/netkit/"
oidc_required_scopes:
  - "netkit.exec"
```

### 5. Test

```bash
# Get token
TOKEN=$(curl -sS -X POST \
  -d "grant_type=client_credentials" \
  -d "client_id=Bq8kl..." \
  -d "client_secret=dkF9m..." \
  -d "scope=netkit.exec" \
  https://auth.u.tomage.net/application/o/token/ | jq -r .access_token)

# Use token
curl -X POST https://netkit.tomage.net/exec \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"dig google.com +short"}'
```

---

## References

- [OAuth 2.0 Client Credentials](https://oauth.net/2/grant-types/client-credentials/)
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)
- [JWKS (JSON Web Key Sets)](https://datatracker.ietf.org/doc/html/rfc7517)
- [Authentik Documentation](https://docs.goauthentik.io/)
