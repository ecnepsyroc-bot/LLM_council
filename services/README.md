# LLM Council Windows Services

This directory contains scripts to run LLM Council as Windows services.

## Quick Start

### Install Services (Easiest Method)

Simply double-click `install-as-service.bat` in the project root. It will request admin privileges automatically.

### Install Services (PowerShell - Run as Administrator)

```powershell
cd services
.\install-services.ps1
```

This will:
- Download NSSM (Non-Sucking Service Manager) if not present
- Install backend as `LLMCouncil-Backend` service
- Install frontend as `LLMCouncil-Frontend` service
- Configure auto-start on Windows boot
- Start both services

### Manage Services

```powershell
.\manage-services.ps1 status   # Check service status
.\manage-services.ps1 start    # Start services
.\manage-services.ps1 stop     # Stop services
.\manage-services.ps1 restart  # Restart services
.\manage-services.ps1 logs     # View recent logs
```

### Uninstall Services

Double-click `uninstall-service.bat` in the project root, or run:

```powershell
.\install-services.ps1 -Uninstall
```

## Service Details

| Service | Port | Description |
|---------|------|-------------|
| LLMCouncil-Backend | 8001 | FastAPI backend server |
| LLMCouncil-Frontend | 5173 | Vite development server |

## Log Files

Logs are stored in the `logs/` directory at the project root:
- `backend.log` - Backend output
- `backend-error.log` - Backend errors
- `frontend.log` - Frontend output
- `frontend-error.log` - Frontend errors

Logs are automatically rotated when they exceed 1MB.

## Troubleshooting

### Services won't start
1. Check logs: `.\manage-services.ps1 logs`
2. Ensure Python and npm are in PATH
3. Verify dependencies are installed (`npm run install:all`)

### Port conflicts
- Backend uses port 8001
- Frontend uses port 5173
- Check for conflicts: `netstat -ano | findstr "8001 5173"`

### Manual service control
```powershell
# Windows Services Manager
services.msc

# Command line
sc query LLMCouncil-Backend
sc query LLMCouncil-Frontend
```
