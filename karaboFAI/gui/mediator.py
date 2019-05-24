"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Mediator class.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from enum import IntEnum
import json

from PyQt5.QtCore import pyqtSignal,  QObject

from ..metadata import Metadata as mt
from ..metadata import MetaProxy
from ..pipeline.data_model import DataManager
from ..config import CorrelationFom


class Mediator(QObject):
    """Mediator for GUI signal-slot connection."""

    start_file_server_sgn = pyqtSignal()
    stop_file_server_sgn = pyqtSignal()
    file_server_started_sgn = pyqtSignal()
    file_server_stopped_sgn = pyqtSignal()

    vip_pulse_id1_sgn = pyqtSignal(int)
    vip_pulse_id2_sgn = pyqtSignal(int)
    # tell the control widget to update VIP pulse IDs
    vip_pulse_ids_connected_sgn = pyqtSignal()

    reset_image_level_sgn = pyqtSignal()

    __instance = None

    def __new__(cls, *args, **kwargs):
        """Create a singleton."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls, *args, **kwargs)
            cls.__instance._is_initialized = False
        return cls.__instance

    def __init__(self, *args, **kwargs):
        if self._is_initialized:
            return
        # this will reset all signal-slot connections
        super().__init__(*args, **kwargs)

        self._meta = MetaProxy()
        self._data = DataManager()

        self._is_initialized = True

    def onBridgeEndpointChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "endpoint", value)

    def onDataFolderChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "data_folder", value)

    def onDetectorSourceNameChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "detector_source_name", value)

    def onMonoSourceNameChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "mono_source_name", value)

    def onXgmSourceNameChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "xgm_source_name", value)

    def onTimingSourceNameChange(self, value: str):
        self._meta.set(mt.DATA_SOURCE, "timing_source_name", value)

    def onSourceTypeChange(self, value: IntEnum):
        self._meta.set(mt.DATA_SOURCE, "source_type", int(value))

    def onImageThresholdMaskChange(self, value: tuple):
        self._meta.set(mt.IMAGE_PROC, "threshold_mask", str(value))

    def onImageMaWindowChange(self, value: int):
        self._meta.set(mt.IMAGE_PROC, "ma_window", value)

    def onImageBackgroundChange(self, value: float):
        self._meta.set(mt.IMAGE_PROC, "background", value)

    def onGeometryFileChange(self, value: str):
        self._meta.set(mt.GEOMETRY_PROC, "geometry_file", value)

    def onQuadPositionsChange(self, value: str):
        self._meta.set(mt.GEOMETRY_PROC, "quad_positions", json.dumps(value))

    def onSampleDistanceChange(self, value: float):
        self._meta.set(mt.GENERAL_PROC, 'sample_distance', value)

    def onPhotonEnergyChange(self, value: float):
        self._meta.set(mt.GENERAL_PROC, 'photon_energy', value)

    def onPulseIdRangeChange(self, value: tuple):
        self._meta.set(mt.GENERAL_PROC, 'pulse_id_range', str(value))

    def onAiIntegCenterXChange(self, value: int):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'integ_center_x', value)

    def onAiIntegCenterYChange(self, value: int):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'integ_center_y', value)

    def onAiIntegMethodChange(self, value: str):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'integ_method', value)

    def onAiIntegPointsChange(self, value: int):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'integ_points', value)

    def onAiIntegRangeChange(self, value: tuple):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'integ_range', str(value))

    def onAiNormalizerChange(self, value: IntEnum):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'normalizer', int(value))

    def onAiAucChangeChange(self, value: tuple):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'auc_range', str(value))

    def onAiFomIntegRangeChange(self, value: tuple):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'fom_integ_range', str(value))

    def onAiPulsedIntegStateChange(self, value: bool):
        self._meta.set(mt.AZIMUTHAL_INTEG_PROC, 'enable_pulsed_ai', str(value))

    def onPpModeChange(self, value: IntEnum):
        value = int(value)
        if self._meta.get(mt.PUMP_PROBE_PROC, 'mode') != value:
            self._data.reset_pp()
            if self._meta.get(mt.CORRELATION_PROC, 'fom_type') == \
                    int(CorrelationFom.PUMP_PROBE_FOM):
                self._data.reset_correlation()
        self._meta.set(mt.PUMP_PROBE_PROC, 'mode', value)

    def onPpOnPulseIdsChange(self, value: list):
        self._meta.set(mt.PUMP_PROBE_PROC, 'on_pulse_ids', str(value))

    def onPpOffPulseIdsChange(self, value: list):
        self._meta.set(mt.PUMP_PROBE_PROC, 'off_pulse_ids', str(value))

    def onPpAnalysisTypeChange(self, value: IntEnum):
        self._meta.set(mt.PUMP_PROBE_PROC, 'analysis_type', int(value))
        self._data.reset_pp()
        if self._meta.get(mt.CORRELATION_PROC, 'fom_type') == \
                int(CorrelationFom.PUMP_PROBE_FOM):
            self._data.reset_correlation()

    def onPpAbsDifferenceChange(self, value: bool):
        self._meta.set(mt.PUMP_PROBE_PROC, "abs_difference", str(value))

    def onPpMaWindowChange(self, value: int):
        self._meta.set(mt.PUMP_PROBE_PROC, "ma_window", value)

    def onPpReset(self):
        self._data.reset_pp()

    def onRoiRegionChange(self, value: tuple):
        rank, x, y, w, h = value
        self._meta.set(mt.ROI_PROC, f'region{rank}', str((x, y, w, h)))

    def onRoiVisibilityChange(self, value: tuple):
        rank, is_visible = value
        self._meta.set(mt.ROI_PROC, f'visibility{rank}', str(is_visible))

    def onRoiFomChange(self, value: IntEnum):
        self._meta.set(mt.ROI_PROC, 'fom_type', int(value))
        self._data.reset_roi()

    def onRoiReset(self):
        self._data.reset_roi()

    def onProj1dNormalizerChange(self, value: IntEnum):
        self._meta.set(mt.ROI_PROC, "proj1d:normalizer", int(value))

    def onProj1dAucRangeChange(self, value: tuple):
        self._meta.set(mt.ROI_PROC, "proj1d:auc_range", str(value))

    def onProj1dFomIntegRangeChange(self, value: tuple):
        self._meta.set(mt.ROI_PROC, "proj1d:fom_integ_range", str(value))

    def onCorrelationFomChange(self, value: IntEnum):
        self._meta.set(mt.CORRELATION_PROC, "fom_type", int(value))
        self._data.reset_correlation()

    def onCorrelationParamChange(self, value: tuple):
        # index, device ID, property name, resolution
        # index starts from 1
        index, device_id, ppt, resolution = value
        self._data.add_correlation(index, device_id, ppt, resolution)
        self._meta.set(mt.CORRELATION_PROC, f'device_id{index}', device_id)
        self._meta.set(mt.CORRELATION_PROC, f'property{index}', ppt)
        self._meta.set(mt.CORRELATION_PROC, f'resolution{index}', resolution)

    def onCorrelationReset(self):
        self._data.reset_correlation()

    def onXasEnergyBinsChange(self, value: int):
        self._meta.set(mt.XAS_PROC, "energy_bins", value)

    def onXasReset(self):
        self._data.reset_xas()

    def onBinningBinsChange(self, value: int):
        self._meta.set(mt.BINNING_PROC, "n_bins", value)

    def onBinningRangeChange(self, value: tuple):
        self._meta.set(mt.BINNING_PROC, "bin_range", str(value))

    def onBinningReset(self):
        self._data.reset_binning()

    def onBinningAnalysisTypeChange(self, value: IntEnum):
        self._meta.set(mt.BINNING_PROC, "analysis_type", int(value))
