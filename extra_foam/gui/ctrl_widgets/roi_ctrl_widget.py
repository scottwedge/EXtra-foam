"""
Distributed under the terms of the BSD 3-Clause License.

The full license is in the file LICENSE, distributed with this software.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget
)

from ..mediator import Mediator
from ..plot_widgets.plot_items import RectROI
from ..ctrl_widgets import _AbstractCtrlWidget, SmartLineEdit
from ..misc_widgets import FColor
from ...config import config
from ...pipeline.data_model import RectRoiGeom


class _SingleRoiCtrlWidget(QWidget):
    """_SingleRoiCtrlWidget class.

    Widget which controls a single ROI.
    """
    # (idx, x, y, w, h) where idx starts from 1
    roi_geometry_change_sgn = pyqtSignal(object)

    _pos_validator = QIntValidator(-10000, 10000)
    _size_validator = QIntValidator(1, 10000)

    INVALID_GEOM = RectRoiGeom.INVALID

    def __init__(self, roi: RectROI, *, parent=None):
        super().__init__(parent=parent)
        self._roi = roi

        self._activate_cb = QCheckBox("On")
        self._lock_cb = QCheckBox("Lock")

        self._width_le = SmartLineEdit()
        self._width_le.setValidator(self._size_validator)
        self._height_le = SmartLineEdit()
        self._height_le.setValidator(self._size_validator)
        self._px_le = SmartLineEdit()
        self._px_le.setValidator(self._pos_validator)
        self._py_le = SmartLineEdit()
        self._py_le.setValidator(self._pos_validator)

        self._line_edits = (self._width_le, self._height_le,
                            self._px_le, self._py_le)

        self.initUI()
        self.initConnections()

        self.disableAllEdit()

    def initUI(self):
        layout = QHBoxLayout()
        idx = self._roi.index

        label = QLabel(f"ROI{idx}: ")
        palette = label.palette()
        palette.setColor(palette.WindowText,
                         FColor.mkColor(config['GUI_ROI_COLORS'][idx-1]))
        label.setPalette(palette)
        layout.addWidget(label)

        layout.addWidget(self._activate_cb)
        layout.addWidget(self._lock_cb)
        layout.addWidget(QLabel("w: "))
        layout.addWidget(self._width_le)
        layout.addWidget(QLabel("h: "))
        layout.addWidget(self._height_le)
        layout.addWidget(QLabel("x: "))
        layout.addWidget(self._px_le)
        layout.addWidget(QLabel("y: "))
        layout.addWidget(self._py_le)

        self.setLayout(layout)
        # left, top, right, bottom
        self.layout().setContentsMargins(2, 1, 2, 1)

    def initConnections(self):
        self._width_le.value_changed_sgn.connect(self.onRoiSizeEdited)
        self._height_le.value_changed_sgn.connect(self.onRoiSizeEdited)
        self._px_le.value_changed_sgn.connect(self.onRoiPositionEdited)
        self._py_le.value_changed_sgn.connect(self.onRoiPositionEdited)

        self._roi.sigRegionChangeFinished.connect(
            self.onRoiGeometryChangeFinished)

        self._activate_cb.stateChanged.connect(self.onToggleRoiActivation)
        self._activate_cb.stateChanged.emit(self._activate_cb.checkState())
        self._lock_cb.stateChanged.connect(self.onLock)

    @pyqtSlot(int)
    def onToggleRoiActivation(self, state):
        if state == Qt.Checked:
            self._roi.show()
            self.enableAllEdit()
            x, y = [int(v) for v in self._roi.pos()]
            w, h = [int(v) for v in self._roi.size()]
        else:
            self._roi.hide()
            self.disableAllEdit()
            x, y, w, h = self.INVALID_GEOM

        self.roi_geometry_change_sgn.emit((self._roi.index, x, y, w, h))

    @pyqtSlot(object)
    def onRoiPositionEdited(self, value):
        x, y = [int(v) for v in self._roi.pos()]
        w, h = [int(v) for v in self._roi.size()]

        if self.sender() == self._px_le:
            x = int(self._px_le.text())
        elif self.sender() == self._py_le:
            y = int(self._py_le.text())

        # If 'update' == False, the state change will be remembered
        # but not processed and no signals will be emitted.
        self._roi.setPos((x, y), update=False)
        # trigger sigRegionChanged which moves the handler(s)
        # finish=False -> sigRegionChangeFinished will not emit, which
        # otherwise triggers infinite recursion
        self._roi.stateChanged(finish=False)

        if not self._activate_cb.isChecked():
            x, y, w, h = self.INVALID_GEOM

        self.roi_geometry_change_sgn.emit((self._roi.index, x, y, w, h))

    @pyqtSlot(object)
    def onRoiSizeEdited(self, value):
        x, y = [int(v) for v in self._roi.pos()]
        w, h = [int(v) for v in self._roi.size()]
        if self.sender() == self._width_le:
            w = int(self._width_le.text())
        elif self.sender() == self._height_le:
            h = int(self._height_le.text())

        # If 'update' == False, the state change will be remembered
        # but not processed and no signals will be emitted.
        self._roi.setSize((w, h), update=False)
        # trigger sigRegionChanged which moves the handler(s)
        # finish=False -> sigRegionChangeFinished will not emit, which
        # otherwise triggers infinite recursion
        self._roi.stateChanged(finish=False)

        if not self._activate_cb.isChecked():
            x, y, w, h = self.INVALID_GEOM

        self.roi_geometry_change_sgn.emit((self._roi.index, x, y, w, h))

    @pyqtSlot(object)
    def onRoiGeometryChangeFinished(self, roi):
        """Connect to the signal from an ROI object."""
        x, y = [int(v) for v in roi.pos()]
        w, h = [int(v) for v in roi.size()]
        self.updateParameters(x, y, w, h)
        # inform widgets outside this window

        if not self._activate_cb.isChecked():
            x, y, w, h = self.INVALID_GEOM

        self.roi_geometry_change_sgn.emit((roi.index, x, y, w, h))

    def notifyRoiParams(self):
        # fill the QLineEdit(s) and Redis
        self._roi.sigRegionChangeFinished.emit(self._roi)

    def updateParameters(self, x, y, w, h):
        self.roi_geometry_change_sgn.disconnect()
        self._px_le.setText(str(x))
        self._py_le.setText(str(y))
        self._width_le.setText(str(w))
        self._height_le.setText(str(h))
        self.roi_geometry_change_sgn.connect(Mediator().onRoiGeometryChange)

    def setEditable(self, editable):
        for w in self._line_edits:
            w.setDisabled(not editable)

    @pyqtSlot(int)
    def onLock(self, state):
        self._roi.setLocked(state == Qt.Checked)
        self.setEditable(not state == Qt.Checked)

    def disableAllEdit(self):
        self.setEditable(False)
        self._lock_cb.setDisabled(True)

    def enableAllEdit(self):
        self._lock_cb.setDisabled(False)
        self.setEditable(True)


class RoiCtrlWidget(_AbstractCtrlWidget):
    """Widget for controlling all the ROIs in the ImageToolWindow."""

    def __init__(self, rois, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._roi_ctrls = []
        for roi in rois:
            widget = _SingleRoiCtrlWidget(roi)
            self._roi_ctrls.append(widget)

        self.initUI()
        self.initConnections()

    def initUI(self):
        """Override."""
        layout = QVBoxLayout()
        for i, roi_ctrl in enumerate(self._roi_ctrls):
            layout.addWidget(roi_ctrl)
        self.setLayout(layout)

    def initConnections(self):
        """Override."""
        mediator = self._mediator

        for widget in self._roi_ctrls:
            widget.roi_geometry_change_sgn.connect(
                mediator.onRoiGeometryChange)

    def updateMetaData(self):
        """Override."""
        for i, widget in enumerate(self._roi_ctrls, 1):
            widget.notifyRoiParams()
        return True
