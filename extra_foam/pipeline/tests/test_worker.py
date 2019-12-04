import unittest

from extra_foam.pipeline.worker import ProcessWorkerLogger


class TestProcessWorkerLogger(unittest.TestCase):
    def testSingleton(self):
        logger1 = ProcessWorkerLogger()
        logger2 = ProcessWorkerLogger()
        self.assertIs(logger1, logger2)