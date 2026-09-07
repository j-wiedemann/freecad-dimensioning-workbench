# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Basic FeaturePythonObject example.

see: https://wiki.freecad.org/Scripted_objects
see: https://wiki.freecad.org/App_FeaturePython
"""

from __future__ import annotations
from ..resources import Resources

import FreeCAD as App
import Part


class AnnotationFPO:
    """Dimension feature python object"""
    def __init__(self, fpo: App.DocumentObject) -> None:
        AnnotationFPO.setProperties(self, fpo)
        fpo.Proxy = self

    def setProperties(self, fpo: App.DocumentObject) -> None:
        pl = fpo.PropertiesList
        if "String" not in pl:
            fpo.addProperty("App::PropertyString", "String", "Dimension", "Text to generate.").String = "Annotation"
        if "TextSize" not in pl:
            fpo.addProperty("App::PropertyLength", "TextSize", "Dimension", "Size of the text.").TextSize = 10.0
        if "Tracking" not in pl:
            fpo.addProperty("App::PropertyFloat", "Tracking", "Dimension", "Space between characters.").Tracking = 0.25
    
    def onChanged(self, fpo: App.DocumentObject, prop: str) -> None:
        '''Do something when a property has changed'''
        # App.Console.PrintMessage("DimensionsFPO:    Change property: " + str(prop) + "\n")
        return

    def execute(self, fpo: App.DocumentObject) -> None:
        '''Do something when doing a recomputation, this method is mandatory'''
        App.Console.PrintMessage("AnnotationFPO:    recompute called for {}\n".format(fpo.Name))
        text = fpo.String
        wire_string_text = Part.makeWireString(
            text,
            Resources.font(''),
            "/ReliefSingleLineCAD-Regular.ttf",
            fpo.TextSize,
            fpo.Tracking,
            )
        pile = wire_string_text[::-1]
        text_wires = []
        while pile:
            element = pile.pop()
            if isinstance(element, list):
                pile.extend(element[::-1])
            else:
                text_wires.append(element)
        fpo.Shape = Part.makeCompound([s.removeShape(s.Edges[-1]) for s in text_wires])

    @classmethod
    def create(cls, name: str | None = None, doc: App.Document | None = None) -> AnnotationFPO:
        """Optional utility method to create instances of this feature"""

        # Check valid document
        if not (doc := doc or App.ActiveDocument):
            raise ValueError("A FreeCAD document is required")

        # Create the c++ DocumentObject
        # see: https://wiki.freecad.org/App_FeaturePython
        obj = doc.addObject("Part::FeaturePython", name or "Dimension_000")

        # Bind the Python Proxy
        proxy = cls(obj)

        # Manage Gui (ViewProvider) if available
        if App.GuiUp and hasattr(obj, "ViewObject"):
            from .annotation_vp import AnnotationViewProvider
            AnnotationViewProvider(obj.ViewObject)

        obj.recompute()
        return obj
