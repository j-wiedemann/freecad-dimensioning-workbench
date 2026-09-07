# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Basic ViewProvider example.

see: https://wiki.freecad.org/Scripted_objects
"""

from __future__ import annotations
from ..resources import Resources
from .. import utils
from .. import snapper

import FreeCAD as App
import FreeCADGui as Gui
from FreeCAD import Base
import DraftVecUtils
import DraftGeomUtils
from PySide import QtCore, QtGui

translate = App.Qt.translate


class DimensionTaskPanel:
    def __init__(self, fpo=None) -> None:
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

        # observer
        self.add_point_obs = None
        
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
            # get potentiel best mode
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

        # connect signal
        self.form.angle.valueChanged.connect(self.angle_value_changed)
        self.form.text_size.valueChanged.connect(self.text_size_value_changed)
        self.form.arrow_size.valueChanged.connect(self.arrow_size_value_changed)
        self.form.offset.valueChanged.connect(self.offset_value_changed)
        self.form.modes.currentIndexChanged.connect(self.mode_changed)
        self.form.sector.currentIndexChanged.connect(self.sector_changed)
        self.form.projections.currentIndexChanged.connect(self.projection_changed)
        self.form.text_offset.valueChanged.connect(self.text_offset_value_changed)
        self.form.ext_line_offset.valueChanged.connect(self.ext_line_offset_value_changed)
        self.form.add_point.clicked.connect(self.add_point_clicked)
        self.form.add_shape.clicked.connect(self.add_selection_to_references)
        self.form.remove_reference.clicked.connect(self.remove_reference)
        self.form.create_dimension.clicked.connect(self.create_dimension)

    def accept(self):
        App.ActiveDocument.commitTransaction()
        if self.add_point_obs:
            self.add_point_obs.cancel()
        Gui.Control.closeDialog()

    def reject(self):
        App.ActiveDocument.abortTransaction()
        if self.add_point_obs:
            self.add_point_obs.cancel()
        Gui.Control.closeDialog()

    def create_dimension(self):
        App.ActiveDocument.commitTransaction()
        if self.add_point_obs:
            self.add_point_obs.cancel()
        Gui.Control.closeDialog()
        Gui.Selection.clearSelection()
        taskpanel = DimensionTaskPanel()
        QtCore.QTimer.singleShot(0, lambda: Gui.Control.showDialog(taskpanel))
                        
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

    def add_point_clicked(self):
        if self.add_point_obs:
            self.add_point_obs.cancel()
            self.form.add_point.setText(translate("dimensioning", "Add point"))
        else:
            self.add_point_obs = snapper.getPoint(callback=self.add_point)
            self.form.add_point.setText(translate("dimensioning", "Abort"))
    
    def add_point(self, vector=None):
        if vector:
            # add item in qlistwidget
            item_data = vector
            item_text = "Point {}".format(DraftVecUtils.tup(vector))
            item = QtGui.QListWidgetItem()
            item.setText(item_text)
            item.setData(QtCore.Qt.UserRole, item_data)
            print("Dimension:    add reference {}".format(item_text))
            self.form.references.addItem(item)
            self.add_point_obs = None
            self.form.add_point.setText(translate("dimensioning", "Add point"))
            self.refresh_dimension_fpo()

    def add_selection_to_references(self):
        selection = Gui.Selection.getCompleteSelection()
        if len(selection) < 1:
            return
        for sel in selection:
            obj = App.ActiveDocument.getObject(sel.ObjectName)
            if sel.HasSubObjects:
                for sub_name in sel.SubElementNames:
                    item_text = '{} : {}'.format(sel.ObjectName, sub_name)
                    item_data = (obj, sub_name)
            else:
                item_text = '{}'.format(sel.ObjectName)
                item_data = (obj, '')
            # add item in qlistwidget
            item = QtGui.QListWidgetItem()
            item.setText(item_text)
            item.setData(QtCore.Qt.UserRole, item_data)
            print("Dimension:    add reference {}".format(item_text))
            self.form.references.addItem(item)
        self.refresh_dimension_fpo()

    def remove_reference(self):
        listItems=self.form.references.selectedItems()
        if not listItems: 
            return        
        for item in listItems:
            self.form.references.takeItem(self.form.references.row(item))
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
        
