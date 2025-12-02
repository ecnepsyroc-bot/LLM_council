# Luxify Systems Integration Plan: Edge Node System & Millwork Workflow System

This document outlines a plan to integrate the audited Edge Node System with your Millwork Workflow System running on your Dejavara-P16 Gen 2 laptop, ultimately contributing to the larger Luxify Systems platform. It leverages insights from the audit report you provided and addresses the priority of security, testing, and feature roll out.

## I. Executive Summary & Key Recommendations:

The Edge Node System represents a solid foundation, built on a modern .NET 8.0 stack with a clean architecture and robust API. However, the audit identified key weaknesses that must be addressed before any expanded deployment or integration:

- **Critical Security Gaps:** The lack of authentication/authorization is a showstopper. We must implement JWT authentication and role-based access control IMMEDIATELY.
- **Lack of Testing:** Code reliability must be ensured through robust unit, integration, and E2E tests.
- **Deployment Readiness:** Configuration and deployment pipelines (Docker, CI/CD) must be established for seamless integration.
- **Feature Prioritization:** Based on immediate business need identify which set of features are absolutely necessary for the initial roll out.

Addressing these weaknesses is paramount. Prioritize **II. Security Enhancements** then **X. Testing Strategy** below.

## II. Security Enhancements (CRITICAL):

- **Implement JWT Authentication:** Implement a JWT (JSON Web Token) authentication mechanism as per .NET 8.0 standards. Refer to Microsoft’s documentation on Identity Framework for best practices.
- **Role-Based Authorization:** Introduce role-based access control (RBAC) to restrict access to endpoints based on user roles (PM, Shop Manager, Operator, etc.). Implement role definitions within the JWT claims.
- **Secrets Management:** Move all sensitive information (database passwords, API keys, etc.) out of `appsettings.json` and into Environment Variables or, preferably, a dedicated secrets management solution like Azure Key Vault. Access secrets at runtime via configuration providers.
- **HTTPS Enforcement:** Ensure that the application enforces HTTPS for all communication channels. Configure TLS/SSL certificates properly and enable HSTS (HTTP Strict Transport Security) headers to prevent downgrade attacks.

## III. Integration Architecture and Network Setup:

We recommend a phased integration approach:

### Phase 1: Isolated Network Configuration (Week 1)

Configure a secure, isolated network environment. Consider these points:

- Static IPs are recommended but configure a isolated subnet is a minimum: Example: Shop Computer (10.0.0.10), Dejavara-P16 (10.0.0.20), SQL Server (10.0.0.5).
- Firewall Rules: Implement rules that allow communication on only the necessary ports.
- Database Environment: Centralize SQL Server access with network-level access control.

```
┌─────────────────┐    Network    ┌─────────────────┐
│   Shop Computer │◄──────────────►│ Dejavara-P16    │
│                 │   10.0.0.0/24  │                 │
│ Edge Node API   │                │ Millwork Dev    │
│ Port: 5000      │                │ Port: 5001      │
└─────────────────┘                └─────────────────┘
```

**SQL Connection Strings:** Implement a shared authentication setup using shared database.

```json
{
  "ConnectionStrings": {
    "EdgeNode": "Server=10.0.0.5;Database=EdgeNodeDB;User Id=luxify_edge;Password={env_var};",
    "Millwork": "Server=10.0.0.5;Database=MillworkDB;User Id=luxify_millwork;Password={env_var};",
    "Shared": "Server=10.0.0.5;Database=LuxifySharedDB;User Id=luxify_shared;Password={env_var};"
  }
}
```

### Phase 2: Service Mesh Integration (Week 2)

Consider using a Luxify Gateway to proxy systems for a more secure system.

```
┌──────────────────────────────────────────────────────┐
│                 Luxify Gateway                       │
│                 Port: 8080                           │
│   ┌─────────────────┐    ┌─────────────────────────┐  │
│   │ Edge Node Proxy │    │ Millwork Workflow Proxy │  │
│   │ → :5000         │    │ → :5001                 │  │
│   └─────────────────┘    └─────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## IV. Technology Alignment:

Ensure the Millwork Workflow System aligns technologically with the Edge Node System for easier integration:

- **.NET 8.0:** Use the same runtime for both systems.
- **Entity Framework Core 8.0:** For data persistence.
- **SQL Server:** Allows for database sharing, simplified configuration.
- **SignalR:** Allows for real-time updates.
- **Clean Architecture:** Follow simliar project stucture.

## V. Millwork Workflow System Recommendations:

Modularize the Millwork system like this example:

**MillworkWorkflow.Core (Business Logic)**

```csharp
Managers/
├── ProductionManager.cs      // Job queue, scheduling
├── InventoryManager.cs       // Materials, hardware
├── QualityManager.cs         // Inspections, defects
├── ShippingManager.cs        // Delivery coordination
└── CostingManager.cs         // Labor, material costs

Services/
├── CncProgrammingService.cs  // G-code generation
├── CutListGenerator.cs       // Optimization
├── LabelPrintingService.cs   // Shop floor labels
└── TimeTrackingService.cs    // Labor tracking
```

**MillworkWorkflow.Data (Database access)**

```csharp
Entities/
├── WorkOrder.cs             // Manufacturing jobs
├── MaterialStock.cs         // Inventory tracking
├── ProductionStep.cs        // Workflow stages
├── QualityCheck.cs          // Inspection points
├── ShippingManifest.cs      // Delivery tracking
└── LaborEntry.cs           // Time tracking
```

## VI. Integration Points Between Systems:

| Edge Node Entity | Millwork Entity     | Sync Method         |
| :--------------- | :------------------ | :------------------ |
| Job              | WorkOrder           | Job ID foreign key  |
| FactoryOrder     | ProductionBatch     | FO Number reference |
| Drawing          | CncProgram          | Drawing ID + G-code |
| DrawingMaterial  | MaterialRequirement | BOM sync            |
| Message          | ProductionNote      | Cross-system chat   |

## VII. Shared Services Architecture:

Centralize common functionalities using shared libraries:

**Luxify.Shared Library:** Contains common DTOs (Data Transfer Objects) and cross-system events.

```csharp
// Common DTOs; Ex: Job
public class LuxifyJobDto
{
    public int JobId { get; set; }
    public string JobCode { get; set; }
    public DateTime CreatedDate { get; set; }
}
// Cross-system events; Ex: Job status
public class JobStatusChangedEvent
{
    public int JobId { get; set; }
    public string System { get; set; } // "edge-node" | "millwork"
    public string NewStatus { get; set; }
    public DateTime Timestamp { get; set; }
}
```

**Luxify.Auth.Service:** Offers unified authentication and authorization using JWT. Contains:

- JWT tokens valid across systems
- Role definitions

**Luxify.Sync.Service:** Manages data synchronization between systems.

## VIII. Implementation Roadmap:

- **Week 1:** Network Setup
- **Week 2:** Authentication Integration
- **Week 3:** Basic Millwork Components
- **Week 4:** Real-Time Integration
- **Week 5:** Advanced Features
- **Week 6:** Production Deployment (after THOROUGH security and testing!)

## IX. Thorough Architectural Considerations:

- **Database Schema:** Pay detailed attention to ensure compatibility between systems. Take the following questions into account.
  - Are there any audit columns(created_at, updated_at) added?
  - Double check your table names for conformity. Are there any tables that use camelCase syntax rather than snake_case?
- **API Layer:**
  - Consdider how versioning of the API is being handled.
  - Mention any API documentation standards (e.g., Swagger/OpenAPI, which you already note is there).
- **Frontend Architecture:** Note the Javascript framwork.
  - What framework is being used? (React? Angular? Vue.js? Vanilla JS?)
  - Are there any build tools being used?
  - It would be good to analyze the frontend since it is a complex problem to fix.
  - Does this frontend need to be changed if a new security measure is implemented? (authentication)?

## X. Testing Strategy:

Develop a multi-faceted testing strategy:

- **Unit Tests:** Focus on individual components (Managers, Services). Use xUnit, Moq. Provide a timeline to complete them
- **Integration Tests:** Verify interactions between different modules and external systems. Add a timeline for at least a few Integration/E2E end points to test end to end.
- **End-to-End (E2E) Tests:** Simulate user workflows to ensure the system behaves as expected.
- Implement a testing method that checks each endpoint for the correct load and speed. Add metrics to check speed.

## XI. Missing Feature Implementation:

Prioritize the "Recommended Additions" from the audit report based integrating into other sections of the Luxify system. Apply the tag or rank feature based on the greatest needs and ease of implementation.

## XII. Deployment & Monitoring:

- **Deployment Strategy:** You will need to target environment specifics (e.g., Azure App Service). After this document the process in a detailed guide.
- **Logging Methods:**
  - Add monitoring and logging methods to each point of the system.

## XIII. Network Security:

- Use strong WPA3 on your shop WiFi
- Configure firewall rules
- VPN access
- Regular security updates

## XIV. System Health Monitoring and Backup:

- **SystemHealthMonitor:** Use database connectivity and performance metrics.
- Implement Daily, Weekly and Monthly backups of all systems.

## XV. Success Metrics:

Define clear success metrics for each phase:

- **Phase 1:** Both systems communicate reliably, Jobs synchronize.
- **Phase 2:** Real-time manufacturing status, Cost Tracking, Integration
