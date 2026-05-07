"""
Render ArchiMateModel to Open Group ArchiMate Exchange Format XML.
Spec: https://www.opengroup.org/xsd/archimate/
"""
from __future__ import annotations
from lxml import etree  # type: ignore
from ..models import ArchiMateModel

_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"
_SCHEMA_LOC = (
    "http://www.opengroup.org/xsd/archimate/3.0/ "
    "http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"
)


def render(model: ArchiMateModel) -> str:
    nsmap = {None: _NS, "xsi": _XSI}
    root = etree.Element(f"{{{_NS}}}model", nsmap=nsmap)
    root.set(f"{{{_XSI}}}schemaLocation", _SCHEMA_LOC)
    root.set("identifier", f"id-{model.id}")

    name_el = etree.SubElement(root, f"{{{_NS}}}name")
    name_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
    name_el.text = model.name

    # Elements
    elements_el = etree.SubElement(root, f"{{{_NS}}}elements")
    for e in model.elements:
        el = etree.SubElement(elements_el, f"{{{_NS}}}element")
        el.set("identifier", f"id-{e.id}")
        el.set(f"{{{_XSI}}}type", e.type)
        n = etree.SubElement(el, f"{{{_NS}}}name")
        n.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        n.text = e.name
        if e.description:
            d = etree.SubElement(el, f"{{{_NS}}}documentation")
            d.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            d.text = e.description

    # Relationships
    rels_el = etree.SubElement(root, f"{{{_NS}}}relationships")
    for r in model.relationships:
        rel = etree.SubElement(rels_el, f"{{{_NS}}}relationship")
        rel.set("identifier", f"id-{r.id}")
        rel.set(f"{{{_XSI}}}type", r.type)
        rel.set("source", f"id-{r.source_id}")
        rel.set("target", f"id-{r.target_id}")
        if r.name:
            n = etree.SubElement(rel, f"{{{_NS}}}name")
            n.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            n.text = r.name
        if r.access_type:
            rel.set("accessType", r.access_type)

    # Views
    if model.views:
        views_el = etree.SubElement(root, f"{{{_NS}}}views")
        diagrams_el = etree.SubElement(views_el, f"{{{_NS}}}diagrams")
        for v in model.views:
            view_el = etree.SubElement(diagrams_el, f"{{{_NS}}}view")
            view_el.set("identifier", f"id-{v.id}")
            if v.viewpoint:
                view_el.set("viewpoint", v.viewpoint)
            vn = etree.SubElement(view_el, f"{{{_NS}}}name")
            vn.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            vn.text = v.name
            for eid in v.element_ids:
                node = etree.SubElement(view_el, f"{{{_NS}}}node")
                node.set("elementRef", f"id-{eid}")
                node.set("identifier", f"id-node-{eid}")
            for rid in v.relationship_ids:
                conn = etree.SubElement(view_el, f"{{{_NS}}}connection")
                conn.set("relationshipRef", f"id-{rid}")
                conn.set("identifier", f"id-conn-{rid}")

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()
