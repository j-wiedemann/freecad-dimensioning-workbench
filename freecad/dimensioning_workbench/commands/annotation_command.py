# SPDX-License-Identifier: LGPL-2.1-or-later

"""Example FreeCAD command demonstrating the command structure."""

from typing import ClassVar

import FreeCAD as App
translate = App.Qt.translate

from ..resources import Resources


class AnnotationCommand:
    """Annotation command that add shapestring style annotation."""

    # Good practice (optional): set a constant for your command name, it is used in several places.
    Name: ClassVar[str] = "dimensioning_workbench_AnnotationCommand"

    def __init__(self) -> None:
        # Optional: initialize instance variables that persist for the command's lifetime
        pass

    def GetResources(self) -> dict[str, str]:
        # Returns a dictionary that defines how the command appears in the UI.
        # - Pixmap: path to the icon file (relative to FreeCAD's icon search paths or absolute path)
        # - MenuText: text shown in menus (use translate for translation support)
        # - ToolTip: text shown when hovering over the button/menu item
        # - Accel: optional keyboard shortcut (e.g., "Ctrl+A")
        return {
            "Pixmap": Resources.icon(
                "Draft_Text.svg"
            ),
            "MenuText": translate(
                "dimensioning",
                "Annotation",
            ),
            "ToolTip": translate(
                "dimensioning",
                "Add annotation",
            ),
        }

    def Activated(self) -> None:
        # Called when the user triggers the command (clicks the toolbar button,
        # selects the menu item, or runs FreeCADGui.runCommand()).
        # Place the main logic of your command here.
        App.Console.PrintMessage("Example Command activated\n")

        # Example: Create a custom DocumentObject
        from ..features import AnnotationFPO
        doc = App.ActiveDocument or App.newDocument()
        AnnotationFPO.create("Annotation_000", doc)

    def IsActive(self) -> bool:
        # Called frequently by FreeCAD to determine if the command should be
        # enabled (True) or greyed out/disabled (False).
        # Use this to check for conditions like: active document exists,
        # objects are selected, workbench is in correct state, etc.
        return True

    @classmethod
    def Install(cls) -> None:
        # Optional utility method to register the command
        if App.GuiUp:
            App.Gui.addCommand(cls.Name, cls())
