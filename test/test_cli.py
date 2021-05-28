# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import os
from stat import S_IMODE
import shutil
import subprocess
import tempfile
import unittest

import six
import re
import yaml
from pathlib import Path

from pkr.kard import Kard
from pkr.utils import PATH_ENV_VAR
from pkr.version import __version__
from .utils import get_test_files_path


def _build_tmp_pkr_path():
    """Create a tmp folder"""
    return Path(tempfile.mkdtemp())


def _create_kard_fs(self_cls):
    """Create a folder for kard"""
    os.environ[PATH_ENV_VAR] = str(self_cls.pkr_path)


def _populate_env(self_cls, env_name="env1"):
    env_path = self_cls.pkr_path / "env"
    test_env_path = get_test_files_path() / env_name

    shutil.copytree(str(test_env_path), str(env_path))


def _populate_templates(self_cls, template_name="templates1"):
    tpl_path = self_cls.pkr_path / "templates"
    test_tpl_path = get_test_files_path() / template_name

    shutil.copytree(str(test_tpl_path), str(tpl_path))


def _create_test_kard(self_cls, **kwargs):
    kard_name = "test"

    kwargs.setdefault("env_name", "dev")
    kwargs.setdefault("driver_name", "compose")

    kwargs.setdefault("extra", {})
    kwargs["extra"].setdefault("tag", "test")

    self_cls.kard = Kard.create(kard_name, **kwargs)
    Kard.set_current(kard_name)


class TestCLI(unittest.TestCase):
    PKR = "pkr"

    @staticmethod
    def _run_cmd(cmd):

        prc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        prc.wait()

        return prc

    def _create_kard_fs(self):
        self.pkr_path = _build_tmp_pkr_path()
        Kard.CURRENT_KARD = None  # Clear the Kard cache
        _create_kard_fs(self)
        self.addCleanup(os.environ.pop, PATH_ENV_VAR)

    def tearDown(self):
        if hasattr(self, "pkr_path") and self.pkr_path.exists():
            shutil.rmtree(str(self.pkr_path))
            del self.pkr_path

    def test_help(self):
        cmd = "{} -h".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        stdout = prc.stdout.read()
        self.assertTrue(stdout.startswith(b"usage:"))

    def test_version(self):
        cmd = "{} -v".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        expected_output = "pkr {}\n".format(__version__).encode()

        if six.PY2:
            stdout = prc.stderr.read()
            prc.stdout.close()
            # Here we prevent the tests from failing when we have the random TypeError
            self.assertTrue(stdout.startswith(expected_output))
        else:
            stdout = prc.stdout.read()
            prc.stderr.close()
            self.assertEqual(expected_output, stdout)

    def test_kard_create_should_warn_no_pkr_path(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        cmd = "{} kard create test".format(self.PKR)

        prc = self._run_cmd(cmd)
        self.assertEqual(1, prc.returncode)

        error_msg = b"Current path .* is not a valid pkr path, " b"no usable env found\n"
        stdout = prc.stdout.read()
        six.assertRegex(self, stdout, error_msg)

    def test_should_use_valid_pkr_path_from_env(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        self.pkr_path = _build_tmp_pkr_path()
        _populate_env(self)

        os.environ[PATH_ENV_VAR] = str(self.pkr_path)

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

    def test_should_not_use_invalid_pkr_path_from_env(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        self.pkr_path = _build_tmp_pkr_path()

        os.environ[PATH_ENV_VAR] = str(self.pkr_path)

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(1, prc.returncode)

        error_msg = b"Given path .* is not a valid pkr path, " b"no usable env found\n"
        stdout = prc.stdout.read()
        six.assertRegex(self, stdout, error_msg)

    def test_should_use_valid_pkr_path_from_current_path(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        self.pkr_path = _build_tmp_pkr_path()
        _populate_env(self)

        cmd = "cd {} && {} kard list".format(self.pkr_path, self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

    def test_should_use_valid_pkr_path_from_current_path_child_directory(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        self._create_kard_fs()
        _populate_env(self)
        _create_test_kard(self)

        cmd = "cd {}/kard/current/ && {} kard list".format(self.pkr_path, self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

    def test_should_not_use_invalid_pkr_path_from_env(self):

        # Ensure the environment variable is not set
        previous_path = os.environ.pop(PATH_ENV_VAR, None)
        if previous_path:
            self.addCleanup(os.environ.setdefault, PATH_ENV_VAR, previous_path)

        self.pkr_path = _build_tmp_pkr_path()

        cmd = "cd {} && {} kard list".format(self.pkr_path, self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(1, prc.returncode)

        error_msg = b"Current path .* is not a valid pkr path, " b"no usable env found\n"
        stdout = prc.stdout.read()
        six.assertRegex(self, stdout, error_msg)

    def test_kard_list_should_display_warn_message(self):

        self._create_kard_fs()
        _populate_env(self)

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = b"No kard found.\n"
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

    def test_kard_list(self):

        self._create_kard_fs()
        _populate_env(self)
        _create_test_kard(self)

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = (
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
            b"Kards:\n"
            b" - test\n"
        )
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

    def test_kard_create_with_extra(self):

        self._create_kard_fs()
        _populate_env(self)

        cmd = "{} kard create test --extra tag=123".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = (
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
            b"Current kard is now: test\n"
        )
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

        meta_file = self.pkr_path / "kard" / "test" / "meta.yml"
        self.assertTrue(meta_file.exists())

        expected_meta = {
            "driver": {"name": "compose"},
            "env": "dev",
            "features": ["h", "g", "f", "e"],
            "project_name": self.pkr_path.name.lower(),
            "src_path": "{}/kard/test/src".format(str(self.pkr_path)),
            "tag": "123",
        }

        self.assertEqual(expected_meta, yaml.safe_load(meta_file.open("r")))

    def test_kard_create_with_meta(self):

        self._create_kard_fs()
        _populate_env(self)

        shutil.copy(str(get_test_files_path() / "meta1.yml"), str(self.pkr_path / "meta1.yml"))

        cmd = "{} kard create test --features c,d,c --meta {}/meta1.yml".format(
            self.PKR, str(self.pkr_path)
        )

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = (
            b"WARNING: Feature a is duplicated in passed meta\n"
            b"WARNING: Feature c is duplicated in args\n"
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
            b"Current kard is now: test\n"
        )
        stdout = prc.stdout.read()
        print(stdout)
        self.assertEqual(msg, stdout)

        meta_file = self.pkr_path / "kard" / "test" / "meta.yml"
        self.assertTrue(meta_file.exists())

        expected_meta = {
            "driver": {"name": "compose"},
            "env": "dev",
            "features": ["h", "g", "f", "e", "b", "a", "d", "c"],
            "project_name": self.pkr_path.name.lower(),
            "src_path": "{}/kard/test/src".format(str(self.pkr_path)),
            "tag": "123",
        }

        self.assertEqual(expected_meta, yaml.safe_load(meta_file.open("r")))

    def test_kard_make(self):

        self._create_kard_fs()
        _populate_env(self)
        _populate_templates(self)
        _create_test_kard(self)

        cmd = "{} kard make".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()

        self.assertEqual(0, prc.returncode, stdout)

        msg = (
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
            b"Removing docker-context... done !\n"
            b"(Re)creating docker-context... done !\n"
            b"Recreating sources in pkr context... done !\n"
        )

        self.assertEqual(msg, stdout)


class TestKardMake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkr_path = _build_tmp_pkr_path()
        _create_kard_fs(cls)
        _populate_env(cls)
        _populate_templates(cls)
        _create_test_kard(cls, extra={"foo": "bar"})

        Kard.CURRENT_KARD = None  # Clear the Kard cache
        cls.kard.make()

        cls.context_path = cls.pkr_path / "kard" / "current" / "docker-context"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.pkr_path))
        os.environ.pop(PATH_ENV_VAR)

    def test_docker_compose_present(self):
        # Check if files are created
        dc_file = self.pkr_path / "kard" / "current" / "docker-compose.yml"
        self.assertTrue(dc_file.exists())

        expected_docker_compose = {
            "services": {},
            "paths": [
                str(self.context_path.resolve() / "test"),
                str(self.pkr_path / "kard" / "test" / "src" / "test"),
            ],
        }

        self.assertEqual(expected_docker_compose, yaml.safe_load(dc_file.open("r")))

    def test_dockerfile_present(self):
        gen_file = self.context_path / "backend.dockerfile"
        expected_content = """FROM python:alpine3.7\n"""

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)

    def test_config_present(self):
        gen_file = self.context_path / "backend" / "backend.conf"
        expected_content = (
            "foo=bar\n"
            "tag_b64=dGVzdA==\n"
            "tag_sha256=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08\n"
            "htpassword=a:"
        )

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)


class TestKardMakeWithRelativeSrcPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkr_path = _build_tmp_pkr_path()
        _create_kard_fs(cls)
        _populate_env(cls)
        _populate_templates(cls)
        _create_test_kard(cls, extra={"src_path": "dummy/.."})

        Kard.CURRENT_KARD = None  # Clear the Kard cache
        cls.kard.make()

        cls.context_path = cls.pkr_path / "kard" / "current" / "docker-context"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.pkr_path))
        os.environ.pop(PATH_ENV_VAR)

    def test_docker_compose_present(self):
        # Check if files are created
        dc_file = self.pkr_path / "kard" / "current" / "docker-compose.yml"
        self.assertTrue(dc_file.exists())

        expected_docker_compose = {
            "services": {},
            "paths": [
                str(self.context_path.resolve() / "test"),
                str(self.pkr_path / "test"),
            ],
        }

        self.assertEqual(expected_docker_compose, yaml.safe_load(dc_file.open("r")))

    def test_start_script_present_with_proper_mod(self):
        gen_file = self.context_path / "backend" / "start.sh"
        expected_content = "#!/bin/bash\n\nsleep 1\n"
        # We only check permissions for user, to be compatible with Travis CI environment
        expected_user_mode = "5"

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)

        mode = str(S_IMODE(gen_file.stat().st_mode))[:1]
        self.assertEqual(expected_user_mode, mode)

    def test_exec_script_present_with_proper_mod(self):
        gen_file = self.context_path / "backend" / "exec.sh"
        expected_content = "echo test"
        expected_user_mode = "5"

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)

        mode = str(S_IMODE(gen_file.stat().st_mode))[:1]
        self.assertEqual(expected_user_mode, mode)


class TestKardMakeWithExtensionDev(TestKardMake):
    @classmethod
    def setUpClass(cls):
        cls.pkr_path = _build_tmp_pkr_path()
        _create_kard_fs(cls)
        _populate_env(cls, "env2")
        _populate_templates(cls, "templates2")
        _create_test_kard(cls)

        Kard.CURRENT_KARD = None  # Clear the Kard cache
        cls.kard.make()

        cls.context_path = cls.pkr_path / "kard" / "current" / "docker-context"

    def test_dockerfile_present(self):
        gen_file = self.context_path / "backend.dockerfile"
        expected_content = "FROM python:alpine3.7\n\n" 'VOLUME ["/usr/src/app"]'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)


class TestKardMakeWithExtensionProd(TestKardMake):
    @classmethod
    def setUpClass(cls):
        cls.pkr_path = _build_tmp_pkr_path()
        _create_kard_fs(cls)
        _populate_env(cls, "env2")
        _populate_templates(cls, "templates2")
        _create_test_kard(cls, env_name="prod")

        Kard.CURRENT_KARD = None  # Clear the Kard cache
        cls.kard.make()

        cls.context_path = cls.pkr_path / "kard" / "current" / "docker-context"

    def test_dockerfile_present(self):
        gen_file = self.context_path / "backend.dockerfile"
        expected_content = "FROM python:alpine3.7\n\n" 'ADD "app" "/usr/src/app"'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)


class TestImagePull(TestCLI):
    def test_image_pull_properly_fail(self):
        self._create_kard_fs()
        _populate_env(self)
        _populate_templates(self)
        _create_test_kard(self)

        # We want to test that the command `pkr image pull` get a same error 3
        # times, because it should retry 3 times, and fail with code 1
        cmd = "{} image pull -r dummyregistry -t remote_tag".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        self.assertEqual(1, prc.returncode, stdout)

        expected_cmd_output = b"Pulling backend:test from dummyregistry/backend:remote_tag..."
        expected_error_regex = b"Error while pulling the image test:"
        expected_final_print_prefix = b"ImagePullError"

        error_outputs = stdout.split(b"\n")[:-1]
        # 1 line for the command output
        # 4 lines with the same error (3 tries, and the final print)
        self.assertEqual(len(error_outputs), 8)
        self.assertEqual(error_outputs[3], expected_cmd_output)

        errors = error_outputs[4:]
        # Check for 3 lines with the same message that indicate we have
        # retried 3 times
        six.assertRegex(self, errors[0], expected_error_regex)
        six.assertRegex(self, errors[1], expected_error_regex)
        six.assertRegex(self, errors[2], expected_error_regex)
        # Check that the last line is the final error print with the proper
        # error type
        six.assertRegex(self, errors[-1], expected_final_print_prefix)


class TestImagePush(TestCLI):
    def test_image_push(self):
        self._create_kard_fs()
        _populate_env(self)
        _populate_templates(self)
        _create_test_kard(self)

        cmd = "{} image push -r testrepo.io -t foo -o bar".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        self.assertEqual(1, prc.returncode, stdout)

        expected_cmd_output = b"Pushing backend:foo to testrepo.io/backend:foo"
        expected_cmd_output_2 = re.compile(
            b"ERROR: \(ImageNotFound\) 404 Client Error for http\+docker://.*: "
            b'Not Found \("No such image: backend:foo"\)'
        )

        error_outputs = stdout.split(b"\n")[:-1]
        # 1 line for the command output
        # 4 lines with the same error (3 tries, and the final print)
        self.assertEqual(len(error_outputs), 5)
        self.assertEqual(error_outputs[3], expected_cmd_output)
        assert re.match(expected_cmd_output_2, error_outputs[4])
