# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for handling the life cycle for minikube"""

from future import standard_library

standard_library.install_aliases()
import json
import shlex
import subprocess
from urllib.parse import urlparse

from docker.tls import TLSConfig
from pathlib2 import Path

from ..utils import ask_input

from .base import AbstractDriver
from .k8s import KubernetesPkr


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

        cmd = '''
/bin/bash -c 'eval $(/usr/local/bin/minikube docker-env) && \
echo "{\\"host\\": \\"$DOCKER_HOST\\", \\"cert\\":\\"$DOCKER_CERT_PATH\\"}"'
        '''

        out = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
        stdout = out.stdout.read()

        target = json.loads(stdout)
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

    def __init__(self, kard, *args, **kwargs):
        super(MinikubePkr, self).__init__(kard, *args, **kwargs)
        self.host = args[0]

    def get_registry(self, **kwargs):
        if kwargs.get('url') is None:
            kwargs['url'] = urlparse(self.host).hostname + ':5000'
        return super(MinikubePkr, self).get_registry(**kwargs)
