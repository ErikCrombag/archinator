from __future__ import annotations
import json
from .models import ArchiMateModel, Element, Relationship, View


def _parse_diagram_input(diagram: str, fmt: str) -> ArchiMateModel:
    """Parse a diagram string (any supported format) back into an ArchiMateModel.

    For exchange_xml and json, we do a full parse.
    For mermaid and plantuml, we extract what we can (best-effort).
    Primarily used by validate_diagram tool.
    """
    if fmt == "json":
        return _parse_json(diagram)
    if fmt == "exchange_xml":
        return _parse_exchange_xml(diagram)
    raise ValueError(f"Parsing of format '{fmt}' not yet supported for validation input. Use 'json' or 'exchange_xml'.")


def _parse_json(text: str) -> ArchiMateModel:
    data = json.loads(text)
    elements = [
        Element(
            id=e["id"], type=e["type"], name=e["name"],
            layer=e["layer"], aspect=e["aspect"],
            description=e.get("description"),
            properties=e.get("properties", {}),
        )
        for e in data.get("elements", [])
    ]
    relationships = [
        Relationship(
            id=r["id"], type=r["type"],
            source_id=r["source_id"], target_id=r["target_id"],
            name=r.get("name"),
            properties=r.get("properties", {}),
        )
        for r in data.get("relationships", [])
    ]
    views = [
        View(
            id=v["id"], name=v["name"], viewpoint=v.get("viewpoint"),
            element_ids=v.get("element_ids", []),
            relationship_ids=v.get("relationship_ids", []),
        )
        for v in data.get("views", [])
    ]
    return ArchiMateModel(
        id=data.get("id", "imported"),
        name=data.get("name", "Imported Model"),
        elements=elements, relationships=relationships, views=views,
        metadata=data.get("metadata", {}),
    )


def _parse_exchange_xml(text: str) -> ArchiMateModel:
    from lxml import etree  # type: ignore
    root = etree.fromstring(text.encode())
    ns = {"a": "http://www.opengroup.org/xsd/archimate/3.0/"}
    xsi = "http://www.w3.org/2001/XMLSchema-instance"

    model_id = (root.get("identifier") or "imported").replace("id-", "")
    name_el = root.find("a:name", ns)
    model_name = name_el.text if name_el is not None else "Imported"

    elements: list[Element] = []
    from .validation.rules import ELEMENT_TYPES
    for el in root.findall(".//a:element", ns):
        eid = (el.get("identifier") or "").replace("id-", "")
        etype = el.get(f"{{{xsi}}}type", "")
        name_node = el.find("a:name", ns)
        ename = name_node.text if name_node is not None else eid
        spec = ELEMENT_TYPES.get(etype, {})
        elements.append(Element(
            id=eid, type=etype, name=ename,
            layer=spec.get("layer", "Unknown"),
            aspect=spec.get("aspect", "Unknown"),
        ))

    relationships: list[Relationship] = []
    for rel in root.findall(".//a:relationship", ns):
        rid = (rel.get("identifier") or "").replace("id-", "")
        rtype = rel.get(f"{{{xsi}}}type", "")
        src = (rel.get("source") or "").replace("id-", "")
        tgt = (rel.get("target") or "").replace("id-", "")
        name_node = rel.find("a:name", ns)
        rname = name_node.text if name_node is not None else None
        relationships.append(Relationship(
            id=rid, type=rtype, source_id=src, target_id=tgt, name=rname,
        ))

    return ArchiMateModel(
        id=model_id, name=model_name,
        elements=elements, relationships=relationships,
    )
