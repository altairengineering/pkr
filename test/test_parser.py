# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import unittest

import mock

from pkr.cli.parser import _create_kard


class TestParser(unittest.TestCase):

    def test_create_kard(self):
        args = mock.MagicMock()
        args.configure_mock(**{
            'name': 'ace',
            'driver': 'compose',
            'env': 'dev',
            'extra': ['test=false', 'foo=bar', 'car.wheel=4'],
            'meta': None,
            'features': 'rainbow,log,poney'
        })

        with mock.patch('pkr.cli.parser.Kard') as kard_mock:
            _create_kard(args)

            expected_extras = {
                'test': False,
                'foo': 'bar',
                'car': {
                    'wheel': '4'
                },
                'features': ['rainbow', 'log', 'poney']
            }

            kard_mock.create.assert_called_with(
                'ace', 'dev', 'compose', expected_extras)

            kard_mock.set_current.assert_called_with('ace')
