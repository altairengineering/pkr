# Copyright© 1986-2024 Altair Engineering Inc.

import unittest

from pkr.utils import merge


class TestMerge(unittest.TestCase):
    """
    TestMerge tests the behavior of the merge function in pkr/utils.py.

    The current test set does not cover all possible behaviors of the merge
    function.
    """

    def test_none_source(self):
        source = None
        dest = {"key": "value"}
        result = merge(source, dest)
        self.assertEqual(result, dest)
        self.assertIsNone(source)

    def test_empty_source(self):
        source = {}
        dest = {"key": "value"}
        result = merge(source, dest)
        self.assertEqual(result, dest)

    def test_none_destination(self):
        source = {"key": "value"}
        dest = None
        result = merge(source, dest)
        self.assertEqual(result, source)
        self.assertIsNone(dest)

    def test_empty_destination(self):
        source = {"key": "value"}
        dest = {}
        result = merge(source, dest)
        self.assertEqual(result, source)

        # Mutate result, should also change dest
        result["test"] = 12
        self.assertIn("test", dest)
        self.assertEqual(dest["test"], 12)

    def test_simple_merge(self):
        source = {"key1": "value", "key2": "new value"}
        dest = {"key2": "old value", "key3": 9}
        result = merge(source, dest)

        # Result should include all unique keys and any duplicates should
        # have the value from source.
        self.assertEqual(
            result,
            {"key1": "value", "key2": "new value", "key3": 9},
        )
