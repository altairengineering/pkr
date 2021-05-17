import unittest
from pkr import driver

class TestDriver(unittest.TestCase):
    def test_list_drivers(self):
        self.assertEqual(driver.list_drivers(), ('base', 'docker_compose', 'k8s', 'minikube'))

    def test_load_driver(self):
        self.assertEqual(repr(driver.load_driver('docker_compose')), "<class 'pkr.driver.docker_compose.Driver'>")

    def test_load_driver_by_alias(self):
        self.assertEqual(repr(driver.load_driver('compose')), "<class 'pkr.driver.docker_compose.Driver'>")