"""
ArchiMate 3.2 rules data.
Source: The Open Group ArchiMate 3.2 Specification.
Bootstrap step may enrich/override these from PDF + opengroup.org.
"""
from __future__ import annotations

# ── Element catalogue ────────────────────────────────────────────────────────
# layer: Strategy | Business | Application | Technology | Physical
#        | Motivation | Implementation | Composite
# aspect: ActiveStructure | Behavior | PassiveStructure
#         | Motivation | Composite | Junction

ELEMENT_TYPES: dict[str, dict[str, str]] = {
    # Strategy
    "Resource":        {"layer": "Strategy", "aspect": "ActiveStructure"},
    "Capability":      {"layer": "Strategy", "aspect": "Behavior"},
    "CourseOfAction":  {"layer": "Strategy", "aspect": "Behavior"},
    "ValueStream":     {"layer": "Strategy", "aspect": "Behavior"},
    # Business – Active Structure
    "BusinessActor":         {"layer": "Business", "aspect": "ActiveStructure"},
    "BusinessRole":          {"layer": "Business", "aspect": "ActiveStructure"},
    "BusinessCollaboration": {"layer": "Business", "aspect": "ActiveStructure"},
    "BusinessInterface":     {"layer": "Business", "aspect": "ActiveStructure"},
    # Business – Behavior
    "BusinessProcess":     {"layer": "Business", "aspect": "Behavior"},
    "BusinessFunction":    {"layer": "Business", "aspect": "Behavior"},
    "BusinessInteraction": {"layer": "Business", "aspect": "Behavior"},
    "BusinessEvent":       {"layer": "Business", "aspect": "Behavior"},
    "BusinessService":     {"layer": "Business", "aspect": "Behavior"},
    # Business – Passive Structure
    "BusinessObject":  {"layer": "Business", "aspect": "PassiveStructure"},
    "Representation":  {"layer": "Business", "aspect": "PassiveStructure"},
    "Contract":        {"layer": "Business", "aspect": "PassiveStructure"},
    "Product":         {"layer": "Business", "aspect": "PassiveStructure"},
    # Application – Active Structure
    "ApplicationComponent":    {"layer": "Application", "aspect": "ActiveStructure"},
    "ApplicationCollaboration":{"layer": "Application", "aspect": "ActiveStructure"},
    "ApplicationInterface":    {"layer": "Application", "aspect": "ActiveStructure"},
    # Application – Behavior
    "ApplicationProcess":     {"layer": "Application", "aspect": "Behavior"},
    "ApplicationFunction":    {"layer": "Application", "aspect": "Behavior"},
    "ApplicationInteraction": {"layer": "Application", "aspect": "Behavior"},
    "ApplicationEvent":       {"layer": "Application", "aspect": "Behavior"},
    "ApplicationService":     {"layer": "Application", "aspect": "Behavior"},
    # Application – Passive Structure
    "DataObject": {"layer": "Application", "aspect": "PassiveStructure"},
    # Technology – Active Structure
    "Node":                    {"layer": "Technology", "aspect": "ActiveStructure"},
    "Device":                  {"layer": "Technology", "aspect": "ActiveStructure"},
    "SystemSoftware":          {"layer": "Technology", "aspect": "ActiveStructure"},
    "TechnologyCollaboration": {"layer": "Technology", "aspect": "ActiveStructure"},
    "TechnologyInterface":     {"layer": "Technology", "aspect": "ActiveStructure"},
    "CommunicationNetwork":    {"layer": "Technology", "aspect": "ActiveStructure"},
    "Path":                    {"layer": "Technology", "aspect": "ActiveStructure"},
    # Technology – Behavior
    "TechnologyProcess":     {"layer": "Technology", "aspect": "Behavior"},
    "TechnologyFunction":    {"layer": "Technology", "aspect": "Behavior"},
    "TechnologyInteraction": {"layer": "Technology", "aspect": "Behavior"},
    "TechnologyEvent":       {"layer": "Technology", "aspect": "Behavior"},
    "TechnologyService":     {"layer": "Technology", "aspect": "Behavior"},
    # Technology – Passive Structure
    "Artifact": {"layer": "Technology", "aspect": "PassiveStructure"},
    # Physical
    "Equipment":           {"layer": "Physical", "aspect": "ActiveStructure"},
    "Facility":            {"layer": "Physical", "aspect": "ActiveStructure"},
    "DistributionNetwork": {"layer": "Physical", "aspect": "ActiveStructure"},
    "Material":            {"layer": "Physical", "aspect": "PassiveStructure"},
    # Motivation
    "Stakeholder":  {"layer": "Motivation", "aspect": "ActiveStructure"},
    "Driver":       {"layer": "Motivation", "aspect": "Motivation"},
    "Assessment":   {"layer": "Motivation", "aspect": "Motivation"},
    "Goal":         {"layer": "Motivation", "aspect": "Motivation"},
    "Outcome":      {"layer": "Motivation", "aspect": "Motivation"},
    "Principle":    {"layer": "Motivation", "aspect": "Motivation"},
    "Requirement":  {"layer": "Motivation", "aspect": "Motivation"},
    "Constraint":   {"layer": "Motivation", "aspect": "Motivation"},
    "Meaning":      {"layer": "Motivation", "aspect": "Motivation"},
    "Value":        {"layer": "Motivation", "aspect": "Motivation"},
    # Implementation & Migration
    "WorkPackage":        {"layer": "Implementation", "aspect": "Behavior"},
    "Deliverable":        {"layer": "Implementation", "aspect": "PassiveStructure"},
    "ImplementationEvent":{"layer": "Implementation", "aspect": "Behavior"},
    "Plateau":            {"layer": "Implementation", "aspect": "Composite"},
    "Gap":                {"layer": "Implementation", "aspect": "Composite"},
    # Composite / cross-cutting
    "Grouping":    {"layer": "Composite", "aspect": "Composite"},
    "Location":    {"layer": "Composite", "aspect": "Composite"},
    "AndJunction": {"layer": "Composite", "aspect": "Junction"},
    "OrJunction":  {"layer": "Composite", "aspect": "Junction"},
}

# ── Relationship types ────────────────────────────────────────────────────────
RELATIONSHIP_TYPES: set[str] = {
    # Structural
    "Composition", "Aggregation", "Assignment", "Realization",
    # Dependency
    "Serving", "Access", "Influence", "Association",
    # Dynamic
    "Triggering", "Flow",
    # Other
    "Specialization",
}

# ── Layer ordering (higher index = higher abstraction) ───────────────────────
# Used to validate cross-layer direction (lower layers realize/serve upper).
LAYER_ORDER: dict[str, int] = {
    "Physical": 0,
    "Technology": 1,
    "Application": 2,
    "Business": 3,
    "Strategy": 4,
    "Motivation": 5,
    "Implementation": 6,
    "Composite": 7,
}

# ── Relationship rules ────────────────────────────────────────────────────────
# Each entry: (source_aspects, target_aspects, cross_layer_allowed, notes)
# Aspects: ActiveStructure | Behavior | PassiveStructure | Motivation | Composite | Junction | ANY
# "ANY" means no aspect restriction.

ANY = "__ANY__"

RELATIONSHIP_RULES: dict[str, dict] = {
    "Composition": {
        "allowed_pairs": [
            (ANY, ANY),  # Composition is structurally permissive; layer constraint applies
        ],
        "same_layer_preferred": True,
        "cross_layer": True,
        "notes": "Container must be of same or higher layer than contained element.",
    },
    "Aggregation": {
        "allowed_pairs": [(ANY, ANY)],
        "same_layer_preferred": True,
        "cross_layer": True,
        "notes": "Weaker form of Composition.",
    },
    "Assignment": {
        "allowed_pairs": [
            ("ActiveStructure", "Behavior"),
            ("ActiveStructure", "ActiveStructure"),  # role → actor
            ("ActiveStructure", "PassiveStructure"),  # deployment: Node→Artifact, Equipment/Facility→Material
        ],
        "same_layer_preferred": True,
        "cross_layer": False,
        "notes": "Active Structure assigned to Behavior, another Active Structure, or Passive Structure (deployment).",
    },
    "Realization": {
        "allowed_pairs": [
            ("Behavior", "Behavior"),
            ("PassiveStructure", "PassiveStructure"),
            ("PassiveStructure", "ActiveStructure"),  # Artifact → ApplicationComponent/SystemSoftware
            ("Behavior", "Motivation"),       # WorkPackage → Goal/Requirement
            ("PassiveStructure", "Motivation"),
            ("Composite", "Composite"),        # Plateau → Plateau
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Lower-layer element realizes higher-layer counterpart. Includes Artifact realizing ApplicationComponent.",
    },
    "Serving": {
        "allowed_pairs": [
            ("Behavior", "Behavior"),
            ("Behavior", "ActiveStructure"),
            ("ActiveStructure", "ActiveStructure"),
            ("ActiveStructure", "Behavior"),  # spec B.5: interface/actor serving a process (derived but allowed)
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Service provision, typically from lower/same layer to higher/same layer.",
    },
    "Access": {
        "allowed_pairs": [
            ("Behavior", "PassiveStructure"),
            ("ActiveStructure", "PassiveStructure"),  # spec §5.2.2: "active structure element or a behavior element"
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Behavior or Active Structure element observes or acts upon a Passive Structure element.",
    },
    "Influence": {
        "allowed_pairs": [
            ("Motivation", "Motivation"),
            ("ActiveStructure", "Motivation"),
            ("Behavior", "Motivation"),
            ("PassiveStructure", "Motivation"),
            # NOTE: Motivation→Core Influence is NOT allowed per spec B.4 restriction (line 245)
            # and confirmed by B.5 tables (image 377): Motivation source → Core/Strategy rows show ONLY 'O' (Association).
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Core/Strategy elements influence Motivation targets, or Motivation→Motivation. Motivation cannot influence Core elements.",
    },
    "Association": {
        "allowed_pairs": [(ANY, ANY)],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Generic, undirected or directed, between any elements.",
    },
    "Triggering": {
        "allowed_pairs": [
            ("Behavior", "Behavior"),
            ("Junction", "Behavior"),
            ("Behavior", "Junction"),
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Causal ordering between Behavior elements.",
    },
    "Flow": {
        "allowed_pairs": [
            ("Behavior", "Behavior"),
            ("PassiveStructure", "Behavior"),
            ("Behavior", "PassiveStructure"),
            ("PassiveStructure", "PassiveStructure"),
            ("Junction", "Behavior"),
            ("Behavior", "Junction"),
        ],
        "same_layer_preferred": False,
        "cross_layer": True,
        "notes": "Transfer of information or material between elements.",
    },
    "Specialization": {
        "allowed_pairs": [(ANY, ANY)],
        "same_layer_preferred": True,
        "cross_layer": False,
        "notes": "Child specializes parent. Source and target should be same element type.",
    },
}

# ── Viewpoint definitions ─────────────────────────────────────────────────────
# element_types and relationship_types are allow-lists.
# Empty list means "all allowed".

VIEWPOINTS: dict[str, dict] = {
    "Organization": {
        "element_types": [
            "BusinessActor", "BusinessRole", "BusinessCollaboration",
            "BusinessInterface", "Location",
        ],
        "relationship_types": ["Composition", "Aggregation", "Assignment", "Association", "Specialization"],
        "description": "Internal structure of an organization.",
    },
    "BusinessProcessCooperation": {
        "element_types": [
            "BusinessActor", "BusinessRole", "BusinessCollaboration",
            "BusinessProcess", "BusinessFunction", "BusinessInteraction",
            "BusinessEvent", "BusinessService", "BusinessObject",
            "Representation", "Location",
        ],
        "relationship_types": [],
        "description": "Cooperation between business processes.",
    },
    "BusinessProcess": {
        "element_types": [
            "BusinessActor", "BusinessRole", "BusinessCollaboration",
            "BusinessProcess", "BusinessFunction", "BusinessInteraction",
            "BusinessEvent", "BusinessService", "BusinessObject",
            "Representation",
        ],
        "relationship_types": [],
        "description": "Single business process and its context.",
    },
    "ApplicationUsage": {
        "element_types": [
            "BusinessProcess", "BusinessFunction", "BusinessInteraction",
            "BusinessEvent", "BusinessService",
            "ApplicationComponent", "ApplicationCollaboration",
            "ApplicationInterface", "ApplicationProcess",
            "ApplicationFunction", "ApplicationInteraction",
            "ApplicationEvent", "ApplicationService", "DataObject",
        ],
        "relationship_types": [],
        "description": "How application services support business processes.",
    },
    "ApplicationCooperation": {
        "element_types": [
            "ApplicationComponent", "ApplicationCollaboration",
            "ApplicationInterface", "ApplicationProcess",
            "ApplicationFunction", "ApplicationInteraction",
            "ApplicationEvent", "ApplicationService", "DataObject",
        ],
        "relationship_types": [],
        "description": "Relationships between application components.",
    },
    "ApplicationStructure": {
        "element_types": [
            "ApplicationComponent", "ApplicationCollaboration",
            "ApplicationInterface", "DataObject",
        ],
        "relationship_types": ["Composition", "Aggregation", "Assignment", "Association", "Realization", "Serving"],
        "description": "Internal structure of applications.",
    },
    "TechnologyUsage": {
        "element_types": [
            "ApplicationComponent", "ApplicationCollaboration",
            "ApplicationFunction", "ApplicationService", "DataObject",
            "Node", "Device", "SystemSoftware", "TechnologyCollaboration",
            "TechnologyInterface", "TechnologyService", "Artifact",
            "CommunicationNetwork", "Path",
        ],
        "relationship_types": [],
        "description": "How technology supports applications.",
    },
    "Technology": {
        "element_types": [
            "Node", "Device", "SystemSoftware", "TechnologyCollaboration",
            "TechnologyInterface", "TechnologyProcess", "TechnologyFunction",
            "TechnologyInteraction", "TechnologyEvent", "TechnologyService",
            "Artifact", "CommunicationNetwork", "Path",
        ],
        "relationship_types": [],
        "description": "Technology infrastructure.",
    },
    "Physical": {
        "element_types": [
            "Equipment", "Facility", "DistributionNetwork", "Material",
            "Node", "Device", "SystemSoftware", "Artifact",
        ],
        "relationship_types": [],
        "description": "Physical environment and infrastructure.",
    },
    "Stakeholder": {
        "element_types": [
            "Stakeholder", "Driver", "Assessment", "Goal",
            "Outcome", "Principle", "Value",
        ],
        "relationship_types": ["Association", "Influence", "Specialization"],
        "description": "Stakeholder concerns and motivation.",
    },
    "GoalRealization": {
        "element_types": [
            "Goal", "Outcome", "Principle", "Requirement",
            "Constraint", "Driver", "Assessment",
        ],
        "relationship_types": ["Realization", "Influence", "Association", "Specialization"],
        "description": "How goals are realized by requirements and principles.",
    },
    "RequirementRealization": {
        "element_types": [
            "BusinessActor", "BusinessRole", "BusinessProcess",
            "BusinessFunction", "ApplicationComponent",
            "Requirement", "Constraint", "Goal",
        ],
        "relationship_types": ["Realization", "Assignment", "Association"],
        "description": "How core elements realize requirements.",
    },
    "Motivation": {
        "element_types": [
            "Stakeholder", "Driver", "Assessment", "Goal", "Outcome",
            "Principle", "Requirement", "Constraint", "Meaning", "Value",
        ],
        "relationship_types": [],
        "description": "Full motivation aspect.",
    },
    "Strategy": {
        "element_types": [
            "Resource", "Capability", "CourseOfAction", "ValueStream",
        ],
        "relationship_types": [],
        "description": "Strategic concerns.",
    },
    "CapabilityMap": {
        "element_types": ["Capability"],
        "relationship_types": ["Composition", "Aggregation", "Association", "Realization"],
        "description": "Capability hierarchy.",
    },
    "ValueStream": {
        "element_types": [
            "ValueStream", "Capability", "BusinessProcess",
            "BusinessFunction",
        ],
        "relationship_types": ["Composition", "Aggregation", "Association", "Triggering", "Flow"],
        "description": "Value stream across capabilities.",
    },
    "Project": {
        "element_types": [
            "WorkPackage", "Deliverable", "ImplementationEvent",
            "BusinessProcess", "ApplicationComponent",
            "Goal", "Requirement",
        ],
        "relationship_types": [],
        "description": "Projects and work packages.",
    },
    "Migration": {
        "element_types": [
            "Plateau", "Gap", "WorkPackage", "Deliverable",
        ],
        "relationship_types": [],
        "description": "Migration between architectural states.",
    },
    "ImplementationMigration": {
        "element_types": [],  # all allowed
        "relationship_types": [],
        "description": "Combined implementation and migration view.",
    },
    "Full": {
        "element_types": [],
        "relationship_types": [],
        "description": "No viewpoint constraints applied.",
    },
}

# ── Abstraction compaction rules ──────────────────────────────────────────────
# Defines which element types can be collapsed/hidden in abstraction-compact mode.
# Lower priority = collapsed first.
ABSTRACTION_PRIORITY: dict[str, int] = {
    # Always keep high-level strategy/business
    "Capability": 10,
    "ValueStream": 10,
    "BusinessProcess": 9,
    "BusinessFunction": 9,
    "BusinessService": 9,
    "BusinessActor": 8,
    "BusinessRole": 8,
    # Application layer — collapse under serving relationships
    "ApplicationComponent": 6,
    "ApplicationService": 7,
    "ApplicationFunction": 5,
    "ApplicationProcess": 5,
    # Technology — collapse further
    "Node": 4,
    "Device": 3,
    "SystemSoftware": 3,
    "TechnologyService": 4,
    # Physical — lowest, collapse first
    "Equipment": 2,
    "Facility": 2,
    "Material": 1,
}
