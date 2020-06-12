# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Pkr functions for handling the life cycle with k8s"""
import os
import shlex
import subprocess
from time import sleep

from kubernetes import client, config
from passlib.apache import HtpasswdFile

from .base import DOCKER_SOCK, AbstractDriver, Pkr
from ..cli.log import write
from ..utils import get_pkr_path, ensure_definition_matches, merge


class Driver(AbstractDriver):
    """Concrete class for k8s driver"""

    @staticmethod
    def get_docker_client(kard):
        return KubernetesPkr(kard, DOCKER_SOCK)

    @staticmethod
    def get_meta(extras, kard):
        metas = ['registry', 'tag']

        default = kard.env.get('default_meta', {}).copy()
        merge(extras, default)

        return ensure_definition_matches(
            definition=metas,
            defaults=default,
            data=kard.meta)


class KubernetesPkr(Pkr):
    """K8s implementation"""

    K8S_FOLDER = 'k8s'
    K8S_CONFIG = os.path.expandvars('$KUBECONFIG')

    def __init__(self, *args, **kwargs):
        super(KubernetesPkr, self).__init__(*args, **kwargs)

        self._client = None
        self.namespace = 'default'

        self.env = {
            'KUBECONFIG': self.K8S_CONFIG,
            'PATH': os.environ.get('PATH'),
        }

    @property
    def client(self):
        if not self._client:
            config.load_kube_config(self.K8S_CONFIG)
            self._client = client.CoreV1Api()
        return self._client

    def _get_registry(self):
        return self.kard.meta.get('registry')

    def populate_kard(self):

        def read_kard_file(conf_file_name):
            conf_path = self.kard.path / conf_file_name
            return conf_path.read_text()

        def format_image(image_name):

            image = '{}:{}'.format(image_name, self.kard.meta['tag'])

            if not self._get_registry():
                return image

            return '{}/{}'.format(self._get_registry(), image)

        def format_htpasswd(username, password):
            ht = HtpasswdFile()
            ht.set_password(username, password)
            return str(ht.to_string().rstrip())

        data = {
            'kard_file_content': read_kard_file,
            'format_image': format_image,
            'format_htpasswd': format_htpasswd,
        }
        tpl_engine = self.kard.get_template_engine(data)

        k8s_files = self.kard.env.env['driver']['k8s'].get('k8s_files', [])

        if k8s_files is not None:
            for k8s_file in k8s_files:
                path = get_pkr_path() / k8s_file
                tpl_engine.copy(path=path,
                                origin=path.parent,
                                local_dst=self.kard.path / self.K8S_FOLDER,
                                excluded_paths=[],
                                gen_template=True)

    def run_cmd(self, command):
        proc = subprocess.Popen(
            shlex.split(command),
            env=self.env,
            close_fds=True
        )
        stdout, stderr = proc.communicate()

        return stdout or '', stderr or ''

    def run_kubectl(self, cmd):
        """Run kubectl tool with the provided command"""
        return self.run_cmd('kubectl {}'.format(cmd))

    def start(self, services=None):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        k8s_files_path = self.kard.path / 'k8s'

        for k8s_file in sorted(k8s_files_path.glob('*.yml')):
            write('Processing {}'.format(k8s_file))
            out, _ = self.run_kubectl('apply -f {}'.format(k8s_file))
            write(out)
            sleep(0.5)

    def stop(self, services=None):
        """Stops services"""
        k8s_files_path = self.kard.path / 'k8s'

        for k8s_file in sorted(k8s_files_path.glob('*.yml'), reverse=True):
            write('Processing {}'.format(k8s_file))
            out, _ = self.run_kubectl('delete -f {}'.format(k8s_file))
            write(out)
            sleep(0.5)

    def restart(self, services=None):
        """Restart services"""
        raise NotImplementedError()

    def cmd_ps(self):
        """ List containers with ips"""
        response = self.client.list_namespaced_pod(self.namespace)
        services = response.items
        for service in services:
            write(' - {}: {}'.format(
                service.metadata.name, service.status.pod_ip))
