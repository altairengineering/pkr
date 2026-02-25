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

    def test_type_check(self):
        base = {"key": "value"}
        overload = None
        with self.assertRaises(TypeError):
            merge(base, overload, raise_on_type_mismatch=True)

    def test_empty_overload(self):
        base = {"key": "value"}
        overload = {}
        result = merge(base, overload)
        self.assertEqual(result, base)

        # Mutate result, should not change overload
        result["test"] = 12
        self.assertNotIn("test", overload)

    def test_simple_merge(self):
        base = {"key2": "old value", "key3": 9}
        overload = {"key1": "value", "key2": "new value"}
        result = merge(base, overload)

        # Result should include all unique keys and any duplicates should
        # have the value from source.
        self.assertEqual(
            result,
            {"key1": "value", "key2": "new value", "key3": 9},
        )
