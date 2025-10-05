"""
Tests for API endpoints
"""
import pytest


class TestSystemEndpoints:
    """Test system endpoints (healthz, stats)"""

    def test_healthz(self, client):
        """Test /healthz endpoint returns capability information"""
        response = client.get("/healthz")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["version"] == "2.0.0"
        assert data["service"] == "netkit-api"
        assert "capabilities" in data
        assert "has_net_raw" in data["capabilities"]
        assert "has_net_admin" in data["capabilities"]

    def test_stats_requires_auth(self, client):
        """Test /stats requires authentication"""
        response = client.get("/stats")
        assert response.status_code == 401

    def test_stats_with_auth(self, client, auth_headers):
        """Test /stats with valid authentication"""
        response = client.get("/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "rate_limiter" in data
        assert "job_manager" in data
        assert "tools" in data


class TestToolEndpoints:
    """Test tool discovery endpoints"""

    def test_list_tools(self, client):
        """Test /tools lists all available tools"""
        response = client.get("/tools")
        assert response.status_code == 200

        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) > 0

        # Check for essential tools
        tool_names = list(data["tools"].keys())
        assert "dig" in tool_names
        assert "nmap" in tool_names
        assert "curl" in tool_names

    def test_get_tool_info(self, client):
        """Test /tools/{name} returns tool information"""
        response = client.get("/tools/dig")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "dig"
        assert "description" in data
        assert "available" in data
        assert "requires_capability" in data
        assert "max_timeout" in data

    def test_get_unknown_tool(self, client):
        """Test /tools/{name} with unknown tool returns 404"""
        response = client.get("/tools/nonexistent-tool")
        assert response.status_code == 404
        assert "Unknown tool" in response.json()["detail"]


class TestToolExecution:
    """Test tool execution endpoint"""

    def test_exec_requires_auth(self, client):
        """Test /exec requires authentication"""
        response = client.post("/exec", json={"command": "dig google.com +short"})
        assert response.status_code == 401

    def test_exec_with_invalid_auth(self, client, invalid_auth_headers):
        """Test /exec with invalid API key"""
        response = client.post(
            "/exec",
            json={"command": "dig google.com +short"},
            headers=invalid_auth_headers
        )
        assert response.status_code == 401

    def test_exec_dig_full_command(self, client, auth_headers):
        """Test executing dig with full command string"""
        response = client.post(
            "/exec",
            json={"command": "dig google.com +short"},
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data
        assert data["exit_code"] == 0
        assert "duration_seconds" in data

    def test_exec_dig_tool_args(self, client, auth_headers):
        """Test executing dig with tool + args format"""
        response = client.post(
            "/exec",
            json={
                "tool": "dig",
                "args": ["google.com", "+short"]
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["exit_code"] == 0

    def test_exec_dig_tool_command(self, client, auth_headers):
        """Test executing dig with tool + command format"""
        response = client.post(
            "/exec",
            json={
                "tool": "dig",
                "command": "google.com +short"
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["exit_code"] == 0

    def test_exec_unknown_tool(self, client, auth_headers):
        """Test executing unknown tool returns 400"""
        response = client.post(
            "/exec",
            json={"command": "nonexistent-tool arg1"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "Unknown tool" in response.json()["detail"]

    def test_exec_empty_command(self, client, auth_headers):
        """Test executing empty command returns 400"""
        response = client.post(
            "/exec",
            json={"command": ""},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_exec_no_command_or_tool(self, client, auth_headers):
        """Test request with neither command nor tool returns 400"""
        response = client.post(
            "/exec",
            json={"timeout": 30},
            headers=auth_headers
        )
        assert response.status_code == 400

    def test_exec_with_timeout(self, client, auth_headers):
        """Test execution with custom timeout"""
        response = client.post(
            "/exec",
            json={
                "command": "dig google.com +short",
                "timeout": 5
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["exit_code"] == 0


class TestAsyncJobs:
    """Test async job execution"""

    def test_create_async_job(self, client, auth_headers):
        """Test creating async job"""
        response = client.post(
            "/exec",
            json={
                "command": "dig google.com +short",
                "async": True
            },
            headers=auth_headers
        )
        assert response.status_code == 202

        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "tool" in data

    def test_get_job_status(self, client, auth_headers):
        """Test getting job status"""
        # Create job
        create_response = client.post(
            "/exec",
            json={"command": "dig google.com +short", "async": True},
            headers=auth_headers
        )
        job_id = create_response.json()["job_id"]

        # Get job status
        response = client.get(f"/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert data["status"] in ["pending", "running", "completed", "failed"]

    def test_get_nonexistent_job(self, client, auth_headers):
        """Test getting nonexistent job returns 404"""
        response = client.get("/jobs/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404

    def test_list_jobs(self, client, auth_headers):
        """Test listing jobs"""
        response = client.get("/jobs", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "jobs" in data
        assert "count" in data
        assert isinstance(data["jobs"], list)

    def test_list_jobs_requires_auth(self, client):
        """Test listing jobs requires authentication"""
        response = client.get("/jobs")
        assert response.status_code == 401

    def test_delete_job(self, client, auth_headers):
        """Test deleting a job"""
        # Create job
        create_response = client.post(
            "/exec",
            json={"command": "dig google.com +short", "async": True},
            headers=auth_headers
        )
        job_id = create_response.json()["job_id"]

        # Delete job
        response = client.delete(f"/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id

    def test_delete_nonexistent_job(self, client, auth_headers):
        """Test deleting nonexistent job returns 404"""
        response = client.delete("/jobs/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404
