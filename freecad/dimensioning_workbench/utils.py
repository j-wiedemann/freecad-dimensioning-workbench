# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Utils for dimensioning workbench
"""

import FreeCAD as App
import Part
import DraftGeomUtils


def resolve_sub_shape(obj, sub_name: str):
    """Resolve a (object, subelement) reference to a Part shape in global coordinates.

    Mirrors the resolution done in DimensionFPO.get_references_data so
    previsualization and computation agree: when a referenced object lives
    inside a container with a placement (e.g. App::Part, or PartDesign
    Body), the ancestor placement chain is applied so the shape stands at
    its actual position in the document.

    Returns None when the reference cannot be resolved (missing, invalid or
    deleted object), callers must skip.
    """
    if obj is None:
        return None
    try:
        if "PartDesign" in obj.TypeId:
            if obj.TypeId == "PartDesign::Body":
                body = obj
            else:
                body = obj.getParent()
            body_to_global = None
            if hasattr(body, "getGlobalPlacement") and body.getGlobalPlacement() != body.Placement:
                body_to_global = body.getGlobalPlacement().Matrix
            if body_to_global is not None:
                shape = Part.getShape(
                    body,
                    obj.Name + "." + sub_name,
                    needSubElement=True,
                    mat=body_to_global,
                    transform=False,
                )
            else:
                shape = Part.getShape(body, obj.Name + "." + sub_name, needSubElement=True)
        else:
            obj_to_global = None
            if hasattr(obj, "getGlobalPlacement") and obj.getGlobalPlacement() != obj.Placement:
                obj_to_global = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).Matrix
            if obj_to_global is not None:
                shape = obj.getSubObject(sub_name, matrix=obj_to_global)
            else:
                shape = obj.getSubObject(sub_name)
    except Exception:
        App.Console.PrintWarning(
            "Utils:    cannot resolve reference {} : {}\n".format(
                getattr(obj, "Name", "?"),
                sub_name,
            )
        )
        return None
    return shape


def get_main_direction(obj:App.Vector|Part.Edge) -> str:
    if isinstance(obj, Part.Edge):
        vec = DraftGeomUtils.vec(obj)
    else:
        vec = obj
    main_dir = None
    vec.normalize()
    abs_vec = (abs(vec.x), abs(vec.y), abs(vec.z))
    idx = abs_vec.index(max(abs(vec.x), abs(vec.y), abs(vec.z)))
    if idx == 0:
        main_dir = "X"
    elif idx == 1:
        main_dir = "Y"
    elif idx == 2:
        main_dir = "Z"
    if main_dir:
        return main_dir
    else:
        App.Console.PrintWarning("Utils:    get_main_direction return an arbitrary X direction.\n")
        return "X"