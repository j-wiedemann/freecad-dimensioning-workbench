# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Dimension Feature Python Object
"""

from __future__ import annotations
from .. import utils
from ..resources import Resources
import math
import re

import FreeCAD as App
from FreeCAD import Vector as V
import Part
import DraftGeomUtils
import DraftVecUtils


def format_dim_value(value: float, decimals: int) -> str:
    """Format a dimension value: round to decimals and strip trailing zeros."""
    text = f"{value:.{decimals}f}"
    if decimals > 0:
        text = text.rstrip("0").rstrip(".")
    return text


class DimensionFPO:
    """Dimension feature python object"""
    def __init__(self, fpo: App.DocumentObject) -> None:
        DimensionFPO.setProperties(self, fpo)
        fpo.Proxy = self

    def setProperties(self, fpo: App.DocumentObject) -> None:
        pl = fpo.PropertiesList
        if "ReferenceShapesList" not in pl:
            fpo.addProperty("App::PropertyLinkSubListHidden", "ReferenceShapesList", "Dimension", "Dimension references shapes list.")
        if "ReferencePointsList" not in pl:
            fpo.addProperty("App::PropertyVectorList", "ReferencePointsList", "Dimension", "Dimension references points list.")
        if "Offset" not in pl:
            fpo.addProperty("App::PropertyDistance", "Offset", "Dimension", "Extension line length.").Offset = 100
        if "Angle" not in pl:
            fpo.addProperty("App::PropertyAngle", "Angle", "Dimension", "Angle orientation for circular dimension.").Angle = 45.0
        if "Mode" not in pl:
            fpo.addProperty("App::PropertyEnumeration", "Mode", "Dimension", "Dimension mode.")
            mode_list = [
                "X",
                "Y",
                "Z",
                "Distance",
                "Radius",
                "Diameter",
                "Angle",
                "ArcLength",
                "ChainX",
                "ChainY",
                "ChainZ",
            ]
            fpo.Mode = mode_list
        if "Projection" not in pl:
            fpo.addProperty("App::PropertyEnumeration", "Projection", "Dimension", "Projection direction.")
            projection_list = [
                "X",
                "Y",
                "Z",
                "Custom",
            ]
            fpo.Projection = projection_list
        if "TextOffset" not in pl:
            fpo.addProperty("App::PropertyDistance", "TextOffset", "Dimension", "Text position offset.").TextOffset = 0.0
        if "VerticalTextOffset" not in pl:
            fpo.addProperty(
                "App::PropertyDistance",
                "VerticalTextOffset",
                "Dimension",
                "Vertical offset of the text from the dimension line. When the text does not overlap the line anymore, the line is drawn continuous.",
                ).VerticalTextOffset = 0.0
        if "Sector" not in pl:
            fpo.addProperty("App::PropertyInteger", "Sector", "Dimension", "Angle sector.").Sector = 0
        if "ArrowSize" not in pl:
            fpo.addProperty("App::PropertyLength", "ArrowSize", "Dimension", "Size of the arrows.").ArrowSize = 18.0
        if "TextSize" not in pl:
            fpo.addProperty("App::PropertyLength", "TextSize", "Dimension", "Size of the text.").TextSize = 10.0
        if "ExtLineOffset" not in pl:
            fpo.addProperty("App::PropertyDistance", "ExtLineOffset", "Dimension", "Offset of the ext line from references.").ExtLineOffset = 5.0
        if "Prefix" not in pl:
            fpo.addProperty("App::PropertyString", "Prefix", "Dimension", "Text prepended before the automatic symbol and value.").Prefix = ""
        if "Suffix" not in pl:
            fpo.addProperty("App::PropertyString", "Suffix", "Dimension", "Text appended after the value.").Suffix = ""
        if "Override" not in pl:
            fpo.addProperty("App::PropertyString", "Override", "Dimension", "Replaces the measured value when non-empty; supports newlines and '$dim' to insert the rounded measured value.").Override = ""
        if "Decimals" not in pl:
            fpo.addProperty("App::PropertyIntegerConstraint", "Decimals", "Dimension", "Number of decimals shown in the dimension value.")
            fpo.Decimals = (2, 0, 6, 1)

    def onChanged(self, fpo: App.DocumentObject, prop: str) -> None:
        '''Do something when a property has changed'''
        # App.Console.PrintMessage("DimensionsFPO:    Change property: " + str(prop) + "\n")
        return

    def onDocumentRestored(self, fpo: App.DocumentObject) -> None:
        '''Ensure new properties exist when restoring documents created earlier'''
        self.setProperties(fpo)

    def execute(self, fpo: App.DocumentObject) -> None:
        '''Do something when doing a recomputation, this method is mandatory'''
        App.Console.PrintMessage("DimensionsFPO:    recompute called for {}\n".format(fpo.Name))
        if fpo.Mode in ["X", "Y", "Z"]:
            self.make_length_dimension(fpo)
        elif fpo.Mode == "Distance":
            self.make_distance_dimension(fpo)
        elif fpo.Mode in ["Radius", "Diameter"]:
            self.make_circular_dimension(fpo)
        elif fpo.Mode == "Angle":
            self.make_angular_dimension(fpo)
        elif fpo.Mode in ["ChainX", "ChainY", "ChainZ"]:
            self.make_chain_dimension(fpo)
        elif fpo.Mode == "ArcLength":
            self.make_arc_length_dimension(fpo)

    def make_length_dimension(self, fpo: App.DocumentObject) -> None:
        """
        Create a length dimension shape for linear measurements.
        """
        references_data = self.get_references_data(fpo)
        references = references_data['references']
        if references_data['vector_counter'] == 2:
            p1 = references[0]
            p2 = references[1]
        elif references_data['edge_counter'] == 2:
            p1 = references[0].Vertexes[0].Point
            p2 = references[1].Vertexes[0].Point
        elif references_data['edge_counter'] == 1 and references_data['vector_counter'] == 0:
            p1 = references[0].Vertexes[0].Point
            p2 = references[0].Vertexes[1].Point
        elif references_data['edge_counter'] == 1 and references_data['vector_counter'] == 1:
            if isinstance(references[0], Part.Edge):
                p1 = references[0].Vertexes[0].Point
                p2 = references[1]
            else:
                p2 = references[1].Vertexes[0].Point
                p1 = references[0]
        else:
            App.Console.PrintWarning("Dimension[Length]:    references provided are incoherent or not handle.\n")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            return
        
        # get the length depending on the mode. The base placement is the
        # first picked point, but the drawing follows the canonical axis
        # direction: when the second point stands opposite to it (inverse
        # pick order), the shape is mirrored along the axis while the text
        # keeps its reading orientation (see mirror_axis below).
        vec = p2.sub(p1)
        mirror_axis = False
        if fpo.Mode == "X":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(0,1,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,0,1))
            if vec_proj.x < 0.0:
                mirror_axis = True
        elif fpo.Mode == "Y":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(1,0,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,0,1))
            if vec_proj.y > 0.0:
                mirror_axis = True
        elif fpo.Mode == "Z":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(1,0,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,1,0))
            if vec_proj.z < 0.0:
                mirror_axis = True
        else:
            App.Console.PrintWarning("Dimension[Length]:    mode '{}' not handled.\n".format(fpo.Mode))
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        length = vec_proj.Length

        # make the dim text
        dim_text_shape = self.make_dim_text_shape(fpo, length)
        bb = dim_text_shape.BoundBox
        if fpo.Mode == "Z":
            angle = 90.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2 - fpo.VerticalTextOffset.Value,
                fpo.TextOffset.Value - bb.Center.y,
                0))
        elif fpo.Mode == "Y" and fpo.Projection == "Z":
            angle = -90.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2 + fpo.VerticalTextOffset.Value,
                -fpo.TextOffset.Value - bb.Center.y,
                0))
        else:
            angle = 0.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2 + fpo.TextOffset.Value,
                fpo.VerticalTextOffset.Value - bb.Center.y,
                0))
        dim_text_shape.rotate(V(length/2, 0, 0), V(0, 0, 1), angle*-1)
        bb = dim_text_shape.BoundBox
        
        # make arows
        left_arrow = self.make_arrow_shape(fpo)
        if abs(fpo.TextOffset.Value) > length/2:
            left_arrow.rotate(V(0, 0, 0), V(0, 0, 1), 180)
        right_arrow = left_arrow.mirror(V(length/2, 0, 0), V(1, 0, 0))
        
        # make lines: the dimension line is interrupted by the text only
        # while the text overlaps it; once the vertical text offset moves
        # the text clear of the line, the line is drawn as one continuous
        # line.
        text_on_line = (bb.YMin - 2.0) < 0.0 < (bb.YMax + 2.0)
        pl1 = V(left_arrow.BoundBox.XMax, 0, 0)
        if abs(fpo.TextOffset.Value) > length/2:
            pl2 = V(right_arrow.BoundBox.XMin, 0, 0)
        elif text_on_line:
            pl2 = V(bb.XMin - 8, 0, 0)
        else:
            pl2 = V(right_arrow.BoundBox.XMin, 0, 0)
        line1 = Part.makeLine(pl1, pl2)
        line2 = None
        if fpo.TextOffset.Value > length/2:
            pl1 = V(right_arrow.BoundBox.XMax, 0, 0)
            pl2 = V(bb.XMin - 8, 0, 0)
            line2 = Part.makeLine(pl1, pl2)
        elif fpo.TextOffset.Value < -length/2:
            pl1 = V(bb.XMax + 8, 0, 0)
            pl2 = V(left_arrow.BoundBox.XMin, 0, 0)
            line2 = Part.makeLine(pl1, pl2)
        elif text_on_line:
            pl1 = V(bb.XMax + 8, 0, 0)
            pl2 = V(length - left_arrow.BoundBox.XLength, 0, 0)
            line2 = Part.makeLine(pl1, pl2)
        
        # make extensions lines
        ext_line_start_length = abs(fpo.Offset.Value)
        ext_line_end_length = abs(fpo.Offset.Value)
        if fpo.Projection == "X":
            vec_prime = V(vec).projectToPlane(V(0,0,0),V(1,0,0))
            if fpo.Mode == "Y":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(0,1,0))
                if fpo.Offset.Value >= 0:
                    if p1.z < p2.z:
                        ext_line_start_length += vec_proj.Length
                    else:
                        ext_line_end_length += vec_proj.Length
                else:
                    if p1.z < p2.z:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
            elif fpo.Mode == "Z":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(0,0,1))
                if fpo.Offset.Value >= 0:
                    if p1.y < p2.y:
                        ext_line_start_length += vec_proj.Length
                    else:
                        ext_line_end_length += vec_proj.Length  
                else:
                    if p1.y < p2.y:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
        elif fpo.Projection == "Y":
            vec_prime = V(vec).projectToPlane(V(0,0,0),V(0,1,0))
            if fpo.Mode == "X":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(1,0,0))
                if fpo.Offset.Value >= 0:
                    if p1.z < p2.z:
                        ext_line_start_length += vec_proj.Length
                    else:
                        ext_line_end_length += vec_proj.Length
                else:
                    if p1.z < p2.z:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
            elif fpo.Mode == "Z":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(0,0,1))
                if fpo.Offset.Value >= 0:
                    if p1.y < p2.y:
                        ext_line_start_length += vec_proj.Length
                    else:
                        ext_line_end_length += vec_proj.Length  
                else:
                    if p1.y < p2.y:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
        elif fpo.Projection == "Z":
            vec_prime = V(vec).projectToPlane(V(0,0,0),V(0,0,1))
            if fpo.Mode == "X":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(1,0,0))
                if fpo.Offset.Value >= 0:
                    if p1.y > p2.y:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
                else:
                    if p1.y < p2.y:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length 
            elif fpo.Mode == "Y":
                vec_proj = vec_prime.projectToPlane(V(0,0,0),V(0,1,0))
                if fpo.Offset.Value >= 0:
                    if p1.x < p2.x:
                        ext_line_start_length += vec_proj.Length
                    else:
                        ext_line_end_length += vec_proj.Length
                else:
                    if p1.x < p2.x:
                        ext_line_end_length += vec_proj.Length
                    else:
                        ext_line_start_length += vec_proj.Length
                        

        sign = 1
        if fpo.Offset.Value < 0:
            sign = -1
        pe1 = V(0, 10 * sign, 0)
        pe2 = V(0, -ext_line_start_length * sign, 0)

        pc1 = V(length, 10 * sign, 0)
        pc2 = V(length, -ext_line_end_length * sign, 0)

        if fpo.Mode == "X":
            if fpo.Offset.Value >= 0:
                ext_line1 = Part.makeLine(pe1, pe2)
                ext_line2 = Part.makeLine(pc1, pc2)
            else:
                ext_line2 = Part.makeLine(pe1, pe2)
                ext_line1 = Part.makeLine(pc1, pc2)
        else:
            ext_line2 = Part.makeLine(pe1, pe2)
            ext_line1 = Part.makeLine(pc1, pc2)
        
        # respect pick order: when the second point lies opposite the
        # canonical axis direction, mirror the drawing along the axis so
        # the dimension extends from the first picked point, and reposition
        # the text without changing its reading orientation.
        if mirror_axis:
            left_arrow = left_arrow.mirror(V(), V(1, 0, 0))
            right_arrow = right_arrow.mirror(V(), V(1, 0, 0))
            line1 = line1.mirror(V(), V(1, 0, 0))
            if line2 is not None:
                line2 = line2.mirror(V(), V(1, 0, 0))
            ext_line1 = ext_line1.mirror(V(), V(1, 0, 0))
            ext_line2 = ext_line2.mirror(V(), V(1, 0, 0))
            tbb = dim_text_shape.BoundBox
            dim_text_shape.translate(V(-tbb.XMin - tbb.XMax, 0, 0))

        # make dimension shape compound
        dim_shape = Part.makeCompound(
            [part for part in [
                left_arrow,
                line1,
                dim_text_shape,
                line2,
                right_arrow,
                ext_line1,
                ext_line2,
            ] if part is not None]
            )

        pl = App.Placement()
        pl.Base = pl.multVec(p1.add(V(0, ext_line_start_length * sign, 0)))
        if fpo.Projection == "X":
            if fpo.Mode == "Y":
                pl.rotate(p1, V(0, 0, 1), -90, True)
                pl.rotate(p1, V(0, 1, 0), -90, True)
            elif fpo.Mode == "Z":
                pl.rotate(p1, V(0, 1, 0), -90, True)
        elif fpo.Projection == "Y":
            if fpo.Mode == "X":
                pl.rotate(p1, V(1, 0, 0), 90, True)
            elif fpo.Mode == "Z":
                pl.rotate(p1, V(0, 0, 1), 90, True)
                pl.rotate(p1, V(1, 0, 0), 90, True)
        elif fpo.Projection == "Z":
            if fpo.Mode == "X":
                pass
            elif fpo.Mode == "Y":
                pl.rotate(p1, V(0, 0, 1), -90, True)

        fpo.Shape = dim_shape
        fpo.Placement = pl
        fpo.recompute()

    def make_distance_dimension(self, fpo: App.DocumentObject) -> None:
        references_data = self.get_references_data(fpo)
        references = references_data['references']
        if references_data['vector_counter'] == 2:
            og_p1 = references[0]
            og_p2 = references[1]
        elif references_data['edge_counter'] == 1:
            og_p1 = references[0].Vertexes[0].Point
            og_p2 = references[0].Vertexes[1].Point
        else:
            App.Console.PrintWarning("Dimension[Distance]:    references provided are incoherent or not handle.\n")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        # keep the first picked point as the dimension base. The placement
        # frame stays on the canonical axis direction (vec_canonical) and,
        # when the second point stands opposite to it (inverse pick order),
        # the drawing is mirrored along the axis while the text keeps its
        # reading orientation (see mirror_axis below).
        p1 = V(og_p1)
        p2 = V(og_p2)
        vec = p2.sub(p1)
        main_dir = self.get_main_direction(V(vec))
        mirror_axis = False
        vec_canonical = V(vec)
        if main_dir == "X" and vec.x < 0.0:
            vec_canonical.multiply(-1.0)
            mirror_axis = True
        elif main_dir == "Y" and vec.y > 0.0:
            vec_canonical.multiply(-1.0)
            mirror_axis = True
        elif main_dir == "Z" and vec.z < 0.0:
            vec_canonical.multiply(-1.0)
            mirror_axis = True
        length = vec.Length
        # Make the dim text (tilt follows the canonical direction so the
        # text reading orientation is kept whatever the pick order)
        txt = self.make_dim_text_shape(fpo, length)
        vec_prime = V(vec_canonical).projectToPlane(V(0,0,0),V(0,0,1))
        angle = math.degrees(vec_canonical.getAngle(vec_prime))
        if math.isnan(angle):
            angle = 90.0
        if fpo.Sector == 1:
            angle = -angle
        elif fpo.Sector == 2:
            angle = 180-angle
        elif fpo.Sector == 3:
            angle = 180+angle
        txt.translate(
            V(length/2-txt.BoundBox.XLength/2-fpo.TextOffset.Value,
              fpo.VerticalTextOffset.Value-txt.BoundBox.Center.y+fpo.Offset.Value,
               0))
        txt.rotate(txt.BoundBox.Center, V(0,0,1), angle*-1)
        # make arrows
        left_arrow = self.make_arrow_shape(fpo)
        left_arrow.translate(V(0, fpo.Offset.Value, 0))
        right_arrow = left_arrow.mirror(V(length/2,0,0),V(1,0,0))
        # make lines: the dimension line is interrupted by the text only
        # while the text overlaps it; once the vertical text offset moves
        # the text clear of the line, the line is drawn as one continuous
        # line.
        text_on_line = (txt.BoundBox.YMin - 2.0) < fpo.Offset.Value < (txt.BoundBox.YMax + 2.0)
        line2 = None
        if text_on_line:
            pl1 = V(left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
            pl2 = V(txt.BoundBox.XMin - 8, fpo.Offset.Value, 0)
            line1 = Part.makeLine(pl1, pl2)
            pl1 = V(txt.BoundBox.XMax + 8, fpo.Offset.Value, 0)
            pl2 = V(length - left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
            line2 = Part.makeLine(pl1, pl2)
        else:
            pl1 = V(left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
            pl2 = V(length - left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
            line1 = Part.makeLine(pl1, pl2)
        # make extensions line
        if fpo.Offset.Value >= 0:
            if abs(fpo.Offset.Value) > fpo.ExtLineOffset.Value :
                y_base = fpo.ExtLineOffset.Value
            else:
                y_base = fpo.Offset.Value
            ext_line1 = Part.makeLine(
                V(0, y_base, 0),
                V(0, fpo.Offset.Value + fpo.ArrowSize.Value/2, 0))
            ext_line2 = Part.makeLine(
                V(length, y_base, 0),
                V(length, fpo.Offset.Value + fpo.ArrowSize.Value/2, 0))
        else:
            if abs(fpo.Offset.Value) > fpo.ExtLineOffset.Value :
                y_base = -fpo.ExtLineOffset.Value
            else:
                y_base = fpo.Offset.Value
            ext_line1 = Part.makeLine(
                V(0, y_base, 0),
                V(0, fpo.Offset.Value - fpo.ArrowSize.Value/2, 0))
            ext_line2 = Part.makeLine(
                V(length, y_base, 0),
                V(length, fpo.Offset.Value - fpo.ArrowSize.Value/2, 0))

        # get placement: the base is the first picked point and the frame
        # keeps the canonical axis direction
        pl = App.Placement()
        pl.Base = p1
        vz = V(0, 0, 1)
        if fpo.Projection == "X":
            vz = V(-1, 0, 0)
        elif fpo.Projection == "Y":
            vz = V(0, -1, 0)
        elif fpo.Projection == "Z":
            vz = V(0, 0, 1)
        pl.Rotation = App.Rotation(
            vec_canonical,
            V(0,1,0),
            vz,
            'XZY'
        )

        # respect pick order: when the second point lies opposite the
        # canonical direction, mirror the drawing along the axis so the
        # dimension extends from the first picked point, and reposition
        # the text without changing its reading orientation.
        if mirror_axis:
            left_arrow = left_arrow.mirror(V(), V(1, 0, 0))
            right_arrow = right_arrow.mirror(V(), V(1, 0, 0))
            line1 = line1.mirror(V(), V(1, 0, 0))
            if line2 is not None:
                line2 = line2.mirror(V(), V(1, 0, 0))
            ext_line1 = ext_line1.mirror(V(), V(1, 0, 0))
            ext_line2 = ext_line2.mirror(V(), V(1, 0, 0))
            tbb = txt.BoundBox
            txt.translate(V(-tbb.XMin - tbb.XMax, 0, 0))

        dim_shape = Part.makeCompound(
            [part for part in [
                left_arrow,
                txt,
                right_arrow,
                line1,
                line2,
                ext_line1,
                ext_line2,
            ] if part is not None]
            )
        fpo.Shape = dim_shape
        fpo.Placement = pl
        fpo.recompute()

    def make_circular_dimension(self, fpo: App.DocumentObject) -> None:
        """
        Create a circular dimension shape for radius or diameter measurements.
        """
        references_data = self.get_references_data(fpo)
        references = references_data['references']
        if len(references) == 0:
            App.Console.PrintWarning("Dimension[Circular]:    there is no reference, return empty shape\n")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        edge = references[0]
        if edge.ShapeType == 'Face':
            edge = edge.Edges[0]
        if not hasattr(edge, "Curve") or not hasattr(edge.Curve, "Axis"):
            App.Console.PrintWarning("Dimension[Circular]:    the reference is not a circular face or edge, return empty shape\n")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        loc = edge.Curve.Location
        axis = edge.Curve.Axis
        
        # radius value
        value = edge.Curve.Radius
        # make center cross
        l1 = Part.makeLine(V(-5, 0, 0), V(5, 0, 0))
        l2 = Part.makeLine(V(0, -5, 0), V(0, 5, 0))

        # make arrow
        arrow = self.make_arrow_shape(fpo)
        arrow.translate(V(value, 0, 0))
        arrow.rotate(V(), V(0, 0, 1), fpo.Angle)

        # 1st line to text
        p1 = DraftGeomUtils.findMidpoint(arrow.Edges[1])
        if fpo.Offset.Value != 0:
            length = p1.x + abs(fpo.Offset.Value)
        else:
            length = p1.x + 100.0
        p2 = V(length, p1.y, p1.z)
        l3 = Part.makeLine(p1, p2)
        l3.rotate(p1, V(0, 0, 1), fpo.Angle)

        # 2nd line to text
        if fpo.TextOffset.Value != 0:
            if 90 < fpo.Angle < 270:
                length = l3.Vertexes[1].Point.x - abs(fpo.TextOffset.Value)
            else:
                length = l3.Vertexes[1].Point.x + abs(fpo.TextOffset.Value)
        else:
            if 90 < fpo.Angle < 270:
                length = l3.Vertexes[1].Point.x - 100.0
            else:
                length = l3.Vertexes[1].Point.x + 100.0
        l4 = Part.makeLine(
            l3.Vertexes[1].Point,
            V(
                length,
                l3.Vertexes[1].Point.y,
                0)
                )

        dim_prefix = ""
        if fpo.Mode == "Radius":
            dim_prefix = "R"
            dim_value = value
        elif fpo.Mode == "Diameter":
            dim_prefix = "Ø"
            dim_value = value*2
        else:
            App.Console.PrintWarning("Dimension[Circular]:    mode '{}' not handled.\n".format(fpo.Mode))
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        dim_text_shape = self.make_dim_text_shape(fpo, dim_value, prefix=dim_prefix)
        bb = dim_text_shape.BoundBox
        if 90 < fpo.Angle < 270:
            x = l4.Vertexes[1].Point.x - bb.XLength - 10
            y = l4.Vertexes[1].Point.y - bb.Center.y + fpo.VerticalTextOffset.Value
            z = 0.0
        else:
            x = l4.Vertexes[1].Point.x
            y = l4.Vertexes[1].Point.y - bb.Center.y + fpo.VerticalTextOffset.Value
            z = 0.0
        dim_text_shape.translate(V(x,y,z))
        dim_shape = Part.makeCompound(
            [l1,
            l2,
            arrow,
            l3,
            l4,
            dim_text_shape,
            ])
        
        main_direction = self.get_main_direction(axis)
        if main_direction == "X":
            axis_rot = V(-1, 0, 0)
            vx = V(0, -1, 0)
        elif main_direction == "Y":
            axis_rot = V(0, -1, 0)
            vx = V(1, 0, 0)
        elif main_direction == "Z":
            axis_rot = V(0, 0, 1)
            vx = V(1, 0, 0)
        else:
            axis_rot = axis
            vx = edge.Placement.Rotation.multVec(V(1,0,0))

        rotation = App.Rotation(
                vx,        # Input X (will be used for X-axis alignment)
                V(0, 1, 0),    # Input Y (ignored in ZXY mode)
                axis_rot,        # Input Z (will be used for Z-axis alignment)
                'ZXY'          # Priority order
            )
        pl = App.Placement(loc, rotation)
        fpo.Shape = dim_shape
        fpo.Placement = pl
        fpo.recompute()

    def make_angular_dimension(self, fpo: App.DocumentObject) -> None:
        """
        Create an angular dimension shape measuring angles between edges or lines.
        """
        references_data = self.get_references_data(fpo)
        references = references_data['references']
        if references_data['vector_counter'] == 3:
            ref1 = DraftGeomUtils.edg(references[0], references[1])
            ref2 = DraftGeomUtils.edg(references[1], references[2])
        elif references_data['edge_counter'] == 2:
            ref1 = references[0]
            ref2 = references[1]
        else:
            App.Console.PrintWarning("Dimension[Angular]:    references provided are incoherent or not handle.\n")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            return
        if self.get_main_direction(ref1) == "X":
            if ref1.Vertexes[0].Point.x > ref1.Vertexes[1].Point.x:
                ref1 = DraftGeomUtils.edg(ref1.Vertexes[1].Point, ref1.Vertexes[0].Point)
        elif self.get_main_direction(ref1) == "Y":
            if ref1.Vertexes[0].Point.y < ref1.Vertexes[1].Point.y:
                ref1 = DraftGeomUtils.edg(ref1.Vertexes[1].Point, ref1.Vertexes[0].Point)
        elif self.get_main_direction(ref1) == "Z":
            if ref1.Vertexes[0].Point.z > ref1.Vertexes[1].Point.z:
                ref1 = DraftGeomUtils.edg(ref1.Vertexes[1].Point, ref1.Vertexes[0].Point)
        if self.get_main_direction(ref2) == "X":
            if ref2.Vertexes[0].Point.x > ref2.Vertexes[1].Point.x:
                ref2 = DraftGeomUtils.edg(ref2.Vertexes[1].Point, ref2.Vertexes[0].Point)
        elif self.get_main_direction(ref2) == "Y":
            if ref2.Vertexes[0].Point.y < ref2.Vertexes[1].Point.y:
                ref2 = DraftGeomUtils.edg(ref2.Vertexes[1].Point, ref2.Vertexes[0].Point)
        elif self.get_main_direction(ref2) == "Z":
            if ref2.Vertexes[0].Point.z > ref2.Vertexes[1].Point.z:
                ref2 = DraftGeomUtils.edg(ref2.Vertexes[1].Point, ref2.Vertexes[0].Point)

        # find normal from references
        pt1 = ref1.Vertexes[0].Point
        pt2 = ref1.Vertexes[1].Point
        if DraftGeomUtils.isPtOnEdge(ref2.Vertexes[0].Point, ref1):
            pt3 = ref2.Vertexes[1].Point
        else:
            pt3 = ref2.Vertexes[0].Point
        normal = DraftGeomUtils.get_normal(
            [pt1,
             pt2,
             pt3]
             )
        main_dir = self.get_main_direction(normal)
        if main_dir == "X":
            normal = V(-1, 0, 0)
        elif main_dir == "Y":
            normal = V(0, -1, 0)
        elif main_dir == "Z":
            normal = V(0, 0, 1)
        # else:
        #     normal = V(0, 0, 1)

        intersections = DraftGeomUtils.findIntersection(ref1, ref2, infinite1=True, infinite2=True,)
        center = intersections[0]
        # make list of 4 possibilities
        circle = Part.makeCircle(100, center, normal)
        c1_intersections = DraftGeomUtils.findIntersection(ref1, circle, infinite1=True)
        c2_intersections = DraftGeomUtils.findIntersection(ref2, circle, infinite1=True)

        vec_a = c1_intersections[0].sub(center)
        vec_b = c2_intersections[0].sub(center)
        vec_c = c1_intersections[1].sub(center)
        vec_d = c2_intersections[1].sub(center)

        if fpo.Sector == 0:
            angle = math.degrees(DraftVecUtils.angle(vec_a, vec_b, normal))
            vec_for_pl = vec_a
            if -180 < angle < 0:
                vec_for_pl = vec_b
                angle = abs(angle)
                
        elif fpo.Sector == 1:
            angle = math.degrees(DraftVecUtils.angle(vec_b, vec_c, normal))
            vec_for_pl = vec_b
            if -180 < angle < 0:
                vec_for_pl = vec_c
                angle = abs(angle)
                
        elif fpo.Sector == 2:
            angle = math.degrees(DraftVecUtils.angle(vec_c, vec_d, normal))
            vec_for_pl = vec_c
            if -180 < angle < 0:
                vec_for_pl = vec_d
                angle = abs(angle)
                
        elif fpo.Sector == 3:
            angle = math.degrees(DraftVecUtils.angle(vec_d, vec_a, normal))
            vec_for_pl = vec_d
            if -180 < angle < 0:
                vec_for_pl = vec_a
                angle = abs(angle)
        else:
            App.Console.PrintWarning("Dimension[Angular]:    sector '{}' not handled.\n".format(fpo.Sector))
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        arc = Part.makeCircle(abs(fpo.Offset.Value), V(0,0,0), V(0,0,1), 0.0, angle)
        
        p1 = V(abs(fpo.Offset.Value-10), 0, 0)
        p2 = V(abs(fpo.Offset.Value+10), 0, 0)
        line1 = Part.makeLine(p1, p2)
        line2 = line1.copy()
        line2.rotate(V(0.0, 0.0, 0.0), V(0.0, 0.0, 1.0), angle)

        _circle_arrow = Part.makeCircle(fpo.ArrowSize.Value, arc.Vertexes[0].Point, V(0,0,1))
        _intersection = DraftGeomUtils.findIntersection(arc, _circle_arrow)
        # mid = DraftGeomUtils.findMidpoint(arc)
        arrow = self.make_arrow_shape(fpo)
        arrow.Placement.Base = arc.Vertexes[0].Point
        arrow.Placement.Rotation = App.Rotation(
            _intersection[0].sub(arc.Vertexes[0].Point),
            V(0, 1, 0),
            V(0, 0, 1),
            'XZY',
        )
        _circle_arrow = Part.makeCircle(fpo.ArrowSize.Value, arc.Vertexes[1].Point, V(0,0,1))
        _intersection = DraftGeomUtils.findIntersection(arc, _circle_arrow)
        arrow2 = self.make_arrow_shape(fpo)
        arrow2.Placement.Base = arc.Vertexes[1].Point
        arrow2.Placement.Rotation = App.Rotation(
            _intersection[0].sub(arc.Vertexes[1].Point),
            V(0, 1, 0),
            V(0, 0, 1),
            'XZY',
        )
        if arrow.distToShape(arrow2)[0] <= 0.0:
            arrow.rotate(V(abs(fpo.Offset.Value), 0.0, 0.0), V(0.0, 0.0, 1.0), 180.0)
            arrow2.rotate(arrow2.Vertexes[0].Point, V(0.0, 0.0, 1.0), 180.0)
        dim_text_shape = self.make_dim_text_shape(fpo, angle, unit='°')
        arc_p = Part.makeCircle(abs(fpo.Offset.Value)+abs(fpo.TextOffset.Value), V(0,0,0), V(0,0,1), 0.0, angle)
        arc_mid_point = arc_p.valueAt(arc_p.Curve.parameterAtDistance(arc_p.Length/2, arc_p.FirstParameter))

        if main_dir == "X":
            angle_prime = math.degrees(vec_for_pl.getAngle(V(0, -1, 0)))
            rot = App.Rotation(vec_for_pl.normalize(), V(0,-1,0))
            if round(rot.getYawPitchRoll()[2], 3) != 0.0:
                angle_p = rot.getYawPitchRoll()[2]
            else:
                angle_p = angle_prime
            dim_text_shape.rotate(dim_text_shape.BoundBox.Center, V(0, 0, 1), -angle_p)
        elif main_dir == "Y":
            angle_prime = math.degrees(vec_for_pl.getAngle(V(1, 0, 0)))
            rot = App.Rotation(vec_for_pl.normalize(), V(1, 0, 0))
            if  round(rot.getYawPitchRoll()[1], 3) != 0.0:
                angle_p = rot.getYawPitchRoll()[1]
            else:
                angle_p = angle_prime
            dim_text_shape.rotate(dim_text_shape.BoundBox.Center, V(0, 0, 1), -angle_p)
        elif main_dir == "Z":
            angle_prime = math.degrees(vec_for_pl.getAngle(V(1, 0, 0)))
            dim_text_shape.rotate(dim_text_shape.BoundBox.Center, V(0, 0, 1), angle_prime)

        # The text is oriented before being positioned: rotating a placed
        # multiline block about its bounding box center shifts the box off
        # the arc bisector, so the rotated block is centered on the
        # bisector point using its final bounding box. The vertical text
        # offset moves the block radially, off the dimension arc.
        dim_text_target = arc_mid_point
        arc_text_radius = abs(fpo.Offset.Value) + abs(fpo.TextOffset.Value)
        if fpo.VerticalTextOffset.Value != 0.0 and arc_text_radius > 1e-7:
            scale = (arc_text_radius + fpo.VerticalTextOffset.Value) / arc_text_radius
            dim_text_target = V(arc_mid_point.x * scale, arc_mid_point.y * scale, 0.0)
        dim_text_cog = dim_text_target.sub(dim_text_shape.BoundBox.Center)
        dim_text_cog.z = 0.0
        dim_text_shape.translate(dim_text_cog)

        bb_txt = dim_text_shape.BoundBox
        bb_txt.enlarge(2)
        circle_tt = Part.makeCircle(bb_txt.DiagonalLength/2, bb_txt.Center, V(0,0,1))
        inter_bb = DraftGeomUtils.findIntersection(arc, circle_tt)
        inter_arrow1 = DraftGeomUtils.findIntersection(arc, arrow.Edges[1])
        inter_arrow2 = DraftGeomUtils.findIntersection(arc, arrow2.Edges[1])
        if len(inter_bb) == 2:
            if len(inter_arrow1) == 1:
                arc1 = DraftGeomUtils.arcFrom2Pts(inter_arrow1[0], inter_bb[0], V(0,0,0))
            else:
                arc1 = DraftGeomUtils.arcFrom2Pts(arc.firstVertex().Point, inter_bb[0], V(0,0,0))
            if len(inter_arrow2) == 1:
                arc2 = DraftGeomUtils.arcFrom2Pts(inter_bb[1], inter_arrow2[0], V(0,0,0))
            else:
                arc2 = DraftGeomUtils.arcFrom2Pts(inter_bb[1], arc.lastVertex().Point, V(0,0,0))
            comp_list = [arc1, arc2]
        else:
            if len(inter_arrow1) == 1:
                first_point = inter_arrow1[0]
            else:
                first_point = arc.firstVertex().Point
            if len(inter_arrow2) == 1:
                last_point = inter_arrow2[0]
            else:
                last_point = arc.lastVertex().Point
            arc = DraftGeomUtils.arcFrom2Pts(first_point, last_point, V(0,0,0))
            comp_list = [arc]
        comp_list.extend([
            line1,
            line2,
            arrow,
            arrow2,
            dim_text_shape,])
        dim_shape = Part.makeCompound(comp_list)
        # Part.show(dim_shape)
        pl = App.Placement()
        pl.Base = intersections[0]
        pl.Rotation = App.Rotation(
                vec_for_pl,        # Input X (will be used for X-axis alignment)
                V(0, 1, 0),    # Input Y (ignored in ZXY mode)
                normal,        # Input Z (will be used for Z-axis alignment)
                'XZY'          # Priority order
            )
        fpo.Shape = dim_shape
        fpo.Placement = pl
        fpo.recompute()

    def make_chain_dimension(self, fpo):
        references_data = self.get_references_data(fpo)
        references = references_data['references']
        if fpo.Mode == "ChainX":
            # the first picked reference is the chain origin
            for ref in references:
                ref.projectToPlane(references[0], V(0, 1, 0))
                ref.projectToPlane(references[0], V(0, 0, 1))
            distances = [0.0]
            for ref in references[1:]:
                distances.append(ref.sub(references[0]).Length)
            comp = []
            c = 0
            for ref in references:
                line = Part.makeLine(references[c], references[c].add(V(0, 0, fpo.Offset.Value)))
                comp.append(line)
                txt = self.make_dim_text_shape(fpo, distances[c])
                txt.rotate(V(0, 0, 0), V(0, 0, 1), 90)
                txt.rotate(V(0, 0, 0), V(1, 0, 0), 90)
                txt.translate(line.Vertexes[1].Point.add(V(-txt.BoundBox.Center.x, 0, txt.BoundBox.ZMin)))
                comp.append(txt)
                c += 1

            shape = Part.makeCompound(comp)
            fpo.Shape = shape
            fpo.Placement = App.Placement()
            fpo.recompute()
        elif fpo.Mode == "ChainY":
            # the first picked reference is the chain origin
            for ref in references:
                ref.projectToPlane(references[0], V(1, 0, 0))
                ref.projectToPlane(references[0], V(0, 0, 1))
            distances = [0.0]
            for ref in references[1:]:
                distances.append(ref.sub(references[0]).Length)
            comp = []
            c = 0
            for ref in references:
                line = Part.makeLine(references[c], references[c].add(V(0, 0, fpo.Offset.Value)))
                comp.append(line)
                txt = self.make_dim_text_shape(fpo, distances[c])
                txt.rotate(V(0, 0, 0), V(0, 1, 0), -90)
                txt.translate(line.Vertexes[1].Point.add(V(0,-txt.BoundBox.XMin/2, txt.BoundBox.ZMin)))
                comp.append(txt)
                c += 1
            shape = Part.makeCompound(comp)
            fpo.Shape = shape
            fpo.Placement = App.Placement()
            fpo.recompute()
        elif fpo.Mode == "ChainZ":
            # the first picked reference is the chain origin
            for ref in references:
                ref.projectToPlane(references[0], V(1, 0, 0))
                ref.projectToPlane(references[0], V(0, 1, 0))
            distances = [0.0]
            for ref in references[1:]:
                distances.append(ref.sub(references[0]).Length)
            comp = []
            c = 0
            for ref in references:
                line = Part.makeLine(references[c], references[c].add(V(-fpo.Offset.Value, 0, 0)))
                comp.append(line)
                txt = self.make_dim_text_shape(fpo, distances[c])
                txt.rotate(V(0, 0, 0), V(1, 0, 0), 90)
                txt.translate(line.Vertexes[1].Point.add(V(-txt.BoundBox.XLength-5, 0, -txt.BoundBox.Center.z)))
                comp.append(txt)
                c += 1
            shape = Part.makeCompound(comp)
            fpo.Shape = shape
            fpo.Placement = App.Placement()
            fpo.recompute()

    def make_arc_length_dimension(self, fpo: App.DocumentObject) -> None:
        """
        make the shape of an arc length dimension from a circular edge or 3 points

        """
        App.Console.PrintMessage("Dimension[ArcLength]:    called for {} fpo.".format(fpo.Name))
        references_data = self.get_references_data(fpo)
        references = references_data['references']

        if len(references) == 1 and hasattr(references[0], "ShapeType") and references[0].ShapeType == "Edge":
            if not hasattr(references[0], "Curve") or not hasattr(references[0].Curve, "Axis"):
                App.Console.PrintWarning("Dimension[ArcLength]:    the reference is not a circular edge, return empty shape\n")
                fpo.Shape = Part.Shape()
                fpo.Placement = App.Placement()
                fpo.recompute()
                return
            else:
                mode = "arc"
        elif len(references) == 3 and isinstance(references[0], V) and isinstance(references[1], V) and isinstance(references[2], V):
            mode = "3points"
        else:
            App.Console.PrintError("Dimension[ArcLength]:    Return 2")
            fpo.Shape = Part.Shape()
            fpo.Placement = App.Placement()
            fpo.recompute()
            return
        if mode == "3points":
            try:
                edge = Part.Arc(references[0], references[1], references[2]).toShape()
            except Part.OCCError as error:
                App.Console.PrintError("Dimension[ArcLength]:    Cannot generate shape ({})".format(error))
                fpo.Shape = Part.Shape()
                fpo.Placement = App.Placement()
                fpo.recompute()
                return
        else:
            edge = references[0]

        arc_length = edge.Length
        radius = edge.Curve.Radius
        center = edge.Curve.Location
        axis = edge.Curve.Axis
        main_dir_axis = self.get_main_direction(axis)
        if main_dir_axis == "X":
            vx = V(0, -1, 0)
            vz = V(-1, 0, 0)
        elif main_dir_axis == "Y":
            vx = V(1, 0, 0)
            vz = V(0, -1, 0)
        else:
            vx = V(1, 0, 0)
            vz = V(0, 0, 1)

        # make
        circle = Part.makeCircle(radius+fpo.Offset.Value, center, vz)
        edg1 = Part.makeLine(center, edge.Vertexes[0].Point)
        intersection = DraftGeomUtils.findIntersection(circle, edg1, infinite2=True)
        startpoint = intersection[DraftGeomUtils.findClosest(edge.Vertexes[0].Point, intersection)]
        edg2 = Part.makeLine(center, edge.Vertexes[1].Point)
        intersection = DraftGeomUtils.findIntersection(circle, edg2, infinite2=True)
        endpoint = intersection[DraftGeomUtils.findClosest(edge.Vertexes[1].Point, intersection)]
        mid = DraftGeomUtils.findMidpoint(edge)
        edg3 = Part.makeLine(center, mid)
        intersection = DraftGeomUtils.findIntersection(circle, edg3, infinite2=True)
        midpoint = intersection[DraftGeomUtils.findClosest(mid, intersection)]

        # make arrows
        _circle_arrow = Part.makeCircle(fpo.ArrowSize.Value, startpoint, vz)
        intersection = DraftGeomUtils.findIntersection(circle, _circle_arrow)
        arc_start_pt1 = intersection[DraftGeomUtils.findClosest(mid, intersection)]
        arrow = self.make_arrow_shape(fpo)
        arrow.Placement.Base = startpoint
        arrow.Placement.Rotation = App.Rotation(
            arc_start_pt1.sub(startpoint),
            V(0, 1, 0),
            vz,
            'XZY',
        )

        _circle_arrow = Part.makeCircle(fpo.ArrowSize.Value, endpoint, vz)
        intersection = DraftGeomUtils.findIntersection(circle, _circle_arrow)
        arc_end_pt1 = intersection[DraftGeomUtils.findClosest(mid, intersection)]
        arrow2 = self.make_arrow_shape(fpo)
        arrow2.Placement.Base = endpoint
        arrow2.Placement.Rotation = App.Rotation(
            arc_end_pt1.sub(endpoint),
            V(0, 1, 0),
            vz,
            'XZY',
        )
 
        # make ext lines
        v = DraftGeomUtils.getTangent(edge, edge.Vertexes[0].Point)
        ext_line1 = Part.makeLine(V(-fpo.ArrowSize.Value, 0, 0), V(fpo.ArrowSize.Value, 0, 0))
        ext_line1.Placement.Base = startpoint
        ext_line1.Placement.Rotation = App.Rotation(
            V(1,0,0),
            v,
            vz,
            "YZX"
        )
        v = DraftGeomUtils.getTangent(edge, edge.Vertexes[1].Point)
        ext_line2 = Part.makeLine(V(-fpo.ArrowSize.Value, 0, 0), V(fpo.ArrowSize.Value, 0, 0))
        ext_line2.Placement.Base = endpoint
        ext_line2.Placement.Rotation = App.Rotation(
            V(1,0,0),
            v,
            vz,
            "YZX"
        )

        # make dim txt
        txt = self.make_dim_text_shape(fpo, arc_length)
        # make arc_length symbol
        arc_symbol = Part.makeCircle(txt.BoundBox.YLength, V(0,0,0), V(0,0,1), 0, 180)
        txt.translate(V(arc_symbol.BoundBox.XMax+5, 0, 0))
        bb = txt.BoundBox.united(arc_symbol.BoundBox)
        txt.translate(V(0,0,0).sub(bb.Center))
        arc_symbol.translate(V(0,0,0).sub(bb.Center))
        dim_shape = Part.makeCompound([arc_symbol, txt])
        dim_shape.Placement.Base = midpoint
        # the vertical text offset moves the block radially, off the arc
        if fpo.VerticalTextOffset.Value != 0.0:
            radial = midpoint.sub(center)
            if radial.Length > 1e-7:
                radial.normalize()
                dim_shape.Placement.Base = midpoint.add(radial.multiply(fpo.VerticalTextOffset.Value))
        dim_shape.Placement.Rotation = App.Rotation(
            vx,
            V(0,1,0),
            vz,
            'XZY'
        )

        # make portion arcs: they shorten to leave room for the text only
        # while the text overlaps the arc; once the vertical text offset
        # moves the text clear of it, the arc is drawn as one continuous
        # arc between the arrows.
        _circle = Part.makeCircle(dim_shape.BoundBox.DiagonalLength/2, dim_shape.BoundBox.Center, vz)
        _intersection = DraftGeomUtils.findIntersection(circle, _circle)
        arc_end = None
        if _intersection:
            arc_start_pt2 = _intersection[DraftGeomUtils.findClosest(startpoint, _intersection)]
            arc_end_pt2 = _intersection[DraftGeomUtils.findClosest(endpoint, _intersection)]
            arc_start = DraftGeomUtils.arcFrom2Pts(arc_start_pt1, arc_start_pt2, center)
            arc_end = DraftGeomUtils.arcFrom2Pts(arc_end_pt1, arc_end_pt2, center)
        else:
            arc_start = DraftGeomUtils.arcFrom2Pts(arc_start_pt1, arc_end_pt1, center)
        shape = Part.makeCompound(
            [part for part in [arrow, arrow2, dim_shape, ext_line1, ext_line2, arc_start, arc_end]
             if part is not None]
            )
        fpo.Shape = shape
        fpo.Placement = App.Placement()
        fpo.recompute()

    def get_references_data(self, fpo) -> dict:
        """
        Extract geometric references from dimension feature object.
        
        Processes ReferencePointsList and ReferenceShapesList to collect all
        vertices, edges, and faces, returning reference objects with counters.
        
        Sub-shapes are resolved in global coordinates via
        utils.resolve_sub_shape: when a referenced object lives inside a
        container with a placement (e.g. App::Part, or nested App::Part
        containers), the ancestor placement chain is applied via
        getGlobalPlacement() so the dimension is built at the geometry's
        actual position in the document. This is the same resolution used
        for the hover highlight of the task panel references list.

        Args:
            fpo: Feature Python Object, the freecad dimension object
            
        Returns:
            dict with keys: references, vector_counter, edge_counter,
                          face_counter, shape_counter
        """
        references = []
        vector_counter = 0
        for v in fpo.ReferencePointsList:
            vector_counter += 1
            references.append(v)
        edge_counter = 0
        face_counter = 0
        shape_counter = 0
        for ref in fpo.ReferenceShapesList:
            obj, sub_names = ref[0], ref[1]
            for sub_name in sub_names:
                sub_shape = utils.resolve_sub_shape(obj, sub_name)
                if sub_shape is None:
                    continue
                if sub_shape.ShapeType == 'Face':
                    face_counter += 1
                    references.append(sub_shape)
                elif sub_shape.ShapeType == 'Edge':
                    edge_counter += 1
                    references.append(sub_shape)
                elif sub_shape.ShapeType == 'Vertex':
                    vector_counter += 1
                    references.append(sub_shape.Point)
        return {
            "references":references,
            "vector_counter":vector_counter,
            "edge_counter":edge_counter,
            "face_counter":face_counter,
            "shape_counter":shape_counter,
            }
    
    def get_main_plane(self, vec):
        pass

    def make_arrow_shape(self, fpo) -> Part.Shape:
        """
        Create a triangular arrow shape for dimension arrows.
        
        Constructs a right-pointing arrow with isosceles triangle geometry,
        where the base width is size/3 and height is size.
        
        Parameters
        ----------
        size : float, optional
            Length of the arrow in X direction (default is 18).
            Also determines the arrow head dimensions.
            
        Returns
        -------
        Part.Shape
            A triangular Part shape representing the arrow.
        """
        p1 = V(0, 0, 0)
        p2 = V(fpo.ArrowSize, fpo.ArrowSize/5, 0)
        p3 = V(fpo.ArrowSize, -fpo.ArrowSize/5, 0)
        arrow = Part.makePolygon([p1, p2, p3, p1])
        return arrow
    
    def make_wire_string_shape(self, fpo, string):
        """Render a single text line as a Part compound shape.

        Returns None for an empty string or a string without drawable
        glyphs (e.g. whitespace only) so blank lines still advance the
        line stack in make_dim_text_shape.
        """
        if not string:
            return None
        wire_string_dim_text = Part.makeWireString(
            string,
            Resources.font(''),
            "/ReliefSingleLineCAD-Regular.ttf",
            fpo.TextSize,
            0.25,
            )
        pile = wire_string_dim_text[::-1]
        dim_text_wires = []
        while pile:
            element = pile.pop()
            if isinstance(element, list):
                pile.extend(element[::-1])
            else:
                dim_text_wires.append(element)
        if not dim_text_wires:
            return None
        return Part.makeCompound([s.removeShape(s.Edges[-1]) for s in dim_text_wires])

    def make_dim_text_lines(self, fpo, value, prefix=None, suffix=None, unit=None, tol_sup=None, tol_inf=None):
        """Compose the final dimension text and return its lines.

        Final text is: Prefix + automatic symbol (R/Ø for circular modes)
        + (Override if non-empty, else the rounded value and its unit)
        + Suffix. In the Override text, "$dim" (case-insensitive) is
        replaced by the rounded measured value and its unit.
        Newlines split the text into stacked lines.
        """
        if getattr(fpo, "Override", ""):
            dim_value = format_dim_value(value, getattr(fpo, "Decimals", 2))
            if unit:
                dim_value += "{}".format(unit)
            core = re.sub(r"\$dim", dim_value, fpo.Override, flags=re.IGNORECASE)
        else:
            core = format_dim_value(value, getattr(fpo, "Decimals", 2))
            if unit:
                core += "{}".format(unit)
        text = "{}{}{}{}".format(
            getattr(fpo, "Prefix", "") or "",
            prefix or "",
            core,
            getattr(fpo, "Suffix", "") or "",
            )
        return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def make_dim_text_shape(self, fpo, value, prefix=None, suffix=None, unit=None, tol_sup=None, tol_inf=None):
        """Render the dimension text and stack its lines into one shape.

        The rendered line height depends on the font: some fonts (e.g.
        ReliefSingleLineCAD) draw glyphs much taller than the requested
        TextSize, so a fixed TextSize based line spacing makes multiline
        texts overlap. The line pitch is therefore derived from the lines
        bounding boxes: it covers the tallest and the lowest glyphs of
        all the lines plus a gap, which keeps the spacing even and
        guarantees two adjacent lines never intersect.
        """
        lines = self.make_dim_text_lines(fpo, value, prefix=prefix, suffix=suffix, unit=unit, tol_sup=tol_sup, tol_inf=tol_inf)
        shapes = [self.make_wire_string_shape(fpo, line) for line in lines]
        boxes = [shape.BoundBox for shape in shapes if shape is not None]
        if not boxes:
            return Part.Shape()
        line_span = max(box.YMax for box in boxes) - min(box.YMin for box in boxes)
        line_height = max(line_span * 1.3, fpo.TextSize.Value * 1.5)
        stacked_shapes = []
        offset = 0.0
        for shape in shapes:
            if shape is not None:
                shape.translate(V(0, offset, 0))
                stacked_shapes.append(shape)
            offset -= line_height
        if len(stacked_shapes) == 1:
            return stacked_shapes[0]
        return Part.makeCompound(stacked_shapes)
    
    def get_main_direction(self, obj:App.Vector|Part.Edge) -> str:
        if isinstance(obj, Part.Edge):
            vec = DraftGeomUtils.vec(obj)
        else:
            vec = obj
        if not vec:
            return "X"
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

    @classmethod
    def create(cls, name: str | None = None, doc: App.Document | None = None) -> DimensionFPO:
        """Optional utility method to create instances of this feature"""

        # Check valid document
        if not (doc := doc or App.ActiveDocument):
            raise ValueError("A FreeCAD document is required")

        # Create the c++ DocumentObject
        # see: https://wiki.freecad.org/App_FeaturePython
        obj = doc.addObject("Part::FeaturePython", name or "Dimension_000")

        # Bind the Python Proxy
        cls(obj)

        # Manage Gui (ViewProvider) if available
        if App.GuiUp and hasattr(obj, "ViewObject"):
            from .dimension_vp import DimensionViewProvider
            DimensionViewProvider(obj.ViewObject)

        obj.recompute()
        return obj
