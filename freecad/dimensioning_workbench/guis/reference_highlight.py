# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Hover highlight of the dimension task panel references, drawn in the 3D view
with pivy/coin (same pattern as the Draft trackers).
"""

from __future__ import annotations
from .. import utils

import FreeCAD as App
import FreeCADGui as Gui
import Draft
import pivy.coin as coin
from PySide import QtCore

_FALLBACK_COLOR = (1.0, 1.0, 0.0)
_MARKER_SIZE = 9


def get_selection_color() -> tuple:
    """Return the user selection color as an (r, g, b) float tuple.

    The View preference SelectionColor is packed 0xRRGGBBAA; legacy 0xRRGGBB
    values (null alpha byte) are handled too. Falls back to yellow.
    """
    try:
        param = App.ParamGet("User parameter:BaseApp/Preferences/View")
        value = param.GetUnsigned("SelectionColor")
    except Exception:
        return _FALLBACK_COLOR
    if value <= 0:
        return _FALLBACK_COLOR
    if value & 0xFF == 0:
        # legacy packing without alpha
        return (
            ((value >> 16) & 0xFF) / 255.0,
            ((value >> 8) & 0xFF) / 255.0,
            (value & 0xFF) / 255.0,
        )
    return (
        ((value >> 24) & 0xFF) / 255.0,
        ((value >> 16) & 0xFF) / 255.0,
        ((value >> 8) & 0xFF) / 255.0,
    )


class ReferenceHighlighter(QtCore.QObject):
    """Highlight a dimension reference in the 3D view on list widget hover.

    Installs itself as an event filter on the references QListWidget viewport
    and follows the rows under the mouse. Item data conventions are the ones
    of DimensionTaskPanel:
    - App.Vector: picked point, a coin dot (SoMarkerSet) is drawn at it
    - (obj, sub_name): shape reference, a dot is drawn for vertices, a coin
      copy of the sub-shape is drawn for the other shapes, both at the actual
      (global) position resolved by utils.resolve_sub_shape.
    """

    def __init__(self, list_widget) -> None:
        super().__init__()
        self.list = list_widget
        self.hovered_row = None
        self.view = None
        self.switch = coin.SoSwitch()
        self.switch.whichChild = coin.SO_SWITCH_NONE
        list_widget.setMouseTracking(True)
        viewport = list_widget.viewport()
        viewport.setAttribute(QtCore.Qt.WA_Hover, True)
        viewport.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if event_type == QtCore.QEvent.HoverMove:
            row = self._row_at(event)
            if row != self.hovered_row:
                if row is None:
                    self.clear()
                else:
                    self._show_row(row)
        elif event_type in (QtCore.QEvent.HoverLeave, QtCore.QEvent.Leave):
            self.clear()
        return super().eventFilter(watched, event)

    def clear(self) -> None:
        """Hide the highlight and forget the hovered row."""
        self.hovered_row = None
        self.switch.whichChild = coin.SO_SWITCH_NONE

    def finalize(self) -> None:
        """Detach the highlight from the 3D view and stop following hovers.

        Idempotent, safe to call on panel teardown.
        """
        try:
            self.list.viewport().removeEventFilter(self)
        except RuntimeError:
            # the widget has been deleted already
            pass
        self.hovered_row = None
        self.switch.whichChild = coin.SO_SWITCH_NONE
        if self.view is not None:
            try:
                scene_graph = self.view.getSceneGraph()
                if scene_graph is not None and scene_graph.findChild(self.switch) >= 0:
                    scene_graph.removeChild(self.switch)
            except RuntimeError:
                # the view has been deleted already
                pass
            self.view = None

    def _row_at(self, event):
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        index = self.list.indexAt(pos)
        if not index.isValid():
            return None
        return index.row()

    def _show_row(self, row: int) -> None:
        item = self.list.item(row)
        if item is None:
            self.clear()
            return
        self.hovered_row = row
        node = self._build_node(item.data(QtCore.Qt.UserRole))
        if node is None:
            # keep hovered_row set so a failing reference does not retry on
            # every mouse move, only hide
            self.switch.whichChild = coin.SO_SWITCH_NONE
            return
        self._attach()
        while self.switch.getNumChildren():
            self.switch.removeChild(0)
        self.switch.addChild(node)
        self.switch.whichChild = 0

    def _attach(self) -> None:
        if self.view is not None:
            return
        view = Draft.get3DView()
        if view is None:
            return
        scene_graph = view.getSceneGraph()
        if scene_graph is None:
            return
        scene_graph.addChild(self.switch)
        self.view = view

    def _build_node(self, data):
        if data is None:
            return None
        if isinstance(data, App.Vector):
            return self._dot_node(data)
        if isinstance(data, tuple) and len(data) == 2:
            obj, sub_name = data
            shape = utils.resolve_sub_shape(obj, sub_name)
            if shape is None:
                return None
            if shape.ShapeType == "Vertex":
                return self._dot_node(shape.Point)
            return self._copy_node(shape)
        return None

    def _dot_node(self, point) -> coin.SoSeparator:
        style = coin.SoMaterial()
        style.diffuseColor.setValue(get_selection_color())
        style.setOverride(True)
        coords = coin.SoCoordinate3()
        coords.point.setValue((point.x, point.y, point.z))
        marker = coin.SoMarkerSet()
        marker.markerIndex = Gui.getMarkerIndex("CIRCLE_FILLED", _MARKER_SIZE)
        annotation = coin.SoAnnotation()
        annotation.addChild(coords)
        annotation.addChild(marker)
        node = coin.SoSeparator()
        node.setName("dimensionReferenceDot")
        node.addChild(style)
        node.addChild(annotation)
        return node

    def _copy_node(self, shape):
        # a pivy/coin copy of the shape: writeInventor converts any
        # edge/face/solid to LineSet/IndexedFaceSet nodes
        try:
            content = shape.writeInventor()
            input_buffer = coin.SoInput()
            input_buffer.setBuffer(content)
            root = coin.SoDB.readAll(input_buffer)
            if root is None:
                return None
            # the face fills are depth tested like a FreeCAD selection, the
            # edge lines coincide with the original edges and would lose the
            # depth test against them: they draw last with the depth buffer
            # function set to ALWAYS (tested: a SoAnnotation delayed pass does
            # not honor it and keeps the lines hidden)
            polygons = coin.SoSeparator()
            linework = coin.SoSeparator()
            linework_depth = coin.SoDepthBuffer()
            linework_depth.function = coin.SoDepthBuffer.ALWAYS
            linework.addChild(linework_depth)
            for i in range(root.getNumChildren()):
                section = root.getChild(i)
                if self._has_faces(section):
                    polygons.addChild(section)
                elif self._has_geometry(section):
                    linework.addChild(section)
            if polygons.getNumChildren() == 0 and linework.getNumChildren() == 0:
                return None
        except Exception:
            App.Console.PrintWarning(
                "ReferenceHighlighter:    cannot build a coin copy of the reference.\n"
            )
            return None
        style = coin.SoMaterial()
        style.diffuseColor.setValue(get_selection_color())
        # override the materials embedded in the writeInventor output
        style.setOverride(True)
        drawstyle = coin.SoDrawStyle()
        drawstyle.lineWidth = 2
        drawstyle.setOverride(True)
        # disable the backface culling the writeInventor ShapeHints can
        # trigger with a winding that does not match the traversal side
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE
        # flat uniform color like a FreeCAD selection, lighting off
        lightmodel = coin.SoLightModel()
        lightmodel.model = coin.SoLightModel.BASE_COLOR
        node = coin.SoSeparator()
        node.setName("dimensionReferenceCopy")
        node.addChild(style)
        node.addChild(drawstyle)
        node.addChild(hints)
        node.addChild(lightmodel)
        if polygons.getNumChildren():
            fills = coin.SoSeparator()
            # pull the coincident fill slightly toward the viewer so it is
            # not killed by the depth test against the original face, keep
            # the offset scoped to the fills: applied to the lines it would
            # push them behind the original edges
            offset = coin.SoPolygonOffset()
            offset.factor = -1.0
            offset.units = -1.0
            fills.addChild(offset)
            for i in range(polygons.getNumChildren()):
                fills.addChild(polygons.getChild(i))
            node.addChild(fills)
        if linework.getNumChildren():
            node.addChild(linework)
        return node

    def _has_geometry(self, node) -> bool:
        """Tell whether the node subtree holds a geometry element."""
        try:
            count = node.getNumChildren()
        except Exception:
            return False
        for i in range(count):
            child = node.getChild(i)
            name = str(child.getTypeId().getName())
            if name in ("IndexedFaceSet", "LineSet", "PointSet", "Coordinate3", "IndexedLineSet"):
                return True
            if self._has_geometry(child):
                return True
        return False

    def _has_faces(self, node) -> bool:
        """Tell whether the node subtree holds a face fill element."""
        try:
            count = node.getNumChildren()
        except Exception:
            return False
        for i in range(count):
            child = node.getChild(i)
            if str(child.getTypeId().getName()) == "IndexedFaceSet":
                return True
            if self._has_faces(child):
                return True
        return False
