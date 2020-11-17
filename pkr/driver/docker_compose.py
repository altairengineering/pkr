# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""pkr functions for managing containers lifecycle with compose"""

from builtins import next
import os
import re
import subprocess
import time
import traceback

from compose import config as docker_config
from compose.cli.command import get_project_name
import docker
from pathlib2 import Path
import yaml

from .base import DOCKER_SOCK, AbstractDriver, Pkr
from ..cli.log import write
from ..utils import PkrException, get_kard_root_path, \
    get_pkr_path, is_running_in_docker, merge, \
    ensure_definition_matches


class Driver(AbstractDriver):
    """Abstract class for a driver"""

    @staticmethod
    def get_docker_client(kard):
        """Return a driver instance"""
        return ComposePkr(kard, DOCKER_SOCK)

    @staticmethod
    def get_meta(extras, kard):
        """Ensure that the required meta are present.

        Args:
          * extras(dict): extra values
          * kard: the current kard
        """
        metas = ['tag', 'project_name']

        default = kard.env.get('default_meta', {}).copy()
        default.setdefault('project_name', get_project_name(str(kard.path)))
        merge(extras, default)

        return ensure_definition_matches(
            definition=metas,
            defaults=default,
            data=kard.meta)


class ComposePkr(Pkr):
    """Implements pkr functions for docker-compose"""

    COMPOSE_BIN = 'docker-compose'
    COMPOSE_FILE = 'docker-compose.yml'

    def __init__(self, *args, **kwargs):
        super(ComposePkr, self).__init__(*args, **kwargs)
        self._base_path = None
        self.driver_meta = self.kard.env.env.get('driver', {}).get(
            'docker_compose', {})
        self.driver_meta.update(self.kard.meta['driver'])

    @property
    def kard_folder_path(self):
        """Property for getting the base path if running in a container"""
        if self._base_path is None:
            if is_running_in_docker():
                container_id = os.popen(
                    'cat /proc/self/cgroup | grep docker | '
                    'grep -o -E "[0-9a-f]{64}" | head -n 1').read().rstrip()
                cli = docker.DockerClient(version='auto')
                cont = cli.containers.get(container_id)
                mount = next((
                    c for c in cont.attrs['Mounts']
                    if c['Destination'] == str(get_kard_root_path())))
                self._base_path = Path(mount['Source'])
            else:
                self._base_path = Path(self.kard.path).parent
        return self._base_path

    def expand_path(self, path, var='%KARD_PATH%'):
        return path.replace(var, str(self.kard_folder_path))

    def _call_compose(self, *args):
        compose_file_path = self.kard.path / self.COMPOSE_FILE
        compose_cmd = [self.COMPOSE_BIN,
                       '-f', str(compose_file_path),
                       '-p', self.kard.meta['project_name']] + list(args)
        subprocess.call(compose_cmd)

    def populate_kard(self):
        """Populate context for compose"""

        def get_data_path(path):
            """Prefix the given path with the path to data volumes.

            Resolves a (Kard-relative or absolute) given data_path
            or goes with the default "<kard>/data"."""

            data_path = Path(self.kard.meta.get('data_path', 'data'))

            if data_path.is_absolute():
                return str(data_path / path)

            return str(self.kard_folder_path / self.kard.name / data_path /
                       path)

        tpl_engine = self.kard.get_template_engine({
            'context_path': lambda p: str(
                self.kard_folder_path / self.kard.name /
                self.kard.context.DOCKER_CONTEXT / p),
            'kard_path': lambda p: str(
                self.kard_folder_path / self.kard.name / p),
            'src_path': lambda p: str(Path(self.kard.meta['src_path']) / p),
            'make_container_name': self.make_container_name,
            'make_image_name': lambda n, t=None: self.make_image_name(n, t),
            'data_path': get_data_path,
        })

        files = self.driver_meta.get('compose_extension_files', [])
        try:
            compose_file = self.driver_meta['compose_file']
            files.insert(0, get_pkr_path() / compose_file)
        except KeyError:
            write('Warning: No docker-compose file is provided with this '
                  'environment.')
            return

        compose_file = {}
        for dfp in files:
            # Render the template first
            df_data = tpl_engine.process_template(get_pkr_path() / dfp)
            # Merge the compose_file
            merge(yaml.safe_load(df_data), compose_file)

        with (self.kard.path / self.COMPOSE_FILE).open('w') as dcf:
            yaml.safe_dump(compose_file, dcf, default_flow_style=False)

    def _load_compose_config(self):
        with (self.kard.path / self.COMPOSE_FILE).open('r') as cp_file:
            compose_data = yaml.safe_load(cp_file)

        return docker_config.load(
            docker_config.config.ConfigDetails(
                str(self.kard.path),
                [docker_config.config.ConfigFile(
                    self.COMPOSE_FILE, compose_data)]))

    def _resolve_services(self, services=None):
        """Return a generator of actual services, or all if None is provided"""

        compose_config = self._load_compose_config()
        all_services = [c['name'] for c in compose_config.services]
        if services is None:
            return all_services

        # Resolve * regexp based service names
        for service in set(services):
            if '*' in service:
                reg = re.compile(service)
                services.extend(
                    [m for m in all_services if reg.match(m)])
                services.remove(service)

        # Remove unexisting services
        return set(services) & set(all_services)

    def build_images(
        self, services, tag=None, verbose=True, logfile=None, nocache=False,
        parallel=None
    ):
        # Image names may be different from service names (e.g. image re-use)
        images = [s['image'].partition(':')[0]  # without ":tag" suffix
                  for s in self._load_compose_config().services
                  if s['name'] in services]

        def req_build(container):
            """Return True if the container requires being built"""
            try:
                return 'dockerfile' in self.kard.env.get_container(container)
            except KeyError:
                return False

        super(ComposePkr, self).build_images(
            [i for i in images if req_build(i)], tag, verbose, logfile, nocache, parallel)

    def start(self, services=None, yes=False):
        self._call_compose('up', '-d', *(services or ()))

    def cmd_up(self, services=None, verbose=False, build_log=None):
        """Start PCLM in a the docker environement.

        Use parameters stored in meta.yml to generate the
        docker-compose.yml file, and then up the container via docker-compose.

        If bare_metal support activated, configure the given host network
        interface and add an interface bridged on the host to all the
        containers that need to communicate with bare metal machines on
        the given network.
        """

        # Re-populating the context...
        self.kard.make()

        eff_modules = self._resolve_services(services)

        self.build_images(eff_modules, verbose=verbose, logfile=build_log)

        self.start(services)

        # Do a nap while the containers are launching before calling
        # post_compose
        time.sleep(5)

        # Call post run handlers on extensions
        self.kard.extensions.post_up(eff_modules)

    def stop(self, services=None):
        """Stop the containers"""
        self._call_compose('stop', *(services or ()))

    def restart(self, services=None):
        """Restart containers"""
        self._call_compose('restart', *(services or ()))

    def get_ip(self, container_name):
        """Return the first IP of a container"""
        containers = [
            container
            for container in self.docker.containers(
                filters={'name': container_name})
            if container['Labels']['com.docker.compose.service'] ==
               container_name
        ]

        if len(containers) != 1:
            raise ValueError('ERROR: {} containers named "{}"'.format(
                len(containers), container_name))

        container_info = self.docker.inspect_container(
            containers.pop().get('Id'))
        networks = container_info['NetworkSettings']['Networks']
        return next(iter(networks.values()))['IPAddress']

    def cmd_ps(self):
        """ List containers with ips"""
        services = self._load_compose_config().services
        for service in [s['name'] for s in services]:
            try:
                container_ip = self.get_ip(service)
            except ValueError:
                container_ip = 'stopped'
            write(' - {}: {}'.format(service, container_ip))

    def clean(self, kill=False):
        """ Remove the containers and the build data file.
        If -w option set, also remove all environement files
        """
        if kill:
            self._call_compose('kill')
        self._call_compose('down', '-v')

    def execute(self, container_name, *args):
        """Execute a command on a container

        Args:
          * container_name: the name of the container
          * *args: the command, like 'ps', 'aux'
        """
        execution = self.docker.exec_create(container=container_name,
                                            cmd=args,
                                            tty=True)

        return self.docker.exec_start(exec_id=execution['Id'])

    def launch_container(self, command, image, volumes, v1=False, links=None):
        """Generic method to launch a container"""

        if v1:
            host_config = self.docker.create_host_config(
                binds=[':'.join((v, k)) for k, v in volumes.items()],
                links={l: l for l in [self.make_container_name(s)
                                      for s in links]})
            networking_config = None
        else:
            host_config = self.docker.create_host_config(
                binds=[':'.join((v, k)) for k, v in volumes.items()])
            network_name = self.kard.meta['project_name'] + '_default'.format()
            networking_config = self.docker.create_networking_config({
                network_name: self.docker.create_endpoint_config()
            })

        container = self.docker.create_container(
            image=image,
            name=self.make_container_name('init'),
            command=command,
            host_config=host_config,
            networking_config=networking_config)

        try:
            started = False
            ret = {'StatusCode': 1}
            attempt = 10
            container_id = container.get('Id')
            while started not in ('running', 'exited'):
                self.docker.start(container=container_id)
                info = self.docker.inspect_container(container=container_id)
                started = info['State']['Status']

            while ret['StatusCode'] != 0 and attempt > 0:
                attempt -= 1
                time.sleep(3)
                ret = self.docker.wait(container=container_id)

            logs = self.docker.logs(container=container_id)
            write(logs)
        except:
            write(traceback.format_exc())
            raise
        finally:
            self.docker.remove_container(container=container_id)

        if ret['StatusCode'] != 0:
            raise PkrException(
                'Container exited with non-zero status code {}'.format(ret))
