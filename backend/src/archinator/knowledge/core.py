from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path

# DATA_DIR env var overrides the default (needed in Docker where the install
# path differs from the repo layout).  Locally falls back to <repo_root>/data.
_DATA_DIR = Path(
    os.environ.get(
        "DATA_DIR",
        str(Path(__file__).parent.parent.parent.parent.parent / "data"),
    )
)

# rules_core.md — always present (baked into image at build time from rules.py)
_RULES_PATH = _DATA_DIR / "rules_core.md"

# semantic_core.md — optional, written by scripts/bootstrap.py after PDF + web
#                     extraction.  Mounted via docker volume at runtime.
_BOOTSTRAP_PATH = _DATA_DIR / "semantic_core.md"

_RULES_FALLBACK = """\
# ArchiMate 3.2 Rules Reference (built-in fallback)

rules_core.md not found — run scripts/render_rules_md.py to generate it.

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
    """Return combined rules + (optional) bootstrap content for the LLM prompt."""
    parts: list[str] = []

    # 1. rules_core.md — always expected
    if _RULES_PATH.exists():
        parts.append(_RULES_PATH.read_text(encoding="utf-8"))
    else:
        parts.append(_RULES_FALLBACK)

    # 2. semantic_core.md — only if bootstrap has been run
    if _BOOTSTRAP_PATH.exists():
        parts.append(
            "\n---\n\n# Extended Reference (from bootstrap)\n\n"
            + _BOOTSTRAP_PATH.read_text(encoding="utf-8")
        )

    return "\n\n".join(parts)


def semantic_core_available() -> bool:
    """True when the full bootstrap content is present (not just rules_core)."""
    return _BOOTSTRAP_PATH.exists()
