# Dejavara Port Registry

This document defines the port allocations for development services on Dejavara (development laptop).

## Port Allocation Ranges (Cambium Standard)

| Range | Purpose |
|-------|---------|
| 5000-5049 | APIs |
| 5050-5099 | Dev services |
| 5170-5199 | Frontend dev servers |
| 5400-5499 | Databases |
| 8000-8099 | Backend services |
| 8300-8399 | Utilities |

## Dejavara Active Ports

| Port | Service | Category | Status |
|------|---------|----------|--------|
| 5173 | LLM Council Frontend | Frontend Dev | Active |
| 5433 | PostgreSQL SSH Tunnel | Database (tunneled) | On-demand |
| 8001 | LLM Council Backend | Backend Service | Active |

## Service Details

### LLM Council Frontend (5173)
- **Technology**: Vite + React
- **Start Command**: `cd frontend && npm run dev`
- **URL**: http://localhost:5173
- **Notes**: May use 5174 if 5173 is occupied

### LLM Council Backend (8001)
- **Technology**: Python + FastAPI + Uvicorn
- **Start Command**: `python -m backend.main`
- **URL**: http://localhost:8001
- **Health Check**: http://localhost:8001/health

### PostgreSQL SSH Tunnel (5433)
- **Remote**: Cambium:5432
- **Start Command**: `ssh -L 5433:localhost:5432 cambium -N`
- **Notes**: Used for database access to Cambium server

## External Services (via Cambium)

| Service | Access Method | URL/Port |
|---------|--------------|----------|
| Cambium.Api | Cloudflare Tunnel | https://api.luxifyspecgen.com |
| PostgreSQL | SSH Tunnel | localhost:5433 → Cambium:5432 |

## Port Conflict Resolution

If a port is already in use:

```powershell
# Find process using port
netstat -ano | findstr :<PORT>

# Kill process by PID
taskkill /PID <PID> /F
```

## Adding New Services

When adding a new service:

1. Choose a port from the appropriate range
2. Update this registry
3. Update `scripts/check-ports.ps1`
4. Document in service README
