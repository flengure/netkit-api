FROM python:3.11-slim

# Install all network/security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    openssh-client ca-certificates curl wget git bsdmainutils \
    # Network scanning
    nmap masscan \
    # Service probing
    netcat-openbsd \
    # DNS tools
    dnsutils whois \
    # SSL/TLS auditing
    sslscan \
    # Web inspection
    httpie ruby \
    # Network diagnostics
    traceroute mtr-tiny iputils-ping iproute2 \
    # Perl dependencies for nikto
    libnet-ssleay-perl libcrypt-ssleay-perl \
    # Build dependencies (for some Python packages)
    gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install nikto from GitHub (not in Debian repos)
RUN curl -L https://github.com/sullo/nikto/archive/2.5.0.tar.gz | \
    tar xz -C /opt && \
    ln -s /opt/nikto-2.5.0/program/nikto.pl /usr/local/bin/nikto && \
    chmod +x /usr/local/bin/nikto && \
    ln -s /opt/nikto-2.5.0/program /opt/nikto-2.5.0/program/nikto

# Install testssl.sh (script-based tool)
RUN curl -L https://github.com/drwetter/testssl.sh/archive/v3.0.8.tar.gz | \
    tar xz -C /opt && \
    ln -s /opt/testssl.sh-3.0.8/testssl.sh /usr/local/bin/testssl.sh && \
    chmod +x /usr/local/bin/testssl.sh

# Install whatweb
RUN curl -L https://github.com/urbanadventurer/WhatWeb/archive/v0.5.5.tar.gz | \
    tar xz -C /opt && \
    ln -s /opt/WhatWeb-0.5.5/whatweb /usr/local/bin/whatweb && \
    chmod +x /usr/local/bin/whatweb

# Configure SSH with sane defaults
RUN mkdir -p /etc/ssh && printf '%s\n' \
    'Host *' \
    '    PreferredAuthentications publickey' \
    '    PasswordAuthentication no' \
    '    KbdInteractiveAuthentication no' \
    '    StrictHostKeyChecking no' \
    '    UserKnownHostsFile /dev/null' \
    '    LogLevel ERROR' \
    > /etc/ssh/ssh_config

# Install uv for fast Python dependency management (as root)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements and install Python dependencies with uv (as root)
COPY api/requirements.txt /tmp/requirements.txt
RUN uv pip install --system --no-cache -r /tmp/requirements.txt

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/netkit-api
RUN chmod +x /usr/local/bin/netkit-api

# Create app directory structure
RUN mkdir -p /app/api /app/mcp /root/.ssh

# Copy application code
COPY base_executor.py /app/
COPY rate_limiter.py /app/
COPY target_validator.py /app/
COPY job_manager.py /app/
COPY capabilities.py /app/
COPY config_loader.py /app/
COPY executors.py /app/
COPY oidc_validator.py /app/
COPY api/api.py /app/api/
COPY mcp/server.py /app/mcp/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    API_PORT=8090 \
    SSH_DIR=/root/.ssh \
    PYTHONPATH=/app

# Run as root (container has read_only and cap_add restrictions for security)
WORKDIR /root

# Expose API port (only used in --http mode)
EXPOSE 8090

# Entrypoint defaults to MCP stdio server
# Use --http flag for HTTP API mode
ENTRYPOINT ["/usr/local/bin/netkit-api"]
