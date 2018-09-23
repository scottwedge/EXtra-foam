"""
Offline and online data analysis tool for Azimuthal integration at
FXE instrument, European XFEL.

Plot widgets module.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import abc
from collections import deque

import numpy as np

from .pyqtgraph.Qt import QtCore, QtGui
from .pyqtgraph import (
    BarGraphItem, ColorMap, GraphicsLayoutWidget, ImageItem, intColor,
    LinearRegionItem, mkBrush, mkPen, ScatterPlotItem, SpinBox,
)
from .pyqtgraph.graphicsItems.GradientEditorItem import Gradients
from .pyqtgraph import parametertree as ptree
from .pyqtgraph.parametertree import Parameter, ParameterTree

from .config import Config as cfg
from .data_processing import array2image, integrate_curve, sub_array_with_range


COLOR_MAP = ColorMap(*zip(*Gradients["thermal"]["ticks"]))


class Pen:
    _w = 3
    red = mkPen((255, 0, 0), width=_w)
    green = mkPen((0, 255, 0), width=_w)
    blue = mkPen((0, 0, 255), width=_w)
    cyan = mkPen((0, 255, 255), width=_w)
    purple = mkPen((255, 0, 255), width=_w)
    yellow = mkPen((255, 255, 0), width=_w)


class MainGuiLinePlotWidget(GraphicsLayoutWidget):
    def __init__(self, parent=None, **kwargs):
        """Initialization."""
        super().__init__(parent, **kwargs)

        w = cfg.MAIN_WINDOW_WIDTH - cfg.MAIN_LINE_PLOT_HEIGHT - 25
        h = cfg.MAIN_LINE_PLOT_HEIGHT
        self.setFixedSize(w, h)

        self._plot = self.addPlot()
        self._plot.setTitle("")
        self._plot.setLabel('bottom', "Momentum transfer (1/A)")
        self._plot.setLabel('left', "Scattering signal (arb. u.)")

    def clear_(self):
        self._plot.clear()

    def update(self, data):
        momentum = data.momentum
        for i, intensity in enumerate(data.intensity):
            self._plot.plot(momentum, intensity,
                            pen=mkPen(intColor(i, hues=9, values=5), width=2))
        self._plot.setTitle("Train ID: {}, number of pulses: {}".
                            format(data.tid, len(data.intensity)))


class MainGuiImageViewWidget(GraphicsLayoutWidget):
    def __init__(self, parent=None, **kwargs):
        """Initialization."""
        super().__init__(parent, **kwargs)

        self.setFixedSize(cfg.MAIN_LINE_PLOT_HEIGHT, cfg.MAIN_LINE_PLOT_HEIGHT)

        self._img = ImageItem(border='w')
        self._img.setLookupTable(COLOR_MAP.getLookupTable())

        self._view = self.addViewBox(lockAspect=True)
        self._view.addItem(self._img)

    def clear_(self):
        self._img.clear()

    def update(self, data):
        self._img.setImage(np.flip(data.image_mean, axis=0), autoLevels=False)
        self._view.autoRange()


class PlotWindow(QtGui.QMainWindow):
    """Base class for various pop-out plot windows."""
    def __init__(self, window_id, parent=None):
        """Initialization."""
        super().__init__(parent=parent)

        self.setWindowTitle("FXE Azimuthal integration")
        self._id = window_id
        self._cw = QtGui.QWidget()
        self.setCentralWidget(self._cw)

        self._gl_widget = GraphicsLayoutWidget()

        self._plot_items = []  # bookkeeping PlotItem objects
        self._image_items = []  # bookkeeping ImageItem objects

    @abc.abstractmethod
    def initUI(self):
        raise NotImplementedError

    @abc.abstractmethod
    def initCtrlUI(self):
        pass

    @abc.abstractmethod
    def initPlotUI(self):
        pass

    @abc.abstractmethod
    def update(self, data):
        """Update plots"""
        raise NotImplementedError

    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        # avoid memory leak
        self.parent().remove_window(self._id)

    def clear(self):
        """Clear all plots in the window."""
        for item in self._plot_items:
            item.clear()
        for item in self._image_items:
            item.clear()


class IndividualPulseWindow(PlotWindow):
    plot_w = 800
    plot_h = 280
    max_plots = 4

    def __init__(self, window_id, pulse_ids, *, parent=None, show_image=False):
        """Initialization."""
        super().__init__(window_id, parent=parent)

        self._pulse_ids = pulse_ids
        self._show_image = show_image

        self.initUI()

    def initUI(self):
        layout = self._gl_widget.ci.layout
        layout.setColumnStretchFactor(0, 1)
        if self._show_image:
            layout.setColumnStretchFactor(1, 3)
        w = self.plot_w - self.plot_h + self._show_image*(self.plot_h - 20)
        h = min(self.max_plots, len(self._pulse_ids))*self.plot_h
        self._gl_widget.setFixedSize(w, h)

        count = 0
        for pulse_id in self._pulse_ids:
            count += 1
            if count > self.max_plots:
                break
            if self._show_image is True:
                img = ImageItem(border='w')
                img.setLookupTable(COLOR_MAP.getLookupTable())
                self._image_items.append(img)

                vb = self._gl_widget.addViewBox(lockAspect=True)
                vb.addItem(img)

                line = self._gl_widget.addPlot()
            else:
                line = self._gl_widget.addPlot()

            line.setTitle("Pulse ID {:04d}".format(pulse_id))
            line.setLabel('left', "Scattering signal (arb. u.)")
            if pulse_id == self._pulse_ids[-1]:
                # all plots share one x label
                line.setLabel('bottom', "Momentum transfer (1/A)")
            else:
                line.setLabel('bottom', '')

            self._plot_items.append(line)
            self._gl_widget.nextRow()

        layout = QtGui.QHBoxLayout()
        layout.addWidget(self._gl_widget)
        self._cw.setLayout(layout)

    def update(self, data):
        for i, pulse_id in enumerate(self._pulse_ids):
            p = self._plot_items[i]
            if i == 0:
                p.addLegend(offset=(-40, 20))

            if data is not None:
                p.plot(data.momentum, data.intensity[pulse_id],
                       name="origin",
                       pen=Pen.purple)

                p.plot(data.momentum, data.intensity_mean,
                       name="mean",
                       pen=Pen.green)

                p.plot(data.momentum,
                       data.intensity[pulse_id] - data.intensity_mean,
                       name="difference",
                       pen=Pen.yellow)

            if data is not None and self._show_image is True:
                self._image_items[i].setImage(
                    array2image(np.flip(data.image[pulse_id], axis=0)),
                    autoLevels=False)


class LaserOnOffWindow(PlotWindow):
    plot_w = 800
    plot_h = 450

    modes = ["Laser on/off in the same train",
             "Laser on/off in even/odd train",
             "Laser on/off in odd/even train"]

    def __init__(self,
                 window_id,
                 on_pulse_ids,
                 off_pulse_ids,
                 normalization_range,
                 fom_range, *,
                 ma_window_size=9999,
                 parent=None):
        """Initialization."""
        super().__init__(window_id, parent=parent)

        self._ptree = ptree.ParameterTree(showHeader=True)
        params = [
            {'name': 'Experimental setups', 'type': 'group',
             'children': [
                {'name': 'Operation mode', 'type': 'list',
                 'values': self.modes,
                 'value': self.modes[0]},
                {'name': 'On-pulse IDs', 'type': 'str', 'readonly': True,
                 'value': ', '.join([str(x) for x in on_pulse_ids])},
                {'name': 'Off-pulse IDs', 'type': 'str', 'readonly': True,
                 'value': ', '.join([str(x) for x in  off_pulse_ids])}]},
            {'name': 'Data processing parameters', 'type': 'group',
             'children': [
                 {'name': 'Normalization range', 'type': 'str', 'readonly': True,
                  'value': ', '.join([str(x) for x in normalization_range])},
                 {'name': 'FOM range', 'type': 'str', 'readonly': True,
                  'value': ', '.join([str(x) for x in fom_range])},
                 {'name': 'MA window size', 'type': 'int', 'readonly': True,
                  'value': ma_window_size}]},
            {'name': 'Visualization options', 'type': 'group',
             'children': [
                 {'name': 'Difference scale', 'type': 'int', 'value': 20},
                 {'name': 'Show normalization range', 'type': 'bool', 'value': False},
                 {'name': 'Show FOM range', 'type': 'bool', 'value': False}]},
            {'name': 'Actions', 'type': 'group',
             'children': [
                {'name': 'Clear history', 'type': 'action'}]},
        ]
        p = Parameter.create(name='params', type='group', children=params)
        self._ptree.setParameters(p, showTop=False)

        self._exp_setups = p.param('Experimental setups')
        self._exp_setups.param('Operation mode').sigValueChanged.connect(self._reset)

        self._vis_setups = p.param('Visualization options')

        self._proc_setups = p.param('Data processing parameters')

        p.param('Actions', 'Clear history').sigActivated.connect(self._reset)

        self._count = 0  # The number of trains received

        # A flag which indicates a laser-on train has been received
        # in the modes "Laser on/off in even/odd train" and
        # "Laser on/off in odd/even train"
        self._on_train_received = False

        # The moving average of on/off pulses
        self._on_pulses_ma = None
        self._off_pulses_ma = None

        # The histories of on/off pulses by train, which are used in
        # calculating moving average (MA)
        self._on_pulses_hist = deque()
        self._off_pulses_hist = deque()

        # The history of integrated difference (FOM) between on and off pulses
        self._fom_hist_train_id = []
        self._fom_hist = []

        # an indicator of normalization range
        pen1 = mkPen(QtGui.QColor(
            255, 255, 255, 255), width=1, style=QtCore.Qt.DashLine)
        brush1 = QtGui.QBrush(QtGui.QColor(0, 0, 255, 30))
        self._normalization_range_lri = LinearRegionItem(
            normalization_range, pen=pen1, brush=brush1, movable=False)

        # an indicator of FOM range
        pen2 = mkPen(QtGui.QColor(
            255, 0, 0, 255), width=1, style=QtCore.Qt.DashLine)
        brush2 = QtGui.QBrush(QtGui.QColor(0, 0, 255, 30))
        self._fom_range_lri = LinearRegionItem(
            fom_range, pen=pen2, brush=brush2, movable=False)

        self.initUI()

    def initUI(self):
        control_widget = self.initCtrlUI()
        self.initPlotUI()

        layout = QtGui.QHBoxLayout()
        layout.addWidget(control_widget)
        layout.addWidget(self._gl_widget)
        self._cw.setLayout(layout)

    def initPlotUI(self):
        self._gl_widget.setFixedSize(self.plot_w, 2*self.plot_h)

        p1 = self._gl_widget.addPlot()
        self._plot_items.append(p1)
        p1.setLabel('left', "Scattering signal (arb. u.)")
        p1.setLabel('bottom', "Momentum transfer (1/A)")
        p1.setTitle(' ')

        self._gl_widget.nextRow()

        p2 = self._gl_widget.addPlot()
        self._plot_items.append(p2)
        p2.setLabel('left', "Integrated difference (arb.)")
        p2.setLabel('bottom', "Train ID")
        p2.setTitle(' ')

    def initCtrlUI(self):
        control_widget = QtGui.QWidget()
        control_widget.setMinimumWidth(450)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self._ptree)
        control_widget.setLayout(layout)

        return control_widget

    def update(self, data):
        # TODO: think it twice about how to deal with None data here
        update_plots = False
        mode = self._exp_setups.param('Operation mode').value()
        if mode == self.modes[0]:
            update_plots = True
        else:
            if mode == self.modes[1]:
                flag = 0  # on-train has even train ID
            else:
                flag = 1  # on-train has odd train ID

            # the evolution of FOM is updated if an on-train is
            # followed by an off-train
            if self._on_train_received is True and data.tid % 2 == 1 ^ flag:
                update_plots = True

            if data.tid % 2 == flag:
                self._on_train_received = True
            else:
                self._on_train_received = False

        # retrieve parameters

        on_pulse_ids = self._exp_setups.param('On-pulse IDs').value()
        on_pulse_ids = [int(s) for s in on_pulse_ids.split(',')]
        off_pulse_ids = self._exp_setups.param('Off-pulse IDs').value()
        off_pulse_ids = [int(s) for s in off_pulse_ids.split(',')]

        normalization_range = self._proc_setups.param('Normalization range').value()
        normalization_range = [float(s) for s in normalization_range.split(',')]
        fom_range = self._proc_setups.param('FOM range').value()
        fom_range = [float(s) for s in fom_range.split(',')]
        ma_window_size = self._proc_setups.param('MA window size').value()

        diff_scale = self._vis_setups.param('Difference scale').value()

        self._count += 1

        momentum = data.momentum

        # calculate average over on/off pulses respectively
        this_on_pulses = data.intensity[on_pulse_ids].mean(axis=0)
        this_off_pulses = data.intensity[off_pulse_ids].mean(axis=0)

        # update history
        self._on_pulses_hist.append(this_on_pulses)
        self._off_pulses_hist.append(this_off_pulses)

        if self._count == 1:
            # the first data point
            self._on_pulses_ma = this_on_pulses
            self._off_pulses_ma = this_off_pulses
        else:
            # apply moving average
            self._on_pulses_ma += this_on_pulses / self._count \
                                  - self._on_pulses_ma / (self._count - 1)
            self._off_pulses_ma += this_off_pulses / self._count \
                                   - self._off_pulses_ma / (self._count - 1)

            if len(self._on_pulses_hist) > ma_window_size:
                self._on_pulses_ma -= \
                    self._on_pulses_hist.popleft() / ma_window_size
                self._off_pulses_ma -= \
                    self._off_pulses_hist.popleft() / ma_window_size

        # normalize azimuthal integration curves
        normalized_on_pulse = self._on_pulses_ma / integrate_curve(
            self._on_pulses_ma, momentum, normalization_range)
        normalized_off_pulse = self._off_pulses_ma / integrate_curve(
            self._off_pulses_ma, momentum, normalization_range)

        # then calculate the difference between on- and off pulse curves
        diff = normalized_on_pulse - normalized_off_pulse

        # ------------
        # update plots
        # ------------

        # plot on/off pulses and their difference (upper plot)
        p = self._plot_items[0]
        p.addLegend(offset=(-60, 20))
        p.plot(momentum, normalized_on_pulse, name="On", pen=Pen.purple)
        p.plot(momentum, normalized_off_pulse, name="Off", pen=Pen.green)
        p.plot(momentum, diff_scale * diff, name="difference", pen=Pen.yellow)

        # add normalization/FOM range if requested
        if self._vis_setups.param("Show normalization range").value():
            p.addItem(self._normalization_range_lri)
        if self._vis_setups.param("Show FOM range").value():
            p.addItem(self._fom_range_lri)

        # plot the evolution of fom (lower plot)
        if update_plots:
            # calculate figure-of-merit (FOM) and update history
            fom = sub_array_with_range(diff, momentum, fom_range)[0]
            self._fom_hist.append(np.sum(np.abs(fom)))
            self._fom_hist_train_id.append(data.tid)

            s = ScatterPlotItem(size=20, pen=mkPen(None),
                                brush=mkBrush(120, 255, 255, 255))
            s.addPoints([{'pos': (i, v), 'data': 1} for i, v in
                         zip(self._fom_hist_train_id, self._fom_hist)])

            p = self._plot_items[1]
            p.clear()
            p.addItem(s)
            p.plot(self._fom_hist_train_id, self._fom_hist, pen=Pen.yellow)

    def clear(self):
        """Overload.

        The history of FOM should be untouched when the new data is invalid.
        """
        self._plot_items[0].clear()

    def mode_selected(self):
        pass

    def _reset(self):
        for p in self._plot_items:
            p.clear()

        self._count = 0
        self._on_train_received = False
        self._on_pulses_ma = None
        self._off_pulses_ma = None
        self._on_pulses_hist.clear()
        self._off_pulses_hist.clear()
        self._fom_hist.clear()
        self._fom_hist_train_id.clear()


class SanityCheckWindow(PlotWindow):
    plot_w = 800
    plot_h = 450

    def __init__(self, window_id, normalization_range, fom_range, *,
                 parent=None):
        """Initialization."""
        super().__init__(window_id, parent=parent)

        self._normalization_range = normalization_range
        self._fom_range = fom_range

        self.initUI()

    def initUI(self):
        self.initPlotUI()

        layout = QtGui.QHBoxLayout()
        layout.addWidget(self._gl_widget)
        self._cw.setLayout(layout)

    def initPlotUI(self):
        self._gl_widget.setFixedSize(self.plot_w, self.plot_h)

        self._gl_widget.nextRow()

        p = self._gl_widget.addPlot()
        self._plot_items.append(p)
        p.setLabel('left', "Integrated difference (arb.)")
        p.setLabel('bottom', "Pulse ID")
        p.setTitle(' ')

    def update(self, data):
        """Override."""
        momentum = data.momentum

        # normalize azimuthal integration curves for each pulse
        normalized_pulse_intensities = []
        for pulse_intensity in data.intensity:
            normalized = pulse_intensity / integrate_curve(
                pulse_intensity, momentum, self._normalization_range)
            normalized_pulse_intensities.append(normalized)

        # calculate the different between each pulse and the first one
        diffs = [p - normalized_pulse_intensities[0]
                 for p in normalized_pulse_intensities]

        # calculate the FOM for each pulse
        foms = []
        for diff in diffs:
            fom = sub_array_with_range(diff, momentum, self._fom_range)[0]
            foms.append(np.sum(np.abs(fom)))

        bar = BarGraphItem(x=range(len(foms)), height=foms, width=0.6, brush='b')

        p = self._plot_items[0]
        p.addItem(bar)
        p.setTitle("Train ID: {}".format(data.tid))
        p.plot()
