# Copyright© 1986-2024 Altair Engineering Inc.

"""Pkr functions for handling the life cycle with k8s"""
import base64
import os
import shlex
import subprocess
import sys
import zlib
from tempfile import NamedTemporaryFile
from time import sleep

from kubernetes import client, config
import yaml

from pkr.driver import docker
from pkr.cli.log import write

CONFIGMAP = {
    "apiVersion": "v1",
    "kind": "ConfigMap",
    "metadata": {
        "namespace": "kube-system",
        "labels": {
            "pkr": "kard",
        },
    },
    "data": {},
}


class KubernetesPkr:
    """K8s implementation"""

    K8S_FOLDER = "k8s"
    K8S_CONFIG = os.path.expandvars("$KUBECONFIG")

    # pylint: disable=no-member
    def __init__(self, kard, password=None, **kwargs):
        super().__init__(kard, password=password, **kwargs)

        self.metas["registry"] = None
        self._client = None
        if hasattr(self.kard, "meta"):
            self.namespace = self.kard.meta.get("k8s", {}).get("namespace", "default")

        self.env = {
            "KUBECONFIG": self.K8S_CONFIG,
            "PATH": os.environ.get("PATH"),
        }

    @property
    def client(self):
        """Instantite a client, cache it and returns it"""
        if not self._client:
            config.load_kube_config(self.K8S_CONFIG)
            self._client = client.CoreV1Api()
        return self._client

    def get_templates(self):
        """Return the k8s templates"""
        templates = super().get_templates()

        for file in self.kard.meta["driver"].get("k8s", {}).get("k8s_files", []):
            templates.append(
                {
                    "source": self.kard.env.pkr_path / file,
                    "origin": (self.kard.env.pkr_path / file).parent,
                    "destination": "",
                    "subfolder": "k8s",
                }
            )

        return templates

    def run_cmd(self, command, silent=False):
        """Run a shell command"""
        xargs = {}
        if silent:
            xargs["stdout"] = subprocess.PIPE
            xargs["stderr"] = subprocess.PIPE
        with subprocess.Popen(shlex.split(command), env=self.env, close_fds=True, **xargs) as proc:
            stdout, stderr = proc.communicate()

        return stdout or "", stderr or "", proc.returncode

    def run_kubectl(self, cmd, silent=False):
        """Run kubectl tool with the provided command"""
        return self.run_cmd(f"kubectl {cmd}", silent)

    def new_configmap(self):
        """
        Provide a fresh configmap
        """
        cm = CONFIGMAP.copy()
        cm["metadata"]["name"] = f"pkr-{self.kard.name}"
        return cm

    def get_configmap(self):
        """
        Retrieve previously stored content for this kard
        """
        out, err, returncode = self.run_kubectl(
            f"get cm -n kube-system pkr-{self.kard.name} -o yaml", silent=True
        )
        if returncode and err != "":
            raise Exception(f"Failed to get configmap pkr-{self.kard.name} with : {err}")
        out_hash = {}
        for key, value in yaml.safe_load(out).get("data", {}).items():
            out_hash[key] = zlib.decompress(base64.b64decode(value)).decode("utf-8")
        return out_hash

    def write_configmap(self, c_m):
        """
        Write a configmap for this kard with deployed content
        cm: {"pkr_template_name": "pkr_template_content", ...}
        """
        if len(c_m) == 0:
            self.run_kubectl(f"delete cm -n kube-system pkr-{self.kard.name}")
            return
        cm_compressed = self.new_configmap()
        for key in c_m:
            cm_compressed["data"][key] = base64.b64encode(zlib.compress(c_m[key].encode("utf-8")))
        with NamedTemporaryFile() as f:
            f.write(yaml.dump(cm_compressed).encode("utf-8"))
            self.run_kubectl(f"apply -f {f.name}")

    # pylint: disable=too-many-branches
    def start(self, services=None, yes=False):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        k8s_files_path = self.kard.path / "k8s"
        meta_file = self.kard.path / "meta.yml"
        saved_files = [meta_file] + sorted(k8s_files_path.glob("*.yml"))

        old_cm = self.get_configmap()
        new_cm = {}

        write("Compare with previous deployment ...")
        for k8s_file in saved_files:
            if services and k8s_file.name[:-4] not in services:
                new_cm[k8s_file.name] = old_cm[k8s_file.name]
                continue

            if k8s_file.name in old_cm:
                with NamedTemporaryFile() as f:
                    f.write(old_cm[k8s_file.name].encode("utf-8"))
                    f.seek(0)
                    self.run_cmd(f"diff -u {f.name} {k8s_file}")
            else:
                if not k8s_file.name.startswith("."):
                    write(f"Added file {k8s_file}")

            if not k8s_file.name.startswith("."):
                with open(str(k8s_file), "r", encoding="utf-8") as f:
                    new_cm[k8s_file.name] = f.read()

        for name in old_cm:
            if name not in new_cm:
                write(f"Removed file {name}")

        if sys.stdin.isatty() and not yes:
            proceed = None
            while proceed not in {"y", "n"}:
                proceed = input("Apply (y/n) ? ")
            if proceed == "n":
                return

        write("\nApplying manifests ...")
        for name, cm_content in old_cm.items():
            if name not in new_cm:
                write(f"Removing {name}")
                with NamedTemporaryFile() as f:
                    f.write(cm_content.encode("utf-8"))
                    f.seek(0)
                    out, _, _ = self.run_kubectl(f"delete -f {f.name}")
                    write(out)

        for k8s_file in saved_files[1:]:
            if services and k8s_file.name[:-4] not in services:
                continue
            write(f"Processing {k8s_file.name}")
            out, _, _ = self.run_kubectl(f"apply -f {k8s_file}")
            write(out)
            sleep(0.1)

        self.write_configmap(new_cm)

    def stop(self, services=None):
        """Stops services"""
        k8s_files_path = self.kard.path / "k8s"

        for k8s_file in sorted(k8s_files_path.glob("*.yml"), reverse=True):
            if services and k8s_file.name[:-4] not in services:
                continue
            write(f"Processing {k8s_file}")
            out, _, _ = self.run_kubectl(f"delete -f {k8s_file}")
            write(out)
            sleep(0.5)

        self.write_configmap({})

    def restart(self, services=None):
        """Restart services"""
        raise NotImplementedError()

    def cmd_ps(self):
        """List containers with ips"""
        response = self.client.list_namespaced_pod(self.namespace)
        services = response.items
        for service in services:
            write(f" - {service.metadata.name}: {service.status.phase} - {service.status.pod_ip}")

    # pylint: disable=unused-argument
    def clean(self, kill=False):
        """Clean the stack"""
        self.stop()

    def list_kards(self):
        """Return the list of kards stored in the config map"""
        out, err, returncode = self.run_kubectl("get cm -n kube-system -l pkr=kard -o name", True)
        if returncode and err != "":
            raise Exception(f"Error getting kards from k8s: {err}")

        kards = []
        if out != "":
            for line in out.decode("utf-8").splitlines():
                _, name = line.split("configmap/pkr-")
                kards.append(f"k8s/{name}")
        return kards

    def load_kard(self):
        """Load kard from config map"""
        cm = self.get_configmap()
        with self.kard.meta_file.open("w+") as meta_file:
            meta_file.write(cm["meta.yml"])

    def encrypt(self, password=None):
        """Encrypt the kard"""
        raise NotImplementedError()

    def decrypt(self, password=None):
        """Decrypt the kard"""
        raise NotImplementedError()


# pylint: disable=abstract-method
class KubernetesDriver(KubernetesPkr, docker.DockerDriver):
    """Combine classes for creating the driver"""
