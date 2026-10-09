# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Basic ViewProvider example.

see: https://wiki.freecad.org/Scripted_objects
"""

from __future__ import annotations
from ..resources import Resources
from .. import utils
from .. import snapper
from .reference_highlight import ReferenceHighlighter

import FreeCAD as App
import FreeCADGui as Gui
from FreeCAD import Base
import DraftVecUtils
import DraftGeomUtils
from PySide import QtCore, QtGui

translate = App.Qt.translate


class DimensionTaskPanel:
    def __init__(self, fpo=None) -> None:
        self.highlighter = None
        if not App.ActiveDocument:
            return

        # draw widget
        self.form = Gui.PySideUic.loadUi(Resources.ui("dimension.ui"))
        
        # modes list
        modes_list = [
            (translate("dimensioning", "X"), "X"),
            (translate("dimensioning", "Y"), "Y"),
            (translate("dimensioning", "Z"), "Z"),
            (translate("dimensioning", "Distance"), "Distance"),
            (translate("dimensioning", "Radius"), "Radius"),
            (translate("dimensioning", "Diameter"), "Diameter"),
            (translate("dimensioning", "Angle"), "Angle"),
            (translate("dimensioning", "ArcLength"), "ArcLength"),
            (translate("dimensioning", "ChainX"), "ChainX"),
            (translate("dimensioning", "ChainY"), "ChainY"),
            (translate("dimensioning", "ChainZ"), "ChainZ"),
        ]
        for mode in modes_list:
            self.form.modes.addItem(mode[0], mode[1])
        
        # projections list
        projections_list = [
            (translate("dimensioning", "X"), "X"),
            (translate("dimensioning", "Y"), "Y"),
            (translate("dimensioning", "Z"), "Z"),
            (translate("dimensioning", "Custom"), "Custom"),
        ]
        for proj in projections_list:
            self.form.projections.addItem(proj[0], proj[1])
        
        # angle field
        self.form.angle.setProperty("unit", "deg")
        self.form.angle.setProperty("minimum", 0)
        self.form.angle.setProperty("maximum", 360)

        # dimension offset
        self.form.offset.setProperty("unit", "mm")
        self.form.offset.setProperty("precision", 0)

        # text dimension offset
        self.form.text_offset.setProperty("unit", "mm")
        self.form.text_offset.setProperty("precision", 0)

        # text dimension offset
        self.form.ext_line_offset.setProperty("unit", "mm")
        self.form.ext_line_offset.setProperty("precision", 0)

        # live picking observer
        self.pick_obs = None
        self.pick_mode = "point"
        
        # variables
        if fpo:
            App.ActiveDocument.openTransaction(translate("dimensioning", "Edit Dimension"))
            self.fpo = fpo
            self.edit_mode = 1
            for sub in fpo.ReferenceShapesList:
                item = QtGui.QListWidgetItem()
                item_data = (sub[0], sub[1][0])
                item.setData(QtCore.Qt.UserRole, item_data)
                if sub[1][0] != '':
                    item_text = '{} : {}'.format(sub[0].Name, sub[1][0])
                else:
                    item_text = '{}'.format(sub[0].Name)
                item.setText(item_text)
                self.form.references.addItem(item)
            for vector in fpo.ReferencePointsList:
                item = QtGui.QListWidgetItem()
                item_data = vector
                item.setData(QtCore.Qt.UserRole, item_data)
                item_text = "Point {}".format(DraftVecUtils.tup(vector))
                item.setText(item_text)
                self.form.references.addItem(item)
            
        else:
            
            self.edit_mode = 0
            # get mode and projection from references
            # mode = getattr(self.fpo, "Mode", "X")

            # mode = self.fpo.Mode
            # projection = self.fpo.Projection
            references = []
            vertexes_count = 0
            linear_edges_count = 0
            arc_edges_count = 0
            circular_edges_count = 0
            circular_faces_count = 0
            selection = Gui.Selection.getCompleteSelection()
            if len(selection)>0:
                for sel in selection:
                    if sel.HasSubObjects:
                        for sub_name in sel.SubElementNames:
                            sub = App.ActiveDocument.getObject(sel.ObjectName).getSubObject(sub_name)
                            references.append(sub)
                            item_text = '{} : {}'.format(sel.ObjectName, sub_name)
                            item_data = (App.ActiveDocument.getObject(sel.ObjectName), sub_name)
                            if sub.ShapeType == "Vertex":
                                vertexes_count += 1
                            elif sub.ShapeType == "Edge":
                                if hasattr(sub.Curve, "Axis"):
                                    if sub.isClosed:
                                        circular_edges_count += 1
                                    else:
                                        arc_edges_count += 1
                                elif hasattr(sub.Curve, "Direction"):
                                    linear_edges_count += 1
                            elif sub.ShapeType == "Face":
                                if len(sub.Edges) == 1:
                                    if hasattr(sub.Edges[0].Curve, "Axis"):
                                        if sub.isClosed:
                                            circular_faces_count += 1
                    else:
                        references.append(App.ActiveDocument.getObject(sel.ObjectName))
                        item_text = '{}'.format(App.ActiveDocument.getObject(sel.ObjectName))
                        item_data = (App.ActiveDocument.getObject(sel.ObjectName),'')
                    # add item in qlistwidget
                    item = QtGui.QListWidgetItem()
                    item.setText(item_text)
                    item.setData(QtCore.Qt.UserRole, item_data)
                    print("Dimension:    add reference {}".format(item_text))
                    self.form.references.addItem(item)
            # get potential best mode
            if linear_edges_count == 1:
                vec = DraftGeomUtils.vec(references[0])
                mode = utils.get_main_direction(vec or App.Vector(1,0,0))
                proj_list = ["X", "Y", "Z"]
                proj_list.remove(mode)
                projection = proj_list[0]
            elif arc_edges_count == 1:
                vec = DraftGeomUtils.vec(references[0].Curve.Axis)
                projection = utils.get_main_direction(vec or App.Vector(1,0,0))
                mode = "Radius"
            elif circular_edges_count == 1:
                vec = DraftGeomUtils.vec(references[0].Curve.Axis)
                projection = utils.get_main_direction(vec or App.Vector(1,0,0))
                mode = "Diameter"
            elif circular_faces_count == 1:
                vec = DraftGeomUtils.vec(references[0].Edges[0].Curve.Axis)
                projection = utils.get_main_direction(vec or App.Vector(1,0,0))
                mode = "Diameter"
            elif linear_edges_count == 2 or vertexes_count == 3:
                mode = "Angle"
                projection = "X"
            else:
                mode = "X"
                projection = "Z"
            App.ActiveDocument.openTransaction(translate("dimensioning", "Create Dimension"))
            from ..features import DimensionFPO
            doc = App.ActiveDocument or App.newDocument()
            self.fpo = DimensionFPO.create("Dimension_000", doc)
            self.fpo.Mode = mode
            self.fpo.Projection = projection
                        
        self.update_widget()
        self.refresh_dimension_fpo()

        # connect signals
        self.form.angle.valueChanged.connect(self.angle_value_changed)
        self.form.text_size.valueChanged.connect(self.text_size_value_changed)
        self.form.arrow_size.valueChanged.connect(self.arrow_size_value_changed)
        self.form.offset.valueChanged.connect(self.offset_value_changed)
        self.form.modes.currentIndexChanged.connect(self.mode_changed)
        self.form.sector.currentIndexChanged.connect(self.sector_changed)
        self.form.projections.currentIndexChanged.connect(self.projection_changed)
        self.form.text_offset.valueChanged.connect(self.text_offset_value_changed)
        self.form.ext_line_offset.valueChanged.connect(self.ext_line_offset_value_changed)
        self.form.decimals.valueChanged.connect(self.decimals_value_changed)
        self.form.prefix.textChanged.connect(self.prefix_text_changed)
        self.form.suffix.textChanged.connect(self.suffix_text_changed)
        self.form.override.textChanged.connect(self.override_text_changed)
        self.form.add_shape.clicked.connect(self.toggle_pick_mode)
        self.form.remove_reference.clicked.connect(self.remove_reference)
        self.form.create_dimension.clicked.connect(self.create_dimension)

        # highlight the reference hovered in the list in the 3D view
        self.highlighter = ReferenceHighlighter(self.form.references)

        # always live point picking while the panel is open
        self.start_point_picking()

    def accept(self):
        App.ActiveDocument.commitTransaction()
        self.stop_picking()
        self.stop_highlight()
        Gui.Control.closeDialog()

    def reject(self):
        App.ActiveDocument.abortTransaction()
        self.stop_picking()
        self.stop_highlight()
        Gui.Control.closeDialog()

    def create_dimension(self):
        App.ActiveDocument.commitTransaction()
        self.stop_picking()
        self.stop_highlight()
        Gui.Control.closeDialog()
        Gui.Selection.clearSelection()
        taskpanel = DimensionTaskPanel()
        QtCore.QTimer.singleShot(0, lambda: Gui.Control.showDialog(taskpanel))

    def stop_highlight(self) -> None:
        """Detach the reference hover highlight if any."""
        if self.highlighter:
            self.highlighter.finalize()
            self.highlighter = None

    def update_widget(self):
        # set mode
        idx = self.form.modes.findData(self.fpo.Mode)
        self.form.modes.setCurrentIndex(idx)

        # set proj
        idx = self.form.projections.findData(self.fpo.Projection)
        self.form.projections.setCurrentIndex(idx)

        # set numerical value
        self.form.offset.setProperty("quantityString", self.fpo.Offset.Value)
        self.form.text_offset.setProperty("quantityString", self.fpo.TextOffset.Value)
        self.form.angle.setProperty("quantityString", self.fpo.Angle.Value)
        self.form.sector.setCurrentIndex(self.fpo.Sector)
        self.form.arrow_size.setProperty("quantityString", self.fpo.ArrowSize.Value)
        self.form.text_size.setProperty("quantityString", self.fpo.TextSize.Value)
        self.form.ext_line_offset.setProperty("quantityString", self.fpo.ExtLineOffset.Value)

        # text composition fields (block signals: update_widget may run with
        # the field handlers already connected)
        self.form.decimals.blockSignals(True)
        self.form.decimals.setValue(getattr(self.fpo, "Decimals", 2))
        self.form.decimals.blockSignals(False)
        self.form.prefix.blockSignals(True)
        self.form.prefix.setText(getattr(self.fpo, "Prefix", "") or "")
        self.form.prefix.blockSignals(False)
        self.form.suffix.blockSignals(True)
        self.form.suffix.setText(getattr(self.fpo, "Suffix", "") or "")
        self.form.suffix.blockSignals(False)
        self.form.override.blockSignals(True)
        self.form.override.setPlainText(getattr(self.fpo, "Override", "") or "")
        self.form.override.blockSignals(False)

    def get_initial_configuration(self):
        pass

    def angle_value_changed(self, input):
        self.fpo.Angle = input.Value
        self.refresh_dimension_fpo()

    def text_size_value_changed(self, input):
        self.fpo.TextSize = input
        self.refresh_dimension_fpo()

    def offset_value_changed(self, input):
        self.fpo.Offset = input.Value
        self.refresh_dimension_fpo()

    def arrow_size_value_changed(self, input):
        self.fpo.ArrowSize = input
        self.refresh_dimension_fpo()

    def ext_line_offset_value_changed(self, input):
        self.fpo.ExtLineOffset = input
        self.refresh_dimension_fpo()

    def mode_changed(self):
        self.fpo.Mode = self.form.modes.currentData()
        self.refresh_dimension_fpo()

    def sector_changed(self):
        self.fpo.Sector = self.form.sector.currentIndex()
        self.refresh_dimension_fpo()

    def projection_changed(self):
        self.fpo.Projection = self.form.projections.currentData()
        self.refresh_dimension_fpo()

    def text_offset_value_changed(self, input):
        self.fpo.TextOffset = input
        self.refresh_dimension_fpo()

    def decimals_value_changed(self, value):
        self.fpo.Decimals = value
        self.refresh_dimension_fpo()

    def prefix_text_changed(self, text):
        self.fpo.Prefix = text
        self.refresh_dimension_fpo()

    def suffix_text_changed(self, text):
        self.fpo.Suffix = text
        self.refresh_dimension_fpo()

    def override_text_changed(self):
        self.fpo.Override = self.form.override.toPlainText()
        self.refresh_dimension_fpo()

    def start_point_picking(self) -> None:
        """Arm the always live point picking: every 3D click adds a point."""
        self.stop_picking()
        self.pick_mode = "point"
        self.pick_obs = snapper.getPoint(callback=self.add_point, continuous=True)
        self.form.add_shape.setText(translate("dimensioning", "Add Shape"))
        self.form.add_shape.setChecked(False)

    def start_shape_picking(self) -> None:
        """Arm the always live shape picking: every 3D click adds a shape."""
        self.stop_picking()
        self.pick_mode = "shape"
        self.pick_obs = snapper.getSelection(callback=self.add_shape)
        self.form.add_shape.setText(translate("dimensioning", "Picking shapes... Click to stop"))
        self.form.add_shape.setChecked(True)

    def stop_picking(self) -> None:
        """Cancel the active picking observer if any."""
        if self.pick_obs:
            self.pick_obs.cancel()
        self.pick_obs = None

    def toggle_pick_mode(self) -> None:
        """Switch the live picking mode between points and shapes."""
        if self.pick_mode == "point":
            self.start_shape_picking()
        else:
            self.start_point_picking()

    def add_reference_item(self, item_data, item_text: str) -> None:
        item = QtGui.QListWidgetItem()
        item.setText(item_text)
        item.setData(QtCore.Qt.UserRole, item_data)
        print("Dimension:    add reference {}".format(item_text))
        self.form.references.addItem(item)

    def add_point(self, vector=None) -> None:
        if not vector:
            return
        item_text = "Point {}".format(DraftVecUtils.tup(vector))
        self.add_reference_item(vector, item_text)
        self.refresh_dimension_fpo()

    def add_shape(self, info=None) -> None:
        if not info:
            return
        resolved = self.resolve_pick_info(info)
        if not resolved:
            return
        obj, sub_name, item_text = resolved
        if self.has_shape_reference(obj, sub_name):
            return
        self.add_reference_item((obj, sub_name), item_text)
        self.refresh_dimension_fpo()

    def resolve_pick_info(self, info) -> tuple | None:
        """Resolve a getObjectsInfo() dict to (obj, sub_name, item_text).

        sub_name follows the Gui.Selection convention (subelement name
        relative to obj) so DimensionFPO.get_references_data can resolve it.
        """
        obj = None
        obj_name = info.get("Object", "")
        if obj_name:
            obj = App.ActiveDocument.getObject(obj_name)
        if obj is None:
            parent = info.get("ParentObject", None)
            if parent is not None and hasattr(parent, "Name"):
                obj = parent
            else:
                App.Console.PrintWarning("Dimension:    cannot resolve the picked reference.\n")
                return None
        sub_name = info.get("Component", "") or info.get("SubName", "")
        if sub_name:
            return (obj, sub_name, "{} : {}".format(obj.Name, sub_name))
        return (obj, "", "{}".format(obj.Name))

    def has_shape_reference(self, obj, sub_name: str) -> bool:
        for i in range(self.form.references.count()):
            row = self.form.references.item(i).data(QtCore.Qt.UserRole)
            if isinstance(row, tuple) and len(row) == 2:
                row_obj, row_sub = row
                if getattr(row_obj, "Name", None) == obj.Name and row_sub == sub_name:
                    return True
        return False

    def remove_reference(self):
        listItems=self.form.references.selectedItems()
        if not listItems: 
            return        
        for item in listItems:
            self.form.references.takeItem(self.form.references.row(item))
        if self.highlighter:
            self.highlighter.clear()
        self.refresh_dimension_fpo()

    def refresh_dimension_fpo(self):
        references = []
        ref_point = []
        ref_shape = []
        for i in range(self.form.references.count()):
            item = self.form.references.item(i)
            references.append(item.data(QtCore.Qt.UserRole))
            if isinstance(item.data(QtCore.Qt.UserRole), Base.Vector):
                ref_point.append(item.data(QtCore.Qt.UserRole))
            else:
                ref_shape.append(item.data(QtCore.Qt.UserRole))
        self.fpo.ReferencePointsList = ref_point
        self.fpo.ReferenceShapesList = ref_shape
        self.fpo.recompute()
        
