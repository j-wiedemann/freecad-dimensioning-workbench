# SPDX-License-Identifier: LGPL-2.1-or-later

"""Example FreeCAD Workbench."""

import FreeCAD as App
import FreeCADGui as Gui

translate = App.Qt.translate

from .resources import Resources
from .commands import ExampleCommand
from .commands import DimensionCommand
from .commands import AnnotationCommand

class DimensioningWorkbench(Gui.Workbench):

    MenuText: str = translate(
            "dimensioning",
            "Dimensioning",
        )

    ToolTip: str = translate(
            "dimensioning",
            "Add dimensions to model",
        )

    Icon: str = Resources.icon("dimensioning-wb.svg")


    def Initialize(self) -> None:
        App.Console.PrintMessage("Dimensioning Workbench initialized\n")
        # Adding menus and toolbars when the Workbench is active (example)
        commands = [
            # ExampleCommand.Name,
            DimensionCommand.Name,
            AnnotationCommand.Name]
        self.appendToolbar("Dimensioning", commands)
        self.appendMenu("Dimensioning", commands)

        import DraftTools
        from draftutils import init_tools
        self.snapbar = init_tools.get_draft_snap_commands()

    def Activated(self) -> None:
        App.Console.PrintMessage("Dimensioning Workbench activated\n")

    def Deactivated(self) -> None:
        App.Console.PrintMessage("Dimensioning Workbench deactivated\n")

    def ContextMenu(self, recipient: str) -> None:
        App.Console.PrintMessage("Dimensioning Workbench context menu\n")
        # Adding context menus when the Workbench is active (example)
        commands = [
            # ExampleCommand.Name,
            DimensionCommand.Name,
            AnnotationCommand.Name]
        self.appendContextMenu("", commands)

    @classmethod
    def Install(cls) -> None:
        Gui.addWorkbench(cls)
