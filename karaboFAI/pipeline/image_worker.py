"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Pipeline scheduler.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from .worker import ProcessWorker
from .pipe import KaraboBridge, MpOutQueue
from .processors import (
    AzimuthalIntegrationProcessorPulse, PrePulseFilterProcessor,
    PostPulseFilterProcessor, ImageAssemblerFactory,
    ImageProcessorPulse, ImageProcessorTrain, RoiProcessorPulse,
    XgmProcessor
)
from ..config import config


class ImageWorker(ProcessWorker):
    """Pipeline scheduler."""
    def __init__(self):
        """Initialization."""
        super().__init__('image_worker')

        self._inputs = [KaraboBridge(f"{self._name}:input")]
        self._output = MpOutQueue(f"{self._name}:output")

        self._xgm_proc = XgmProcessor()
        self._assembler = ImageAssemblerFactory.create(config['DETECTOR'])
        self._image_proc_pulse = ImageProcessorPulse()
        self._roi_proc = RoiProcessorPulse()
        self._ai_proc = AzimuthalIntegrationProcessorPulse()
        # FIXME: move '_prepf_proc' before '_assembler'
        self._prepf_proc = PrePulseFilterProcessor()
        self._postpf_proc = PostPulseFilterProcessor()
        self._image_proc_train = ImageProcessorTrain()

        self._tasks = [
            self._xgm_proc,
            self._prepf_proc,
            self._assembler,
            self._image_proc_pulse,
            self._roi_proc,
            self._ai_proc,
            self._postpf_proc,
            self._image_proc_train,
        ]
