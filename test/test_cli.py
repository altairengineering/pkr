# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

import os
from stat import S_IMODE
import shutil

import re
import yaml

from pkr.kard import Kard
from pkr.utils import PATH_ENV_VAR
from pkr.version import __version__
from .utils import pkrTestCase, msg_hlp


class TestCLI(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "path1"
    kard_env = "dev"
    kard_driver = "compose"

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
        stderr = prc.stderr.read()
        self.assertRegex(stderr, error_msg)

    def test_should_use_valid_pkr_path_from_env(self):
        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)

        self.assertEqual(0, prc.returncode, prc.stderr.read())

    def test_should_not_use_invalid_pkr_path_from_env(self):
        os.environ[PATH_ENV_VAR] = "/dev"

        cmd = "{} kard list".format(self.PKR)

        prc = self._run_cmd(cmd)
        stderr = prc.stderr.read()

        self.assertEqual(1, prc.returncode, stderr)

        error_msg = b"Given path .* is not a valid pkr path, " b"no usable env found\n"
        self.assertRegex(stderr, error_msg, stderr)

    def test_should_not_use_invalid_pkr_path_from_current_path(self):
        os.environ.pop(PATH_ENV_VAR)
        cmd = "cd {} && {} kard list".format("/", self.PKR)

        prc = self._run_cmd(cmd)
        stderr = prc.stderr.read()

        self.assertEqual(1, prc.returncode, stderr)

        error_msg = b"Current path .* is not a valid pkr path, " b"no usable env found\n"
        self.assertRegex(stderr, error_msg, stderr)

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
        cmd = "{} kard create test --extra tag=123 --extra tag2=456".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()

        self.assertEqual(0, prc.returncode, stdout)

        msg_err = (
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
        )
        msg = b"Current kard is now: test\n"
        self.assertEqual(msg, stdout, stdout)
        self.assertEqual(msg_err, stderr, stderr)

        meta_file = self.pkr_path / "kard" / "test" / "meta.yml"
        self.assertTrue(meta_file.exists())

        expected_meta = {
            "env": "dev",
            "features": [],
            "project_name": "test",
            "tag": "123",
            "tag2": "456",
        }

        self.assertEqual(expected_meta, yaml.safe_load(meta_file.open("r")))

    def test_kard_create_with_meta(self):
        shutil.copy(str(self.src_path / "meta1.yml"), str(self.pkr_path / "meta1.yml"))

        cmd = "{} kard create test --features c,d,c --meta {}/meta1.yml".format(
            self.PKR, str(self.pkr_path)
        )

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(0, prc.returncode, stderr)

        msg_err = (
            b"WARNING: Feature a is duplicated in passed meta\n"
            b"WARNING: Feature c is duplicated in args\n"
            b"WARNING: Feature g is duplicated in import dev/e from env dev\n"
            b"WARNING: Feature e is duplicated in env dev\n"
            b"WARNING: Feature g is duplicated in feature e from env dev\n"
        )
        msg = b"Current kard is now: test\n"
        self.assertEqual(msg, stdout, stdout)
        self.assertEqual(msg_err, stderr, stderr)

        meta_file = self.pkr_path / "kard" / "test" / "meta.yml"
        self.assertTrue(meta_file.exists())

        expected_meta = {
            "env": "dev",
            "features": ["b", "a", "d", "c"],
            "project_name": "test",
            "tag": "123",
        }

        self.assertEqual(expected_meta, yaml.safe_load(meta_file.open("r")))

        # Test pkr kard dump
        cmd = "{} kard dump".format(self.PKR)
        prc = self._run_cmd(cmd)
        dump = yaml.safe_load(prc.stdout)
        self.assertEqual(dump.get("features", []), ["h", "g", "f", "e", "b", "a", "d", "c"])
        self.assertEqual(dump.get("env_meta"), "dummy")
        self.assertEqual(dump.get("src_path"), "/tmp")
        self.assertEqual(dump.get("templated_meta"), "MTIz")
        self.assertEqual(dump.get("templated_hash").get("key"), "dHV0dQ==")
        self.assertEqual(dump.get("templated_list"), ["tutu", "dHV0dQ=="])
        self.assertEqual(dump.get("templated_inline"), ["tutu", "titi"])
        self.assertEqual(dump.get("templated_dict_list"), ["tutu", {"a": "b", "c": "dHV0dQ=="}])

    def test_kard_make(self):
        self.generate_kard()
        cmd = "{} kard make".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()

        self.assertEqual(0, prc.returncode, msg_hlp(stdout, stderr))

        msg = b"Removing docker-context ... Ok !\n" b"Removing compose ... Ok !\n"

        self.assertEqual(msg, stdout)

    def test_image_pull_properly_fail(self):
        self.generate_kard()
        # We want to test that the command `pkr image pull` get a same error 3
        # times, because it should retry 3 times, and fail with code 1
        cmd = "{} image pull -r dummyregistry -t remote_tag".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, stdout)

        expected_cmd_output = b"Pulling backend:test from dummyregistry/backend:remote_tag..."
        expected_error_regex = b"Error while pulling the image test:"
        expected_final_print_prefix = b"ImagePullError"

        error_outputs = stdout.split(b"\n")[:-1]
        # 1 line for the command output
        # 4 lines with the same error (3 tries, and the final print)
        self.assertEqual(len(error_outputs), 4, stdout)
        self.assertEqual(error_outputs[0], expected_cmd_output)

        errors = error_outputs[1:]
        # Check for 3 lines with the same message that indicate we have
        # retried 3 times
        self.assertRegex(errors[0], expected_error_regex)
        self.assertRegex(errors[1], expected_error_regex)
        self.assertRegex(errors[2], expected_error_regex)
        # Check that the last line is the final error print with the proper
        # error type
        self.assertRegex(stderr, expected_final_print_prefix)

    def test_image_pull_properly_ignore_error(self):
        self.generate_kard()
        # We want to test that the command `pkr image pull` get an error
        # of the non-existence image, and continue the job and finally success with code 0
        cmd = "{} image pull -r dummyregistry -t remote_tag --ignore-errors".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        self.assertEqual(0, prc.returncode, stdout)

        expected_cmd_output = b"Pulling backend:test from dummyregistry/backend:remote_tag..."
        expected_error_regex = b"Error while pulling the image test:"
        expected_final_print_prefix = b"Done !"

        outputs = stdout.split(b"\n")[:-1]
        # 6 lines of output
        self.assertEqual(len(outputs), 6, stdout)
        self.assertEqual(outputs[0], expected_cmd_output)

        self.assertRegex(outputs[1], expected_error_regex)
        # Check that the last line is the final Done message print with the proper
        self.assertRegex(outputs[2], expected_final_print_prefix)

    def test_image_push(self):
        self.generate_kard()

        cmd = "{} image push -r testrepo.io -t foo -o bar".format(self.PKR)

        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, stdout)

        expected_cmd_output = b"Pushing backend:foo to testrepo.io/backend:foo\n"
        expected_cmd_output_2 = re.compile(
            b"ERROR: \(ImageNotFound\) 404 Client Error for http\+docker://.*: "
            b'Not Found \("No such image: backend:foo"\)'
        )

        error_outputs = stderr.split(b"\n")[:-1]
        # 1 line for the command output
        # 4 lines with the same error (3 tries, and the final print)
        self.assertEqual(len(error_outputs), 4, stdout)
        self.assertEqual(stdout, expected_cmd_output)
        assert re.match(expected_cmd_output_2, error_outputs[3])

    def test_explicit_kard_option(self):
        self.generate_kard()

        cmd = "{} kard create test2 --do-not-set-current --extra tag=test2".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(0, prc.returncode, stdout)

        cmd = "{} kard list".format(self.PKR)
        prc = self._run_cmd(cmd)
        self.assertEqual(0, prc.returncode)
        msg = b"Kards:\n" b" - test\n" b" - test2\n"
        stdout = prc.stdout.read()
        self.assertEqual(msg, stdout)

        cmd = "{} kard get".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        self.assertEqual(b"Current Kard: test\n", stdout)

        tag_test2 = b"tag: test2"

        # Use Kard directly through command-line argument
        cmd = "{} kard dump -k test2".format(self.PKR)
        prc = self._run_cmd(cmd)
        self.assertEqual(0, prc.returncode)
        stdout = prc.stdout.read()
        self.assertTrue(tag_test2 in stdout)

        # Use Kard directly through environment variable
        cmd = "{} kard dump".format(self.PKR)
        pkr_env = os.environ.copy()
        pkr_env["PKR_KARD"] = "test2"
        prc = self._run_cmd(cmd, env=pkr_env)
        self.assertEqual(0, prc.returncode)
        stdout = prc.stdout.read()
        self.assertTrue(tag_test2 in stdout)

        # Use default ("current") Kard.
        cmd = "{} kard dump".format(self.PKR)
        prc = self._run_cmd(cmd)
        self.assertEqual(0, prc.returncode)
        stdout = prc.stdout.read()
        self.assertTrue(tag_test2 not in stdout)

    def test_encrypt_kard(self):
        self.generate_kard()
        password = "password"

        cmd = "{} --password {} kard encrypt".format(self.PKR, password)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, msg_hlp(stdout, stderr))
        expected = re.compile(
            b"ERROR: \(FileNotFoundError\) \[Errno 2\] No such file or directory: '/tmp/.*/kard/test/docker-compose.yml'"
        )
        assert re.match(expected, stderr.split(b"\n")[-2])

        # fail to encrypt again
        cmd = "{} -p {} kard encrypt".format(self.PKR, password)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, msg_hlp(stdout, stderr))
        expected = b'ERROR: (PkrException) Metafile for Kard "test" is already encrypted\n'
        self.assertEqual(stderr, expected)

        # fail to decrypt with wrong password
        cmd = "{} -p wrong kard decrypt".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, msg_hlp(stdout, stderr))
        expected = b"ERROR: (Exception) Incorrect decryption password\n"
        self.assertEqual(stderr, expected)

        # decrypt
        cmd = "{} -p {} kard decrypt".format(self.PKR, password)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, msg_hlp(stdout, stderr))
        expected = re.compile(
            b"ERROR: \(FileNotFoundError\) \[Errno 2\] No such file or directory: '/tmp/.*/kard/test/docker-compose.enc'"
        )
        assert re.match(expected, stderr.split(b"\n")[-2])

        # succeed in some regular operations
        cmd = "{} kard dump".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(0, prc.returncode)

        cmd = "{} kard list".format(self.PKR)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(0, prc.returncode, msg_hlp(stdout, stderr))

        # fail to decrypt again
        cmd = "{} --password {} kard decrypt".format(self.PKR, password)
        prc = self._run_cmd(cmd)
        stdout = prc.stdout.read()
        stderr = prc.stderr.read()
        self.assertEqual(1, prc.returncode, msg_hlp(stdout, stderr))
        expected = b'ERROR: (PkrException) Metafile for Kard "test" is already decrypted'
        self.assertEqual(stderr.split(b"\n")[-2], expected)


class TestCLIProd(pkrTestCase):
    PKR = "pkr"
    pkr_folder = "path2"
    kard_env = "prod"

    def test_kard_driver_coming_from_env(self):
        self.generate_kard()
        self.make_kard()

        k8s_path = self.pkr_path / "kard" / "test" / "k8s"
        self.assertTrue(k8s_path.exists())

    def test_src_path_coming_from_env(self):
        self.generate_kard()
        self.make_kard()


class TestKardMake(pkrTestCase):
    kard_extra = {"tag": "test", "foo": "bar"}
    pkr_folder = "path1"
    kard_env = "dev"
    kard_driver = "compose"

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
                str("/tmp/test"),
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
    # test_clean = False

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
        expected_content = "FROM python:alpine3.7\n\n" 'VOLUME ["/usr/src/app"]'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)


class TestKardMakeWithExtensionProd(TestKardMake):
    pkr_folder = "path2"
    kard_env = "prod"

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
        expected_content = "FROM python:alpine3.7\n\n" 'ADD "app" "/usr/src/app"'

        self.assertTrue(gen_file.exists())

        content = gen_file.open("r").read()
        self.assertEqual(expected_content, content)
