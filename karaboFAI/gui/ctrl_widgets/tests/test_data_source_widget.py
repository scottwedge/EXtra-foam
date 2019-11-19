import unittest
from unittest.mock import patch
import time

from karaboFAI.logger import logger
from karaboFAI.gui import mkQApp
from karaboFAI.config import config
from karaboFAI.gui.ctrl_widgets.data_source_widget import DataSourceWidget
from karaboFAI.services import start_redis_server
from karaboFAI.processes import wait_until_redis_shutdown

app = mkQApp()

logger.setLevel("CRITICAL")


class TestDataSourceWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start_redis_server()

    @classmethod
    def tearDownClass(cls):
        wait_until_redis_shutdown()

    @patch.dict(config._data, {"DETECTOR": "DSSC", "TOPIC": "SCS", "SOURCES_EXPIRATION_TIME": 10})
    def testDataSourceList(self):
        widget = DataSourceWidget()
        model = widget._list_model
        proxy = widget._mon

        # test default
        widget.updateSourceList()
        self.assertListEqual([], model._sources)

        # test new sources
        proxy.set_available_sources({"abc": "1234567", "efg": "234567"})
        widget.updateSourceList()
        self.assertListEqual(["abc", "efg"], model._sources)

        # test old sources do not exist when new sources are set
        proxy.set_available_sources({"cba": "1234567", "gfe": "234567"})
        widget.updateSourceList()
        self.assertListEqual(["cba", "gfe"], model._sources)

        # test expiration
        time.sleep(0.020)
        widget.updateSourceList()
        self.assertListEqual([], model._sources)

    def testDataSourceTreeItem(self):
        pass

    def testDataSourceTreeModel(self):
        pass
