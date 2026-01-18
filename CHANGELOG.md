# Changelog

All notable changes to LLM Council will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-18

### Added

#### Core Features
- **Three-stage deliberation system**: Query multiple LLMs, anonymously evaluate responses, and synthesize a final answer
- **Council of LLMs**: Support for Claude, GPT-4, Gemini, Grok, DeepSeek, and other models via OpenRouter
- **Anonymous peer review**: Models evaluate responses without knowing which model produced them
- **Aggregate rankings**: Combined rankings showing model consensus across all evaluations
- **Streaming responses**: Real-time updates via Server-Sent Events (SSE)

#### User Interface
- **Conversation management**: Create, rename, pin, and delete conversations
- **Tabbed stage views**: Easily navigate between individual model responses
- **Expandable stages**: Show/hide each deliberation stage
- **Markdown rendering**: Full markdown support with syntax highlighting

#### Authentication & Security
- **API key authentication**: Secure API access with key-based auth
- **Permission system**: Read, write, admin, and stream permissions
- **Rate limiting**: Configurable per-key and global rate limits
- **Security headers**: CSP, X-Frame-Options, and other security headers
- **Audit logging**: Track API key usage and events

#### Data Management
- **SQLite storage**: Reliable database storage for conversations
- **Migration tools**: Import from JSON, verify data integrity
- **Backup system**: Automated backups with compression and retention

#### Infrastructure
- **Docker support**: Production-ready Dockerfile and compose configuration
- **Health endpoints**: Liveness, readiness, and detailed health checks
- **Structured logging**: JSON logging for production, colored text for development
- **Environment configuration**: Full configuration via environment variables

#### Documentation
- **User Guide**: Complete guide for end users
- **API Documentation**: Full REST API reference with examples
- **Deployment Guide**: Production deployment instructions

### Architecture

- Modular backend with separate packages for auth, council, database, security, and streaming
- FastAPI-based REST API with async support
- React frontend with Vite build system
- OpenRouter integration for multi-model access

### Technical Details

- Python 3.11+ required
- Node.js 18+ for frontend build
- SQLite database (production-ready)
- Pydantic v2 for data validation
- Circuit breaker pattern for API resilience

---

## [0.9.0] - 2024-01-10 (Pre-release)

### Added
- Initial implementation of three-stage deliberation
- Basic conversation storage with JSON files
- Frontend React application
- OpenRouter client with retry logic

### Known Issues
- JSON storage not suitable for production
- No authentication system
- Limited error handling

---

## Upgrade Notes

### Upgrading from 0.9.x to 1.0.0

1. **Database Migration Required**
   ```bash
   python scripts/migrate_json_to_sqlite.py --verify
   ```

2. **Environment Changes**
   - Copy `.env.example` to `.env`
   - Review all new configuration options

3. **Authentication**
   - Create initial admin key:
     ```bash
     python -m backend.auth.bootstrap
     ```
   - Update API clients to include `X-API-Key` header

4. **Breaking Changes**
   - API endpoints now require authentication (unless `BYPASS_AUTH=true`)
   - Response format includes additional metadata
   - Configuration moved to environment variables

---

## Roadmap

### 1.1.0 (Planned)
- [ ] Custom council configuration via UI
- [ ] Export conversations to markdown/PDF
- [ ] Model performance analytics
- [ ] WebSocket support for real-time updates

### 1.2.0 (Planned)
- [ ] Multi-user support
- [ ] Conversation sharing
- [ ] Custom ranking criteria
- [ ] Plugin system for custom models

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
