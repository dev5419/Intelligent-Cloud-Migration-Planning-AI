from .models import Application


MOCK_APPLICATIONS = [
    Application(
        id="app-001",
        name="Customer Portal",
        owner="Digital Products",
        technology="Python / PostgreSQL",
        criticality="High",
        dependencies=["app-002"],
    ),
    Application(
        id="app-002",
        name="Identity Service",
        owner="Platform Engineering",
        technology="Java / PostgreSQL",
        criticality="High",
        dependencies=[],
    ),
    Application(
        id="app-003",
        name="Reporting Dashboard",
        owner="Analytics",
        technology="Node.js / MongoDB",
        criticality="Medium",
        dependencies=["app-001"],
    ),
    Application(
        id="app-004",
        name="Legacy Batch Processor",
        owner="Operations",
        technology="COBOL / Mainframe",
        criticality="Low",
        dependencies=[],
    ),
]

MOCK_RECOMMENDATIONS = {
    "app-001": ("Replatform", 0.89, "Move the application to managed compute and database services with limited code changes."),
    "app-002": ("Rehost", 0.82, "The service is stable and can move to cloud infrastructure with minimal changes."),
    "app-003": ("Refactor", 0.76, "Refactoring can improve scalability and reduce the impact of its upstream dependency."),
    "app-004": ("Retain", 0.68, "Retain the workload temporarily while its mainframe replacement is evaluated."),
}

MOCK_COSTS = {
    "app-001": (420.0, 350.0, 520.0, 62.0),
    "app-002": (280.0, 230.0, 360.0, 48.0),
    "app-003": (190.0, 150.0, 250.0, 55.0),
    "app-004": (95.0, 75.0, 125.0, 34.0),
}


