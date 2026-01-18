# LLM Council Deployment Guide

This guide covers deploying LLM Council to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start with Docker](#quick-start-with-docker)
3. [Manual Deployment](#manual-deployment)
4. [Reverse Proxy Setup](#reverse-proxy-setup)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Monitoring](#monitoring)
7. [Backup and Restore](#backup-and-restore)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required

- **OpenRouter API Key**: Get one at [openrouter.ai/keys](https://openrouter.ai/keys)
- **Server Requirements**:
  - CPU: 2+ cores
  - RAM: 2GB minimum, 4GB recommended
  - Storage: 10GB for application and data

### For Docker Deployment

- Docker 20.10+
- Docker Compose 2.0+ (optional but recommended)

### For Manual Deployment

- Python 3.11 or 3.12
- Node.js 18 or 20 (for frontend build)
- pip or uv package manager

---

## Quick Start with Docker

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/llm-council.git
cd llm-council

# Copy and configure environment
cp .env.example .env
nano .env  # Add your OPENROUTER_API_KEY
```

### 2. Build and Run

```bash
# Build the image
docker-compose -f docker-compose.prod.yml build

# Start the service
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

### 3. Create Admin API Key

```bash
docker-compose -f docker-compose.prod.yml exec llm-council \
  python -m backend.auth.bootstrap --name "Admin" --non-interactive
```

Save the displayed API key securely!

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:8001/health

# Test API (with authentication)
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8001/api/config
```

---

## Manual Deployment

### 1. System Setup

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3.12 python3.12-venv nodejs npm

# Create application user
sudo useradd -m -s /bin/bash council
sudo su - council
```

### 2. Install Application

```bash
# Clone repository
git clone https://github.com/your-org/llm-council.git
cd llm-council

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e ".[production]"

# Build frontend
cd frontend
npm ci
npm run build
cd ..
```

### 3. Configure

```bash
# Create environment file
cp .env.example .env
nano .env
```

Required settings:
```env
OPENROUTER_API_KEY=your_key_here
LOG_LEVEL=INFO
LOG_FORMAT=json
DATABASE_PATH=data/council.db
```

### 4. Initialize Database

```bash
# Initialize database and create admin key
python -m backend.auth.bootstrap --name "Admin" --non-interactive
```

### 5. Create Systemd Service

```bash
sudo nano /etc/systemd/system/llm-council.service
```

```ini
[Unit]
Description=LLM Council Service
After=network.target

[Service]
Type=simple
User=council
Group=council
WorkingDirectory=/home/council/llm-council
Environment=PATH=/home/council/llm-council/.venv/bin
EnvironmentFile=/home/council/llm-council/.env
ExecStart=/home/council/llm-council/.venv/bin/python -m backend.main
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/council/llm-council/data /home/council/llm-council/logs

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable llm-council
sudo systemctl start llm-council
sudo systemctl status llm-council
```

---

## Reverse Proxy Setup

### Nginx

```nginx
# /etc/nginx/sites-available/llm-council
upstream llm_council {
    server 127.0.0.1:8001;
    keepalive 32;
}

server {
    listen 80;
    server_name council.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name council.example.com;

    # SSL configuration (see SSL section)
    ssl_certificate /etc/letsencrypt/live/council.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/council.example.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Proxy settings
    location / {
        proxy_pass http://llm_council;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # SSE support
    location ~ /api/.*/stream {
        proxy_pass http://llm_council;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/llm-council /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Caddy

```caddyfile
# /etc/caddy/Caddyfile
council.example.com {
    reverse_proxy localhost:8001 {
        # Health check
        health_uri /health
        health_interval 30s

        # Headers
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # SSE endpoints need special handling
    @sse path_regexp sse /api/.*/stream
    handle @sse {
        reverse_proxy localhost:8001 {
            transport http {
                compression off
            }
            flush_interval -1
        }
    }
}
```

---

## SSL/TLS Configuration

### Using Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d council.example.com

# Auto-renewal is configured automatically
sudo systemctl status certbot.timer
```

### Manual Certificate

If you have existing certificates:

```bash
# Copy certificates
sudo cp your_certificate.pem /etc/ssl/certs/council.pem
sudo cp your_private_key.pem /etc/ssl/private/council.key

# Set permissions
sudo chmod 644 /etc/ssl/certs/council.pem
sudo chmod 600 /etc/ssl/private/council.key
```

Update nginx configuration to use these paths.

---

## Monitoring

### Health Checks

The application provides three health endpoints:

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `/health` | Liveness check | No |
| `/health/ready` | Readiness check | No |
| `/health/detailed` | Full status | Admin |

### Prometheus Metrics (Optional)

Add to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'llm-council'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: /metrics
    bearer_token: YOUR_API_KEY
```

### Log Aggregation

Logs are output in JSON format (production mode) for easy parsing:

```bash
# View recent logs
docker-compose -f docker-compose.prod.yml logs --tail 100

# Stream logs
docker-compose -f docker-compose.prod.yml logs -f

# Parse with jq
docker-compose -f docker-compose.prod.yml logs --no-color | jq -r '.message'
```

### Alerting

Set up alerts for:

- Health check failures
- High error rates (5xx responses)
- Rate limit exhaustion
- OpenRouter API failures

---

## Backup and Restore

### Automated Backups

```bash
# Create a backup
python scripts/backup_db.py

# List backups
python scripts/backup_db.py --list

# Verify a backup
python scripts/backup_db.py --verify backups/council_20240118_120000.db.gz
```

### Backup Schedule (Cron)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /home/council/llm-council && .venv/bin/python scripts/backup_db.py --retention-days 30
```

### Restore from Backup

```bash
# Restore (will prompt for confirmation)
python scripts/backup_db.py --restore backups/council_20240118_120000.db.gz

# Force restore without confirmation
python scripts/backup_db.py --restore backups/council_20240118_120000.db.gz --force
```

### Data Migration

To migrate from JSON storage to SQLite:

```bash
# Dry run first
python scripts/migrate_json_to_sqlite.py --dry-run

# Migrate with verification
python scripts/migrate_json_to_sqlite.py --verify

# Force re-migration of existing conversations
python scripts/migrate_json_to_sqlite.py --force
```

---

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check logs
journalctl -u llm-council -n 50

# Common causes:
# - Missing OPENROUTER_API_KEY
# - Port already in use
# - Permission issues on data directory
```

#### Database Errors

```bash
# Verify database integrity
python scripts/verify_data.py

# Fix common issues
python scripts/verify_data.py --fix
```

#### High Memory Usage

- Reduce `COUNCIL_MODELS` to fewer models
- Ensure no memory leaks in long-running processes
- Check for orphaned database connections

#### Slow Responses

- Verify OpenRouter API is reachable
- Check network latency to OpenRouter
- Review model selection (some models are slower)

#### Authentication Issues

```bash
# List API keys
python scripts/manage_keys.py list

# Create new key
python scripts/manage_keys.py create --name "Test" --permissions read,write

# Check key status
python scripts/manage_keys.py status KEY_PREFIX
```

### Debug Mode

For debugging, temporarily enable:

```env
LOG_LEVEL=DEBUG
BYPASS_AUTH=true  # Development only!
```

### Getting Help

1. Check the logs first
2. Verify data integrity with `verify_data.py`
3. Test API endpoints with curl
4. Open an issue on GitHub with:
   - Error messages
   - Steps to reproduce
   - Environment details

---

## Security Checklist

Before going to production:

- [ ] Set strong `OPENROUTER_API_KEY`
- [ ] Set `BYPASS_AUTH=false`
- [ ] Create admin API key and store securely
- [ ] Enable HTTPS with valid certificate
- [ ] Configure firewall (only expose 443)
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Review rate limits
- [ ] Test disaster recovery procedure

---

*For additional help, see the [API Documentation](API.md) or [User Guide](USER_GUIDE.md).*
