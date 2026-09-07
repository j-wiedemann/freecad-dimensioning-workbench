# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Snapper for dimensioning workbench
"""

import pivy.coin as coin
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui
import Draft
from draftutils import gui_utils
import draftguitools.gui_trackers as trackers


class getPoint:
    def __init__(self, last=None, callback=None, movecallback=None, mode="line") -> None:
        if not last:
            mode = "point"
        print("Snapper:    init snap with {} mode".format(mode.upper()))
        self.last = last
        self.mode = mode
        self.callback = callback
        self.movecallback = movecallback
        self.view = Draft.get3DView()
        self.pt = None
        self.callbackClick = self.view.addEventCallbackPivy(coin.SoMouseButtonEvent.getClassTypeId(), self.click)
        self.callbackMove = self.view.addEventCallbackPivy(coin.SoLocation2Event.getClassTypeId(), self.move)
        self.linetrack = None
        self.rectangletrack = None
        if self.last and self.mode == "line":
            self.linetrack = trackers.lineTracker()
            self.linetrack.on()
            self.linetrack.p1(self.last)
        elif self.last and self.mode == "rect":
            self.rectangletrack = trackers.rectangleTracker()
            self.rectangletrack.on()
            self.rectangletrack.setPlane(App.Vector(1,0,0),App.Vector(0,1,0))
            self.rectangletrack.p1(self.last)

    def accept(self) -> None:
        if self.callback:
            self.callback(self.pt)
        self.pt = None
        self.finalize()
        print("Snapper:    finalize snapper on ACCEPT")
        
    def cancel(self) -> None:
        self.finalize()
        print("Snapper:    finalize snapper on CANCEL")

    def finalize(self) -> None:
        try:
            if self.callbackClick:
                self.view.removeEventCallbackPivy(coin.SoMouseButtonEvent.getClassTypeId(), self.callbackClick)
            if self.callbackMove:
                self.view.removeEventCallbackPivy(coin.SoLocation2Event.getClassTypeId(), self.callbackMove)
            if self.callbackClick or self.callbackMove:
                gui_utils.end_all_events()
        except RuntimeError:
            # the view has been deleted already
            print("Snapper:    Error when trying to remove Pivy Callbacks")
            pass
        self.callbackClick = None
        self.callbackMove = None
        if self.linetrack:
            self.linetrack.off()
            self.linetrack.finalize()
        if self.rectangletrack:
            self.rectangletrack.off()
            self.rectangletrack.finalize()
        Gui.Snapper.off()
    
    def click(self, event_cb) -> None:
        event = event_cb.getEvent()
        if event.getButton() == 1:
            if event.getState() == coin.SoMouseButtonEvent.DOWN:
                self.accept()
                
    def move(self, event_cb) -> None:
        event = event_cb.getEvent()
        mousepos = event.getPosition()
        ctrl = event.wasCtrlDown()
        shift = event.wasShiftDown()
        self.pt = Gui.Snapper.snap(mousepos, lastpoint=None, active=ctrl, constrain=shift)
        if self.linetrack:
            self.linetrack.p2(self.pt)
        if self.rectangletrack:
            self.rectangletrack.p3(self.pt)
        if self.movecallback:
            self.movecallback(self.pt)


class Snapper:
    def __init__(self, actioner, target, mode) -> None:
        """Create a snapper.
    
        Parameters
        ----------
        actioner : QtGui.QtWidget
            The widget that call this
        target : QtGui.QtWidget
            The widget where data will be send
        mode : snapper mode
            Could be init, point, length, axis
            
        Returns
        -------
        None
        """
        self.is_active = True
        self.actioner = actioner
        self.target = target
        self.mode = mode
        self.original_actioner_text = self.actioner.text()
        self.last = None
        if isinstance(self.target, QtGui.QTextEdit):
            self.original_target_value = self.target.getText()
        elif isinstance(self.target, QtGui.QDoubleSpinBox):
            self.original_target_value = self.target.value()
        self.snap = getPoint(movecallback=self.movecallback, callback=self.callback)

    def movecallback(self, vector=None) -> None:
        if not vector:
            return
        match self.mode:
            case "point":
                self.target.setText("{}, {}, {}".format(round(vector[0],2), round(vector[1],2), round(vector[2],2)))
            case "length":
                if self.last:
                    self.target.setValue((self.last-vector).Length)
            case "axis":
                if self.last:
                    axis = vector-self.last
                    if axis.Length >= App.Base.Precision.approximation():
                        axis = axis.normalize()
                        self.target.setText("{}, {}, {}".format(round(axis[0],2), round(axis[1],2), round(axis[2],2)))
                    
    def callback(self, vector=None) -> None:
        if not vector:
            return
        match self.mode:
            case "point":
                self.target.setText("{}, {}, {}".format(round(vector[0],2), round(vector[1],2), round(vector[2],2)))
                self.finalize()
            case "length":
                if self.last is None:
                    self.last = vector
                    self.snap = getPoint(self.last, movecallback=self.movecallback, callback=self.callback)
                else:
                    self.target.setValue((self.last-vector).Length)
                    self.finalize()
            case "axis":
                if self.last is None:
                    self.last = vector
                    self.snap = getPoint(self.last, movecallback=self.movecallback, callback=self.callback)
                else:
                    axis = vector-self.last
                    if axis.Length >= App.Base.Precision.approximation():
                        axis = axis.normalize()
                        self.target.setText("{}, {}, {}".format(round(axis[0],2), round(axis[1],2), round(axis[2],2)))
                    self.finalize()

    def finalize(self):
        self.is_active = False
        self.snap = None
        self.actioner.setText(self.original_actioner_text)

    def cancel(self):
        if self.snap:
            self.snap.cancel()
        self.set_target_backup_value()
        self.finalize()

    def set_target_backup_value(self):
        if isinstance(self.target, QtGui.QTextEdit):
            self.target.setText(self.original_target_value)
        elif isinstance(self.target, QtGui.QDoubleSpinBox):
            self.target.setValue(self.original_target_value)

        