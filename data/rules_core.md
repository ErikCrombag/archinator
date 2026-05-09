# ArchiMate 3.2 Semantic Core Reference

> Auto-generated from `validation/rules.py` — do not edit manually.
> Reflects the ArchiMate 3.2 specification (The Open Group).

## Key Rules

- **Assignment** direction: ActiveStructure → Behavior, ActiveStructure → ActiveStructure, ActiveStructure → PassiveStructure (deployment). Never Behavior → PassiveStructure.
- **Access** source: Behavior or ActiveStructure. Target: always PassiveStructure.
- **Influence** target: always a Motivation element. Core/Strategy elements *influence* Motivation; Motivation does NOT influence Core.
- **Realization** direction: lower/more-concrete element → higher/more-abstract. Includes Artifact → ApplicationComponent.
- **Serving** direction: Behavior or ActiveStructure → Behavior or ActiveStructure.
- **Triggering / Flow**: Behavior elements (and Junctions). Flow also allows PassiveStructure endpoints.
- **Cross-layer**: Assignment and Specialization are same-layer only.
- Layer stack (low→high): Physical → Technology → Application → Business → Strategy. Motivation and Implementation are orthogonal.

## Element Types

63 element types across 8 layers.

### Physical Layer

| Element | Aspect |
|---|---|
| DistributionNetwork | ActiveStructure |
| Equipment | ActiveStructure |
| Facility | ActiveStructure |
| Material | PassiveStructure |

### Technology Layer

| Element | Aspect |
|---|---|
| Artifact | PassiveStructure |
| CommunicationNetwork | ActiveStructure |
| Device | ActiveStructure |
| Node | ActiveStructure |
| Path | ActiveStructure |
| SystemSoftware | ActiveStructure |
| TechnologyCollaboration | ActiveStructure |
| TechnologyEvent | Behavior |
| TechnologyFunction | Behavior |
| TechnologyInteraction | Behavior |
| TechnologyInterface | ActiveStructure |
| TechnologyProcess | Behavior |
| TechnologyService | Behavior |

### Application Layer

| Element | Aspect |
|---|---|
| ApplicationCollaboration | ActiveStructure |
| ApplicationComponent | ActiveStructure |
| ApplicationEvent | Behavior |
| ApplicationFunction | Behavior |
| ApplicationInteraction | Behavior |
| ApplicationInterface | ActiveStructure |
| ApplicationProcess | Behavior |
| ApplicationService | Behavior |
| DataObject | PassiveStructure |

### Business Layer

| Element | Aspect |
|---|---|
| BusinessActor | ActiveStructure |
| BusinessCollaboration | ActiveStructure |
| BusinessEvent | Behavior |
| BusinessFunction | Behavior |
| BusinessInteraction | Behavior |
| BusinessInterface | ActiveStructure |
| BusinessObject | PassiveStructure |
| BusinessProcess | Behavior |
| BusinessRole | ActiveStructure |
| BusinessService | Behavior |
| Contract | PassiveStructure |
| Product | PassiveStructure |
| Representation | PassiveStructure |

### Strategy Layer

| Element | Aspect |
|---|---|
| Capability | Behavior |
| CourseOfAction | Behavior |
| Resource | ActiveStructure |
| ValueStream | Behavior |

### Motivation Layer

| Element | Aspect |
|---|---|
| Assessment | Motivation |
| Constraint | Motivation |
| Driver | Motivation |
| Goal | Motivation |
| Meaning | Motivation |
| Outcome | Motivation |
| Principle | Motivation |
| Requirement | Motivation |
| Stakeholder | ActiveStructure |
| Value | Motivation |

### Implementation Layer

| Element | Aspect |
|---|---|
| Deliverable | PassiveStructure |
| Gap | Composite |
| ImplementationEvent | Behavior |
| Plateau | Composite |
| WorkPackage | Behavior |

### Composite Layer

| Element | Aspect |
|---|---|
| AndJunction | Junction |
| Grouping | Composite |
| Location | Composite |
| OrJunction | Junction |

## Relationship Rules

Source/target aspects that are **directly** allowed per ArchiMate 3.2 §B.5.
`ANY` = no aspect restriction.

| Relationship | Source Aspect | Target Aspect | Cross-layer |
|---|---|---|---|
| Composition | ANY | ANY | yes |
| Aggregation | ANY | ANY | yes |
| Assignment | ActiveStructure | Behavior | no |
| Assignment | ActiveStructure | ActiveStructure | no |
| Assignment | ActiveStructure | PassiveStructure | no |
| Realization | Behavior | Behavior | yes |
| Realization | PassiveStructure | PassiveStructure | yes |
| Realization | PassiveStructure | ActiveStructure | yes |
| Realization | Behavior | Motivation | yes |
| Realization | PassiveStructure | Motivation | yes |
| Realization | Composite | Composite | yes |
| Serving | Behavior | Behavior | yes |
| Serving | Behavior | ActiveStructure | yes |
| Serving | ActiveStructure | ActiveStructure | yes |
| Serving | ActiveStructure | Behavior | yes |
| Access | Behavior | PassiveStructure | yes |
| Access | ActiveStructure | PassiveStructure | yes |
| Influence | Motivation | Motivation | yes |
| Influence | ActiveStructure | Motivation | yes |
| Influence | Behavior | Motivation | yes |
| Influence | PassiveStructure | Motivation | yes |
| Association | ANY | ANY | yes |
| Triggering | Behavior | Behavior | yes |
| Triggering | Junction | Behavior | yes |
| Triggering | Behavior | Junction | yes |
| Flow | Behavior | Behavior | yes |
| Flow | PassiveStructure | Behavior | yes |
| Flow | Behavior | PassiveStructure | yes |
| Flow | PassiveStructure | PassiveStructure | yes |
| Flow | Junction | Behavior | yes |
| Flow | Behavior | Junction | yes |
| Specialization | ANY | ANY | no |

> Association is always valid between any two elements (ANY→ANY).
> Composition, Aggregation, Specialization always valid between same element type.

## Standard Viewpoints

Empty element/relationship list means *all allowed*.

**Organization** — Internal structure of an organization.
- Elements: BusinessActor, BusinessRole, BusinessCollaboration, BusinessInterface, Location
- Relationships: Composition, Aggregation, Assignment, Association, Specialization

**BusinessProcessCooperation** — Cooperation between business processes.
- Elements: BusinessActor, BusinessRole, BusinessCollaboration, BusinessProcess, BusinessFunction, BusinessInteraction, BusinessEvent, BusinessService, BusinessObject, Representation, Location
- Relationships: all

**BusinessProcess** — Single business process and its context.
- Elements: BusinessActor, BusinessRole, BusinessCollaboration, BusinessProcess, BusinessFunction, BusinessInteraction, BusinessEvent, BusinessService, BusinessObject, Representation
- Relationships: all

**ApplicationUsage** — How application services support business processes.
- Elements: BusinessProcess, BusinessFunction, BusinessInteraction, BusinessEvent, BusinessService, ApplicationComponent, ApplicationCollaboration, ApplicationInterface, ApplicationProcess, ApplicationFunction, ApplicationInteraction, ApplicationEvent, ApplicationService, DataObject
- Relationships: all

**ApplicationCooperation** — Relationships between application components.
- Elements: ApplicationComponent, ApplicationCollaboration, ApplicationInterface, ApplicationProcess, ApplicationFunction, ApplicationInteraction, ApplicationEvent, ApplicationService, DataObject
- Relationships: all

**ApplicationStructure** — Internal structure of applications.
- Elements: ApplicationComponent, ApplicationCollaboration, ApplicationInterface, DataObject
- Relationships: Composition, Aggregation, Assignment, Association, Realization, Serving

**TechnologyUsage** — How technology supports applications.
- Elements: ApplicationComponent, ApplicationCollaboration, ApplicationFunction, ApplicationService, DataObject, Node, Device, SystemSoftware, TechnologyCollaboration, TechnologyInterface, TechnologyService, Artifact, CommunicationNetwork, Path
- Relationships: all

**Technology** — Technology infrastructure.
- Elements: Node, Device, SystemSoftware, TechnologyCollaboration, TechnologyInterface, TechnologyProcess, TechnologyFunction, TechnologyInteraction, TechnologyEvent, TechnologyService, Artifact, CommunicationNetwork, Path
- Relationships: all

**Physical** — Physical environment and infrastructure.
- Elements: Equipment, Facility, DistributionNetwork, Material, Node, Device, SystemSoftware, Artifact
- Relationships: all

**Stakeholder** — Stakeholder concerns and motivation.
- Elements: Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Value
- Relationships: Association, Influence, Specialization

**GoalRealization** — How goals are realized by requirements and principles.
- Elements: Goal, Outcome, Principle, Requirement, Constraint, Driver, Assessment
- Relationships: Realization, Influence, Association, Specialization

**RequirementRealization** — How core elements realize requirements.
- Elements: BusinessActor, BusinessRole, BusinessProcess, BusinessFunction, ApplicationComponent, Requirement, Constraint, Goal
- Relationships: Realization, Assignment, Association

**Motivation** — Full motivation aspect.
- Elements: Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Requirement, Constraint, Meaning, Value
- Relationships: all

**Strategy** — Strategic concerns.
- Elements: Resource, Capability, CourseOfAction, ValueStream
- Relationships: all

**CapabilityMap** — Capability hierarchy.
- Elements: Capability
- Relationships: Composition, Aggregation, Association, Realization

**ValueStream** — Value stream across capabilities.
- Elements: ValueStream, Capability, BusinessProcess, BusinessFunction
- Relationships: Composition, Aggregation, Association, Triggering, Flow

**Project** — Projects and work packages.
- Elements: WorkPackage, Deliverable, ImplementationEvent, BusinessProcess, ApplicationComponent, Goal, Requirement
- Relationships: all

**Migration** — Migration between architectural states.
- Elements: Plateau, Gap, WorkPackage, Deliverable
- Relationships: all

**ImplementationMigration** — Combined implementation and migration view.
- Elements: all
- Relationships: all

**Full** — No viewpoint constraints applied.
- Elements: all
- Relationships: all
