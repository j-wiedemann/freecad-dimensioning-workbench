# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Basic ViewProvider example.

see: https://wiki.freecad.org/Scripted_objects
"""

from __future__ import annotations
from ..resources import Resources
# from ..guis import annotation_gui

import FreeCADGui as Gui


class AnnotationViewProvider:
    def __init__(self, obj: Gui.ViewProviderDocumentObject) -> None:
        """
        Set this object to the proxy object of the actual view provider
        """

        self.Object = obj.Object
        # self._set_properties(vpfpo)
        obj.Proxy = self

    def doubleClicked(self, vobj):
        """
        Open Dimension task panel on double click
        """
        # task = Gui.Control.activeTaskDialog()
        # if task:
        #     task.reject()
        # task = annotation_gui.DimensionTaskPanel(vobj.Object)
        # dialog = Gui.Control.showDialog(task)
        # if dialog is not None:
        #     dialog.setAutoCloseOnTransactionChange(True)
        #     dialog.setDocumentName(Gui.ActiveDocument.Document.Name)
        return True

    def attach(self, vpfpo) -> None:
        """
        Setup the scene sub-graph of the view provider, this method is mandatory
        """
        self.Object = vpfpo.Object
        return

    def updateData(self, fp, prop) -> None:
        """
        If a property of the handled feature has changed we have the chance to handle this here
        """
        return

    def getDisplayModes(self, fpo) -> list:
        """
        Return a list of display modes.
        """
        return []

    def getDefaultDisplayMode(self) -> str:
        """
        Return the name of the default display mode. It must be defined in getDisplayModes.
        """
        return "Flat Lines"

    def setDisplayMode(self, mode) -> str:
        """
        Map the display mode defined in attach with those defined in getDisplayModes.
        Since they have the same names nothing needs to be done.
        This method is optional.
        """
        return mode

    def onChanged(self, vp, prop) -> None:
        """
        Print the name of the property that has changed
        """
        # App.Console.PrintMessage("Change property: " + str(prop) + "\n")
        return

    def getIcon(self) -> str:
        """
        Return the icon in XMP format which will appear in the tree view. This method is optional and if not defined a default icon is shown.
        """
        return Resources.icon("Draft_Text.svg")

    def dumps(self):
        """
        Called during document saving.
        """
        return None

    def loads(self,state):
        """
        Called during document restore.
        """
        return None

