from __future__ import annotations
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data"
_CORE_PATH = _DATA_DIR / "semantic_core.md"

_FALLBACK = """\
# ArchiMate 3.2 Semantic Core Reference (built-in fallback)

## NOTICE
semantic_core.md not found. Run scripts/bootstrap.py to generate it.
Using minimal built-in rules until then.

## Element Catalogue (summary)
Strategy: Resource, Capability, CourseOfAction, ValueStream
Business: BusinessActor, BusinessRole, BusinessCollaboration, BusinessInterface,
  BusinessProcess, BusinessFunction, BusinessInteraction, BusinessEvent,
  BusinessService, BusinessObject, Representation, Contract, Product
Application: ApplicationComponent, ApplicationCollaboration, ApplicationInterface,
  ApplicationProcess, ApplicationFunction, ApplicationInteraction, ApplicationEvent,
  ApplicationService, DataObject
Technology: Node, Device, SystemSoftware, TechnologyCollaboration,
  TechnologyInterface, CommunicationNetwork, Path, TechnologyProcess,
  TechnologyFunction, TechnologyInteraction, TechnologyEvent, TechnologyService, Artifact
Physical: Equipment, Facility, DistributionNetwork, Material
Motivation: Stakeholder, Driver, Assessment, Goal, Outcome, Principle,
  Requirement, Constraint, Meaning, Value
Implementation: WorkPackage, Deliverable, ImplementationEvent, Plateau, Gap
Composite: Grouping, Location, AndJunction, OrJunction

## Relationship Types
Structural: Composition, Aggregation, Assignment, Realization
Dependency: Serving, Access, Influence, Association
Dynamic: Triggering, Flow
Other: Specialization
"""


@lru_cache(maxsize=1)
def load_semantic_core() -> str:
    if _CORE_PATH.exists():
        return _CORE_PATH.read_text(encoding="utf-8")
    return _FALLBACK


def semantic_core_available() -> bool:
    return _CORE_PATH.exists()
