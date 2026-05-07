from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CompactionMode(str, Enum):
    FULL = "full"
    VIEWPOINT = "viewpoint"
    ABSTRACTION = "abstraction"


class OutputFormat(str, Enum):
    EXCHANGE_XML = "exchange_xml"
    JSON = "json"
    MERMAID = "mermaid"
    PLANTUML = "plantuml"


@dataclass
class Element:
    id: str
    type: str
    name: str
    layer: str
    aspect: str
    description: str | None = None
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class Relationship:
    id: str
    type: str
    source_id: str
    target_id: str
    name: str | None = None
    access_type: str | None = None  # Read, Write, ReadWrite, Execute — for Access relationships
    influence_modifier: str | None = None  # +/- modifier for Influence
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class View:
    id: str
    name: str
    viewpoint: str | None
    element_ids: list[str] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)


@dataclass
class ArchiMateModel:
    id: str
    name: str
    elements: list[Element] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    views: list[View] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def element_by_id(self, eid: str) -> Element | None:
        return next((e for e in self.elements if e.id == eid), None)

    def elements_by_type(self, etype: str) -> list[Element]:
        return [e for e in self.elements if e.type == etype]

    def relationships_for_element(self, eid: str) -> list[Relationship]:
        return [r for r in self.relationships if r.source_id == eid or r.target_id == eid]


@dataclass
class ValidationViolation:
    rule: str
    message: str
    element_id: str | None = None
    relationship_id: str | None = None
    severity: str = "error"  # error | warning


@dataclass
class ValidationResult:
    valid: bool
    violations: list[ValidationViolation] = field(default_factory=list)

    def errors(self) -> list[ValidationViolation]:
        return [v for v in self.violations if v.severity == "error"]

    def warnings(self) -> list[ValidationViolation]:
        return [v for v in self.violations if v.severity == "warning"]


@dataclass
class GenerationResult:
    model: ArchiMateModel
    validation: ValidationResult
    outputs: dict[str, str] = field(default_factory=dict)  # format -> rendered string
    compaction_mode: CompactionMode = CompactionMode.FULL
    compact_validation: ValidationResult | None = None
    rag_chunks_used: list[str] = field(default_factory=list)
