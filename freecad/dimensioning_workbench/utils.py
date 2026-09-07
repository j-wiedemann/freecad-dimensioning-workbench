# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Utils for dimensioning workbench
"""

import FreeCAD as App
import Part
import DraftGeomUtils

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
        App.Console.PrintWarning("Utils:    get_main_direction return an arbritary X direction.\n")
        return "X"