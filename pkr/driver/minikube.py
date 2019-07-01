# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for handling the life cycle for minikube"""

from future import standard_library

standard_library.install_aliases()
import json
import os
import shlex
import subprocess

from docker.tls import TLSConfig
from pathlib2 import Path
from kubernetes.client.rest import ApiException

from ..cli.log import write
from ..utils import ask_input

from .base import AbstractDriver
from .k8s import KubernetesPkr


def print_manual():
    print('''
To create or start a kubernetes stack:

# sudo ip link set docker0 promisc on
# export KUBECONFIG=$HOME/.kube/minikube.config
# export MINIKUBE_HOME=$HOME
# export CHANGE_MINIKUBE_NONE_USER=true
# sudo -E minikube start --vm-driver=none --extra-config=kubelet.hairpin-mode=promiscuous-bridge
# sudo -E minikube addons enable ingress
''')


class Driver(AbstractDriver):
    """Abstract class for a driver"""

    @staticmethod
    def get_docker_client(kard):
        """Return the docker client

        The param target specifies wether we should load a client connected to
        the 'local' docker socket, or antoher target. For instance, we can
        connect to a local minikube docker automatically by loading values from
        the 'docker-env' command.
        """

        cmd = '/usr/local/bin/minikube config get vm-driver'
        out = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out.wait()

        # This means we are on "direct" mode, without VM.
        if out.returncode == 64:
            return MinikubePkr(kard)

        cmd = '''
/bin/bash -c 'eval $(minikube docker-env) && \
echo "{\\"host\\": \\"$DOCKER_HOST\\", \\"cert\\":\\"$DOCKER_CERT_PATH\\"}"'
        '''

        out = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
        out.wait()
        stdout = out.stdout.read()

        if out.returncode != 0:
            write('Error while getting the docker environment.')
            write(stdout)

        target = json.loads(stdout)

        if not target['host']:
            return MinikubePkr(kard)

        cert_path = Path(target['cert'])

        tls_config = TLSConfig(
            client_cert=(
                str(cert_path / 'cert.pem'),
                str(cert_path / 'key.pem')),
            verify=str(cert_path / 'ca.pem'))
        return MinikubePkr(kard, target['host'], tls=tls_config)

    @staticmethod
    def get_meta(extras, kard):
        metas = ('tag',)
        ret = {}
        for meta in metas:
            if meta in extras:
                ret[meta] = extras.pop(meta)
            else:
                ret[meta] = ask_input(meta)
        return ret


class MinikubePkr(KubernetesPkr):
    """pkr implementation for minikube"""

    K8S_CONFIG = os.path.expandvars('$HOME/.kube/minikube.config')

    def __init__(self, kard, *args, **kwargs):
        super(MinikubePkr, self).__init__(kard, *args, **kwargs)
        self.mk_bin = 'minikube'

        self.env.update({
            'MINIKUBE_HOME': os.path.expandvars('$HOME'),
            'CHANGE_MINIKUBE_NONE_USER': 'true',
        })

    def get_status(self):
        try:
            self.client.read_node_status('minikube')
        except ApiException:
            print_manual()
            return False

    def run_minikube(self, cmd):
        """Run kubectl tool with the provided command"""
        return self.run_cmd('minikube {}'.format(cmd))
