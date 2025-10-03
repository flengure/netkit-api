#!/bin/bash
# netkit-api Test Examples
# Make executable: chmod +x test_examples.sh

API_KEY="test-key-123"
BASE_URL="http://localhost:8090"

echo "🧪 netkit-api Test Suite"
echo "========================"
echo

# Test 1: Health Check
echo "1️⃣  Health Check (no auth)"
curl -s "${BASE_URL}/healthz" | jq '.ok, .version, .capabilities.features'
echo

# Test 2: List Tools
echo "2️⃣  List Available Tools"
curl -s "${BASE_URL}/tools" | jq '.tools | keys | length'
echo "   Tools available"
echo

# Test 3: DNS Lookup
echo "3️⃣  DNS Lookup (dig)"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "dig google.com +short"}' | jq -c '{tool, duration: .duration_seconds, ips: (.stdout | split("\n") | map(select(length > 0)))}'
echo

# Test 4: MX Records
echo "4️⃣  MX Records (dig)"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "dig gmail.com MX +short"}' | jq '.stdout' -r
echo

# Test 5: Host Lookup
echo "5️⃣  Host Lookup"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "host google.com"}' | jq '.stdout' -r
echo

# Test 6: Whois (first 10 lines)
echo "6️⃣  Whois Lookup"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "whois google.com"}' | jq '.stdout' -r | head -10
echo

# Test 7: Ping
echo "7️⃣  Ping Test"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "ping -c 3 8.8.8.8"}' | jq -c '{tool, exit_code, duration: .duration_seconds}'
echo

# Test 8: Nmap TCP Scan
echo "8️⃣  Nmap TCP Scan"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "nmap -sT -p 80,443 scanme.nmap.org", "timeout": 30}' | jq -c '{tool, exit_code, duration: .duration_seconds}'
echo

# Test 9: Curl Headers
echo "9️⃣  Curl - Fetch Headers"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "curl -sI https://www.google.com"}' | jq '.stdout' -r | head -5
echo

# Test 10: Curl JSON API
echo "🔟 Curl - GitHub API"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "curl -s https://api.github.com/users/github"}' | jq '.stdout' | jq -r 'fromjson | {login, name, public_repos}'
echo

# Test 11: Using Args Array
echo "1️⃣1️⃣  Dig with Args Array"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"tool": "dig", "args": ["cloudflare.com", "A", "+short"]}' | jq '.stdout' -r
echo

# Test 12: Tool + Command Format
echo "1️⃣2️⃣  Nmap with Tool + Command"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"tool": "nmap", "command": "-sT -p 22,80 scanme.nmap.org", "timeout": 25}' | jq -c '{tool, exit_code, duration: .duration_seconds}'
echo

# Test 13: Async Job
echo "1️⃣3️⃣  Async Job (nmap scan)"
JOB_RESPONSE=$(curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "nmap -sT -p 1-100 scanme.nmap.org", "async": true}')
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "   Job created: $JOB_ID"
echo "   Status: $(echo $JOB_RESPONSE | jq -r '.status')"
echo

# Test 14: Check Job Status
echo "1️⃣4️⃣  Check Job Status"
sleep 2
curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/jobs/${JOB_ID}" | jq '{job_id, status, tool}'
echo

# Test 15: List All Jobs
echo "1️⃣5️⃣  List All Jobs"
curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/jobs" | jq '.count'
echo "   total jobs"
echo

# Test 16: Netcat Port Check
echo "1️⃣6️⃣  Netcat Port Check"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "nc -zv google.com 80", "timeout": 10}' | jq -c '{exit_code, stderr: (.stderr[:50])}'
echo

# Test 17: Custom Timeout
echo "1️⃣7️⃣  Timeout Test (will timeout)"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "ping -c 100 8.8.8.8", "timeout": 3}' | jq -c '{exit_code, stderr}'
echo

# Test 18: Error - Invalid Tool
echo "1️⃣8️⃣  Error Handling - Invalid Tool"
curl -s -X POST "${BASE_URL}/exec" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"command": "invalidtool test"}' | jq '.detail'
echo

# Test 19: Error - No Auth
echo "1️⃣9️⃣  Error Handling - No Auth"
curl -s -X POST "${BASE_URL}/exec" \
  -H "Content-Type: application/json" \
  --data '{"command": "dig google.com"}' | jq '.detail'
echo

# Test 20: API Stats
echo "2️⃣0️⃣  API Statistics"
curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/stats" | jq '{tools, rate_limiter: .rate_limiter.total_requests, jobs: .job_manager.total_jobs}'
echo

echo "✅ Test suite complete!"
echo
echo "📖 Interactive docs: http://localhost:8090/docs"
echo "📘 ReDoc: http://localhost:8090/redoc"
