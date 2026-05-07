from __future__ import annotations
from ..models import ArchiMateModel

# ArchiMate element type → PlantUML ArchiMate macro / stereotype
# Requires the ArchiMate PlantUML library (stdlib or custom)
_STEREOTYPE = {
    # Strategy
    "Resource":        "archimate #Strategy",
    "Capability":      "archimate #Strategy",
    "CourseOfAction":  "archimate #Strategy",
    "ValueStream":     "archimate #Strategy",
    # Business
    "BusinessActor":         "archimate #Business",
    "BusinessRole":          "archimate #Business",
    "BusinessCollaboration": "archimate #Business",
    "BusinessInterface":     "archimate #Business",
    "BusinessProcess":       "archimate #Business",
    "BusinessFunction":      "archimate #Business",
    "BusinessInteraction":   "archimate #Business",
    "BusinessEvent":         "archimate #Business",
    "BusinessService":       "archimate #Business",
    "BusinessObject":        "archimate #Business",
    "Representation":        "archimate #Business",
    "Contract":              "archimate #Business",
    "Product":               "archimate #Business",
    # Application
    "ApplicationComponent":    "archimate #Application",
    "ApplicationCollaboration":"archimate #Application",
    "ApplicationInterface":    "archimate #Application",
    "ApplicationProcess":      "archimate #Application",
    "ApplicationFunction":     "archimate #Application",
    "ApplicationInteraction":  "archimate #Application",
    "ApplicationEvent":        "archimate #Application",
    "ApplicationService":      "archimate #Application",
    "DataObject":              "archimate #Application",
    # Technology
    "Node":                    "archimate #Technology",
    "Device":                  "archimate #Technology",
    "SystemSoftware":          "archimate #Technology",
    "TechnologyCollaboration": "archimate #Technology",
    "TechnologyInterface":     "archimate #Technology",
    "CommunicationNetwork":    "archimate #Technology",
    "Path":                    "archimate #Technology",
    "TechnologyProcess":       "archimate #Technology",
    "TechnologyFunction":      "archimate #Technology",
    "TechnologyInteraction":   "archimate #Technology",
    "TechnologyEvent":         "archimate #Technology",
    "TechnologyService":       "archimate #Technology",
    "Artifact":                "archimate #Technology",
    # Physical
    "Equipment":           "archimate #Physical",
    "Facility":            "archimate #Physical",
    "DistributionNetwork": "archimate #Physical",
    "Material":            "archimate #Physical",
    # Motivation
    "Stakeholder":  "archimate #Motivation",
    "Driver":       "archimate #Motivation",
    "Assessment":   "archimate #Motivation",
    "Goal":         "archimate #Motivation",
    "Outcome":      "archimate #Motivation",
    "Principle":    "archimate #Motivation",
    "Requirement":  "archimate #Motivation",
    "Constraint":   "archimate #Motivation",
    "Meaning":      "archimate #Motivation",
    "Value":        "archimate #Motivation",
    # Implementation
    "WorkPackage":         "archimate #Implementation",
    "Deliverable":         "archimate #Implementation",
    "ImplementationEvent": "archimate #Implementation",
    "Plateau":             "archimate #Implementation",
    "Gap":                 "archimate #Implementation",
    # Composite
    "Grouping": "archimate",
    "Location":  "archimate",
}

_ARROW = {
    "Composition":   "*--",
    "Aggregation":   "o--",
    "Assignment":    "-->",
    "Realization":   "..|>",
    "Serving":       "-->",
    "Access":        "..>",
    "Influence":     "..>",
    "Association":   "--",
    "Triggering":    "-[#red]->",
    "Flow":          "-[#blue]->",
    "Specialization":"--|>",
}


def render(model: ArchiMateModel) -> str:
    lines = [
        "@startuml",
        "!include <archimate/Archimate>",
        "",
    ]

    # Group elements by layer for visual grouping
    layers: dict[str, list] = {}
    for e in model.elements:
        layers.setdefault(e.layer, []).append(e)

    for layer, elems in layers.items():
        lines.append(f"package \"{layer}\" {{")
        for e in elems:
            stereotype = _STEREOTYPE.get(e.type, "archimate")
            safe_id = _safe_id(e.id)
            safe_name = e.name.replace('"', "'")
            lines.append(f'  {stereotype} "{safe_name}" as {safe_id} <<{e.type}>>')
        lines.append("}")
        lines.append("")

    for r in model.relationships:
        src = _safe_id(r.source_id)
        tgt = _safe_id(r.target_id)
        arrow = _ARROW.get(r.type, "-->")
        label = f' : "{r.type}"' if not r.name else f' : "{r.name} [{r.type}]"'
        lines.append(f"{src} {arrow} {tgt}{label}")

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


def _safe_id(eid: str) -> str:
    return "e_" + eid.replace("-", "_").replace(".", "_")
