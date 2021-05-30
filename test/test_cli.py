# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import os
from stat import S_IMODE
import shutil
import subprocess
import unittest

import re
import yaml

from pkr.kard import Kard
from pkr.utils import PATH_ENV_VAR
from pkr.version import __version__
from .utils import pkrTestCase


class TestCLI(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "path1"
    kard_env = "dev"

    @staticmethod
    def _run_cmd(cmd):
        prc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        prc.wait()
        return prc

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

        stdout = prc.stdout.read()
        prc.stderr.close()
        self.assertEqual(expected_output, stdout)

    def test_kard_create_should_warn_no_pkr_path(self):
        os.environ.pop(PATH_ENV_VAR)
        cmd = "{} --debug kard create test".format(self.PKR)

        prc = self._run_cmd(cmd)
        self.assertEqual(1, prc.returncode)

        error_msg = b"Current path .* is not a valid pkr path, " b"no usable env found\n"
        stdout = prc.stdout.read()
        self.assertRegex(stdout, error_msg)

    def test_should_use_valid_pkr_path_from_env(self):
        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode, prc.stdout.read())

    def test_should_not_use_invalid_pkr_path_from_env(self):
        os.environ[PATH_ENV_VAR] = "/dev"

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()

        self.assertEqual(1, prc.returncode, stdout)

        error_msg = b"Given path .* is not a valid pkr path, " b"no usable env found\n"
        self.assertRegex(stdout, error_msg, stdout)

    def test_should_not_use_invalid_pkr_path_from_current_path(self):
        os.environ.pop(PATH_ENV_VAR)
        cmd = "cd {} && {} kard list".format("/", self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()

        self.assertEqual(1, prc.returncode, stdout)

        error_msg = b"Current path .* is not a valid pkr path, " b"no usable env found\n"
        self.assertRegex(stdout, error_msg, stdout)

    def test_should_use_valid_pkr_path_from_current_path(self):
        cmd = "cd {} && {} kard list".format(os.environ.pop(PATH_ENV_VAR), self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

    def test_should_use_valid_pkr_path_from_current_path_child_directory(self):
        cmd = "cd {}/env/ && {} kard list".format(os.environ.pop(PATH_ENV_VAR), self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

    def test_kard_list_should_display_warn_message(self):
        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = b"No kard found.\n"
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

    def test_kard_list(self):
        self.generate_kard()

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode)

        msg = b"Kards:\n" b" - test\n"
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

    def test_kard_create_with_extra(self):
        cmd = "{} kard create test --extra tag=123".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()

        self.assertEqual(0, prc.returncode, stdout)

        msg = (
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
            b"Current kard is now: test\n"
        )
        self.assertEqual(msg, stdout, stdout)

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
        shutil.copy(str(self.src_path / "meta1.yml"), str(self.pkr_path / "meta1.yml"))

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
        self.generate_kard()
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

    def test_image_pull_properly_fail(self):
        self.generate_kard()
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
        self.assertEqual(len(error_outputs), 8, stdout)
        self.assertEqual(error_outputs[3], expected_cmd_output)

        errors = error_outputs[4:]
        # Check for 3 lines with the same message that indicate we have
        # retried 3 times
        self.assertRegex(errors[0], expected_error_regex)
        self.assertRegex(errors[1], expected_error_regex)
        self.assertRegex(errors[2], expected_error_regex)
        # Check that the last line is the final error print with the proper
        # error type
        self.assertRegex(errors[-1], expected_final_print_prefix)

    def test_image_push(self):
        self.generate_kard()

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
        self.assertEqual(len(error_outputs), 5, stdout)
        self.assertEqual(error_outputs[3], expected_cmd_output)
        assert re.match(expected_cmd_output_2, error_outputs[4])


class TestKardMake(pkrTestCase):
    kard_extra = {"tag": "test", "foo": "bar"}
    pkr_folder = "path1"
    kard_env = "dev"

    def test_docker_compose_present(self):
        self.generate_kard()
        self.make_kard()

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
        self.generate_kard()
        self.make_kard()

        gen_file = self.context_path / "backend.dockerfile"
        expected_content = """FROM python:alpine3.7\n"""

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)

    def test_config_present(self):
        self.generate_kard()
        self.make_kard()

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


class TestKardMakeWithRelativeSrcPath(pkrTestCase):
    kard_extra = {"tag": "test", "src_path": "dummy/.."}
    pkr_folder = "path1"
    kard_env = "dev"

    def test_docker_compose_present(self):
        self.generate_kard()
        self.make_kard()

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
        self.generate_kard()
        self.make_kard()

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
        self.generate_kard()
        self.make_kard()

        gen_file = self.context_path / "backend" / "exec.sh"
        expected_content = "echo test"
        expected_user_mode = "5"

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)

        mode = str(S_IMODE(gen_file.stat().st_mode))[:1]
        self.assertEqual(expected_user_mode, mode)


class TestKardMakeWithExtensionDev(TestKardMake):
    pkr_folder = "path2"
    kard_env = "dev"

    def test_dockerfile_present(self):
        self.generate_kard()
        self.make_kard()

        gen_file = self.context_path / "backend.dockerfile"
        expected_content = "FROM python:alpine3.7\n\n" 'VOLUME ["/usr/src/app"]'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)


class TestKardMakeWithExtensionProd(TestKardMake):
    pkr_folder = "path2"
    kard_env = "prod"

    def test_dockerfile_present(self):
        self.generate_kard()
        self.make_kard()

        gen_file = self.context_path / "backend.dockerfile"
        expected_content = "FROM python:alpine3.7\n\n" 'ADD "app" "/usr/src/app"'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)
