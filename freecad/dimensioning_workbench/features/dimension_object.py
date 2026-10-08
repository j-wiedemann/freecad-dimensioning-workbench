# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Dimension Feature Python Object
"""

from __future__ import annotations
from ..resources import Resources
import math

import FreeCAD as App
from FreeCAD import Vector as V
import Part
import DraftGeomUtils
import DraftVecUtils


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
        if "Sector" not in pl:
            fpo.addProperty("App::PropertyInteger", "Sector", "Dimension", "Angle sector.").Sector = 0
        if "ArrowSize" not in pl:
            fpo.addProperty("App::PropertyLength", "ArrowSize", "Dimension", "Size of the arrows.").ArrowSize = 18.0
        if "TextSize" not in pl:
            fpo.addProperty("App::PropertyLength", "TextSize", "Dimension", "Size of the text.").TextSize = 10.0
        if "ExtLineOffset" not in pl:
            fpo.addProperty("App::PropertyDistance", "ExtLineOffset", "Dimension", "Offset of the ext line from references.").ExtLineOffset = 5.0
    
    def onChanged(self, fpo: App.DocumentObject, prop: str) -> None:
        '''Do something when a property has changed'''
        # App.Console.PrintMessage("DimensionsFPO:    Change property: " + str(prop) + "\n")
        return

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
        
        # get the length depending the mode and inverse point to follow orientation
        vec = p2.sub(p1)
        if fpo.Mode == "X":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(0,1,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,0,1))
            if [p1.x, p2.x].index(min(p1.x, p2.x)) == 1:
                p1,p2 = V(p2),V(p1)
        elif fpo.Mode == "Y":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(1,0,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,0,1))
            if [p1.y, p2.y].index(max(p1.y, p2.y)) == 1:
                p1,p2 = V(p2),V(p1)
        elif fpo.Mode == "Z":
            vec_prime = V(vec).projectToPlane(V(0,0,0), V(1,0,0))
            vec_proj = vec_prime.projectToPlane(V(0,0,0), V(0,1,0))
            if [p1.z, p2.z].index(min(p1.z, p2.z)) == 1:
                p1,p2 = V(p2),V(p1)
        length = vec_proj.Length

        # make the dim text
        dim_text_shape = self.make_dim_text_shape(fpo, length)
        bb = dim_text_shape.BoundBox
        if fpo.Mode == "Z":
            angle = 90.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2,
                fpo.TextOffset.Value - bb.YLength/2,
                0))
        elif fpo.Mode == "Y" and fpo.Projection == "Z":
            angle = -90.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2,
                -fpo.TextOffset.Value - bb.YLength/2,
                0))
        else:
            angle = 0.0
            dim_text_shape.translate(V(
                length/2 - bb.XLength/2 + fpo.TextOffset.Value,
                -bb.YLength/2,
                0))
        dim_text_shape.rotate(V(length/2, 0, 0), V(0, 0, 1), angle*-1)
        bb = dim_text_shape.BoundBox
        
        # make arows
        left_arrow = self.make_arrow_shape(fpo)
        if abs(fpo.TextOffset.Value) > length/2:
            left_arrow.rotate(V(0, 0, 0), V(0, 0, 1), 180)
        right_arrow = left_arrow.mirror(V(length/2, 0, 0), V(1, 0, 0))
        
        # make lines
        pl1 = V(left_arrow.BoundBox.XMax, 0, 0)
        if abs(fpo.TextOffset.Value) > length/2:
            pl2 = V(right_arrow.BoundBox.XMin, 0, 0)
        else:
            pl2 = V(bb.XMin - 8, 0, 0)
        line1 = Part.makeLine(pl1, pl2)
        if fpo.TextOffset.Value > length/2:
            pl1 = V(right_arrow.BoundBox.XMax, 0, 0)
            pl2 = V(bb.XMin - 8, 0, 0)
        elif fpo.TextOffset.Value < -length/2:
            pl1 = V(bb.XMax + 8, 0, 0)
            pl2 = V(left_arrow.BoundBox.XMin, 0, 0)
        else:
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
        elif fpo.Mode == "Y":
            if fpo.Offset.Value >= 0:
                ext_line2 = Part.makeLine(pe1, pe2)
                ext_line1 = Part.makeLine(pc1, pc2)
            else:
                ext_line2 = Part.makeLine(pe1, pe2)
                ext_line1 = Part.makeLine(pc1, pc2)
        elif fpo.Mode == "Z":
            if fpo.Offset.Value >= 0:
                ext_line2 = Part.makeLine(pe1, pe2)
                ext_line1 = Part.makeLine(pc1, pc2)
            else:
                ext_line2 = Part.makeLine(pe1, pe2)
                ext_line1 = Part.makeLine(pc1, pc2)
        
        # make dimension shape compound
        dim_shape = Part.makeCompound(
            [left_arrow,
            line1,
            dim_text_shape,
            line2,
            right_arrow,
            ext_line1,
            ext_line2
            ])

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
        main_dir = self.get_main_direction(og_p2.sub(og_p1))
        if (main_dir == "X" and og_p1.x > og_p2.x) or \
        (main_dir == "Y" and og_p1.y < og_p2.y) or \
        (main_dir == "Z" and og_p1.z > og_p2.z):
            p1 = V(og_p2)
            p2 = V(og_p1)
        else:
            p1 = V(og_p1)
            p2 = V(og_p2)
        vec = p2.sub(p1)
        length = vec.Length
        # Make the dim text
        txt = self.make_dim_text_shape(fpo, length)
        vec_prime = V(vec).projectToPlane(V(0,0,0),V(0,0,1))
        angle = math.degrees(vec.getAngle(vec_prime))
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
              -txt.BoundBox.YLength/2+fpo.Offset.Value,
               0))
        txt.rotate(txt.BoundBox.Center, V(0,0,1), angle*-1)
        # make arrows
        left_arrow = self.make_arrow_shape(fpo)
        left_arrow.translate(V(0, fpo.Offset.Value, 0))
        right_arrow = left_arrow.mirror(V(length/2,0,0),V(1,0,0))
        # make lines
        pl1 = V(left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
        pl2 = V(txt.BoundBox.XMin - 8, fpo.Offset.Value, 0)
        line1 = Part.makeLine(pl1, pl2)
        pl1 = V(txt.BoundBox.XMax + 8, fpo.Offset.Value, 0)
        pl2 = V(length - left_arrow.BoundBox.XLength, fpo.Offset.Value, 0)
        line2 = Part.makeLine(pl1, pl2)
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

        # get placement
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
            vec,
            V(0,1,0),
            vz,
            'XZY'
        )
        
        dim_shape = Part.makeCompound(
            [left_arrow,
            txt,
            right_arrow,
            line1,
            line2,
            ext_line1,
            ext_line2
            ])
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
        dim_text_shape = self.make_dim_text_shape(fpo, dim_value, prefix=dim_prefix)
        bb = dim_text_shape.BoundBox
        if 90 < fpo.Angle < 270:
            x = l4.Vertexes[1].Point.x - bb.XLength - 10
            y = l4.Vertexes[1].Point.y - bb.YLength / 2
            z = 0.0
        else:
            x = l4.Vertexes[1].Point.x
            y = l4.Vertexes[1].Point.y - bb.YLength / 2
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
        bb_x_length = dim_text_shape.BoundBox.XLength
        bb_y_length = dim_text_shape.BoundBox.YLength
        arc_p = Part.makeCircle(abs(fpo.Offset.Value)+abs(fpo.TextOffset.Value), V(0,0,0), V(0,0,1), 0.0, angle)
        arc_mid_point = arc_p.valueAt(arc_p.Curve.parameterAtDistance(arc_p.Length/2, arc_p.FirstParameter))
        dim_text_cog = V(arc_mid_point.x-bb_x_length/2, arc_mid_point.y-bb_y_length/2, 0.0)
        dim_text_shape.translate(dim_text_cog)

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
            c = 0
            x = 0
            mini = 0
            for ref in references:
                ref.projectToPlane(references[0], V(0, 1, 0))
                ref.projectToPlane(references[0], V(0, 0, 1))
                if ref.x <= x:
                    mini = c
                    x = ref.x
                c += 1
            mini = references.pop(mini)
            references.insert(0, mini)
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
                txt.translate(line.Vertexes[1].Point.add(V(-txt.BoundBox.XMin/2, 0, txt.BoundBox.ZMin)))
                comp.append(txt)
                c += 1

            shape = Part.makeCompound(comp)
            fpo.Shape = shape
            fpo.Placement = App.Placement()
            fpo.recompute()
        elif fpo.Mode == "ChainY":
            c = 0
            x = 0
            mini = 0
            for ref in references:
                ref.projectToPlane(references[0], V(1, 0, 0))
                ref.projectToPlane(references[0], V(0, 0, 1))
                if ref.y <= x:
                    mini = c
                    x = ref.y
                c += 1
            mini = references.pop(mini)
            references.insert(0, mini)
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
            c = 0
            x = 0
            maxi = 0
            for ref in references:
                ref.projectToPlane(references[0], V(1, 0, 0))
                ref.projectToPlane(references[0], V(0, 1, 0))
                if ref.z >= x:
                    maxi = c
                    x = ref.z
                c += 1
            maxi = references.pop(maxi)
            references.insert(0, maxi)
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
                txt.translate(line.Vertexes[1].Point.add(V(-txt.BoundBox.XLength-5, 0, -txt.BoundBox.ZLength/2)))
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
        elif main_dir_axis == "Z":
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
        dim_shape.Placement.Rotation = App.Rotation(
            vx,
            V(0,1,0),
            vz,
            'XZY'
        )

        # make portion arcs
        _circle = Part.makeCircle(dim_shape.BoundBox.DiagonalLength/2, dim_shape.BoundBox.Center, vz)
        _intersection = DraftGeomUtils.findIntersection(circle, _circle)
        arc_start_pt2 = _intersection[DraftGeomUtils.findClosest(startpoint, _intersection)]
        arc_end_pt2 = _intersection[DraftGeomUtils.findClosest(endpoint, _intersection)]
        arc_start = DraftGeomUtils.arcFrom2Pts(arc_start_pt1, arc_start_pt2, center)
        arc_end = DraftGeomUtils.arcFrom2Pts(arc_end_pt1, arc_end_pt2, center)
        shape = Part.makeCompound([arrow, arrow2, dim_shape, ext_line1, ext_line2, arc_start, arc_end])
        fpo.Shape = shape
        fpo.Placement = App.Placement()
        fpo.recompute()

    def get_references_data(self, fpo) -> dict:
        """
        Extract geometric references from dimension feature object.
        
        Processes ReferencePointsList and ReferenceShapesList to collect all
        vertices, edges, and faces, returning reference objects with counters.
        
        Sub-shapes are resolved in global coordinates: when a referenced
        object lives inside a container with a placement (e.g. App::Part, or
        nested App::Part containers), the ancestor placement chain is applied
        via getGlobalPlacement() so the dimension is built at the geometry's
        actual position in the document.

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
            if 'PartDesign' in obj.TypeId:
                if obj.TypeId == 'PartDesign::Body':
                    body = obj
                else:
                    body = obj.getParent()
                body_to_global = None
                if hasattr(body, "getGlobalPlacement") and body.getGlobalPlacement() != body.Placement:
                    body_to_global = body.getGlobalPlacement().Matrix
                for sub_name in sub_names:
                    if body_to_global is not None:
                        sub_shape = Part.getShape(
                            body,
                            obj.Name + '.' + sub_name,
                            needSubElement=True,
                            mat=body_to_global,
                            transform=False,
                        )
                    else:
                        sub_shape = Part.getShape(body, obj.Name + '.' + sub_name, needSubElement=True)
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
            else:
                obj_to_global = None
                if hasattr(obj, "getGlobalPlacement") and obj.getGlobalPlacement() != obj.Placement:
                    obj_to_global = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).Matrix
                for sub_name in sub_names:
                    if obj_to_global is not None:
                        sub_shape = obj.getSubObject(sub_name, matrix=obj_to_global)
                    else:
                        sub_shape = obj.getSubObject(sub_name)
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
    
    def make_dim_text_shape(self, fpo, value, prefix=None, suffix=None, unit=None, tol_sup=None, tol_inf=None):
        dim_text = ''
        if prefix:
            dim_text += prefix
        dim_text += format(value, 'g')
        if unit:
            dim_text += '{}'.format(unit)
        if suffix:
            dim_text += suffix
        wire_string_dim_text = Part.makeWireString(
            dim_text,
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
        dim_text_shape = Part.makeCompound([s.removeShape(s.Edges[-1]) for s in dim_text_wires])
        return dim_text_shape
    
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
            App.Console.PrintWarning("Utils:    get_main_direction return an arbritary X direction.\n")
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
        proxy = cls(obj)

        # Manage Gui (ViewProvider) if available
        if App.GuiUp and hasattr(obj, "ViewObject"):
            from .dimension_vp import DimensionViewProvider
            DimensionViewProvider(obj.ViewObject)

        obj.recompute()
        return obj
