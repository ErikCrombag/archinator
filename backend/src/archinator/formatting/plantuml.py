from __future__ import annotations
from ..models import ArchiMateModel

# ArchiMate element type → PlantUML stdlib macro (Category_TypeName)
# Pattern: {Layer}_{TypeWithoutLayerPrefix}
# Source: https://plantuml.com/archimate-diagram
_ELEMENT_MACRO: dict[str, str] = {
    # Strategy
    "Resource":               "Strategy_Resource",
    "Capability":             "Strategy_Capability",
    "CourseOfAction":         "Strategy_CourseOfAction",
    "ValueStream":            "Strategy_ValueStream",
    # Business – Active Structure
    "BusinessActor":          "Business_Actor",
    "BusinessRole":           "Business_Role",
    "BusinessCollaboration":  "Business_Collaboration",
    "BusinessInterface":      "Business_Interface",
    # Business – Behavior
    "BusinessProcess":        "Business_Process",
    "BusinessFunction":       "Business_Function",
    "BusinessInteraction":    "Business_Interaction",
    "BusinessEvent":          "Business_Event",
    "BusinessService":        "Business_Service",
    # Business – Passive Structure
    "BusinessObject":         "Business_Object",
    "Representation":         "Business_Representation",
    "Contract":               "Business_Contract",
    "Product":                "Business_Product",
    # Application – Active Structure
    "ApplicationComponent":   "Application_Component",
    "ApplicationCollaboration":"Application_Collaboration",
    "ApplicationInterface":   "Application_Interface",
    # Application – Behavior
    "ApplicationProcess":     "Application_Process",
    "ApplicationFunction":    "Application_Function",
    "ApplicationInteraction": "Application_Interaction",
    "ApplicationEvent":       "Application_Event",
    "ApplicationService":     "Application_Service",
    # Application – Passive Structure
    "DataObject":             "Application_DataObject",
    # Technology – Active Structure
    "Node":                   "Technology_Node",
    "Device":                 "Technology_Device",
    "SystemSoftware":         "Technology_SystemSoftware",
    "TechnologyCollaboration":"Technology_Collaboration",
    "TechnologyInterface":    "Technology_Interface",
    "CommunicationNetwork":   "Technology_CommunicationNetwork",
    "Path":                   "Technology_Path",
    # Technology – Behavior
    "TechnologyProcess":      "Technology_Process",
    "TechnologyFunction":     "Technology_Function",
    "TechnologyInteraction":  "Technology_Interaction",
    "TechnologyEvent":        "Technology_Event",
    "TechnologyService":      "Technology_Service",
    # Technology – Passive Structure
    "Artifact":               "Technology_Artifact",
    # Physical
    "Equipment":              "Physical_Equipment",
    "Facility":               "Physical_Facility",
    "DistributionNetwork":    "Physical_DistributionNetwork",
    "Material":               "Physical_Material",
    # Motivation
    "Stakeholder":            "Motivation_Stakeholder",
    "Driver":                 "Motivation_Driver",
    "Assessment":             "Motivation_Assessment",
    "Goal":                   "Motivation_Goal",
    "Outcome":                "Motivation_Outcome",
    "Principle":              "Motivation_Principle",
    "Requirement":            "Motivation_Requirement",
    "Constraint":             "Motivation_Constraint",
    "Meaning":                "Motivation_Meaning",
    "Value":                  "Motivation_Value",
    # Implementation & Migration
    "WorkPackage":            "Implementation_WorkPackage",
    "Deliverable":            "Implementation_Deliverable",
    "ImplementationEvent":    "Implementation_Event",
    "Plateau":                "Implementation_Plateau",
    "Gap":                    "Implementation_Gap",
    # Composite
    "Grouping":               "Grouping",
    "Location":               "Motivation_Location",
    "AndJunction":            "Junction_And",
    "OrJunction":             "Junction_Or",
}

# ArchiMate relationship type → PlantUML Rel_ macro name
_REL_MACRO: dict[str, str] = {
    "Composition":    "Rel_Composition",
    "Aggregation":    "Rel_Aggregation",
    "Assignment":     "Rel_Assignment",
    "Realization":    "Rel_Realization",
    "Serving":        "Rel_Serving",
    "Access":         "Rel_Access",
    "Influence":      "Rel_Influence",
    "Association":    "Rel_Association",
    "Triggering":     "Rel_Triggering",
    "Flow":           "Rel_Flow",
    "Specialization": "Rel_Specialization",
}


def _rel_macro(r) -> str:
    """Pick the correct Rel_ macro based on relationship type and sub-type modifiers."""
    if r.type == "Access":
        # access_type values: Read, Write, ReadWrite (case-insensitive)
        at = (r.access_type or "").lower().replace("-", "").replace("_", "")
        if at in ("read", "r"):
            return "Rel_Access_r"
        if at in ("write", "w"):
            return "Rel_Access_w"
        if at in ("readwrite", "rw", "read-write"):
            return "Rel_Access_rw"
        return "Rel_Access"
    if r.type == "Association":
        # directed if name is set or access_type hints at directionality
        if r.name:
            return "Rel_Association_dir"
        return "Rel_Association"
    return _REL_MACRO.get(r.type, "Rel_Association")


def render(model: ArchiMateModel) -> str:
    lines = [
        "@startuml",
        "!include <archimate/Archimate>",
        "",
    ]

    # Group elements by layer for visual package grouping
    layers: dict[str, list] = {}
    for e in model.elements:
        layers.setdefault(e.layer, []).append(e)

    for layer, elems in layers.items():
        lines.append(f'package "{layer}" {{')
        for e in elems:
            macro = _ELEMENT_MACRO.get(e.type, "Grouping")
            safe_id = _safe_id(e.id)
            safe_name = e.name.replace('"', "'")
            lines.append(f'  {macro}({safe_id}, "{safe_name}")')
        lines.append("}")
        lines.append("")

    for r in model.relationships:
        src = _safe_id(r.source_id)
        tgt = _safe_id(r.target_id)
        macro = _rel_macro(r)
        label = r.type if not r.name else f"{r.name} [{r.type}]"
        safe_label = label.replace('"', "'")
        lines.append(f'{macro}({src}, {tgt}, "{safe_label}")')

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines)


def _safe_id(eid: str) -> str:
    return "e_" + eid.replace("-", "_").replace(".", "_")
