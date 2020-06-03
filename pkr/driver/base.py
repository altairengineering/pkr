# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Docker base object"""
from __future__ import print_function

import re
import sys
import traceback
from collections import namedtuple
from builtins import object

import docker
import tenacity

from pkr.cli.log import write
from pkr.utils import PkrException, get_timestamp

DOCKER_SOCK = 'unix://var/run/docker.sock'


class ImagePullError(PkrException):
    """Raise when error occurs while pulling image"""


class DockerRegistry(namedtuple('DockerRegistry',
                                ('url', 'username', 'password'))):
    """A Docker registry representation

    Args:
      * url: the URL of the registry
      * username: the username for authenticating on the registry
      * password: the password for authenticating on the registry
    """


class AbstractDriver(object):
    """Abstract class for a driver"""

    @staticmethod
    def get_docker_client(kard):
        """Return a driver instance"""

    @staticmethod
    def get_meta(extras, kard):
        """Ensure that the required meta are present.

        Args:
          * extras(dict): extra values
          * kard: the current kard
        """


class Pkr(object):
    """Calls the docker Client class and add extra features for pkr."""

    SERVICE_VAR = '%SERVICE%'

    def __init__(self, kard, *args, **kwargs):
        self.docker = docker.APIClient(*args, version='auto', **kwargs)
        self.kard = kard

    def get_registry(self, **kwargs):
        """Return a DockerRegistry instance with either the provided values, or
        those present in the meta.
        """
        for var in ('url', 'username', 'password'):
            if var not in kwargs and var in self.kard.meta:
                kwargs[var] = self.kard.meta[var]

        return DockerRegistry(**kwargs)

    def make_container_name(self, name):
        """Return the container name formatted with the pattern in metas."""
        container_pattern = self.kard.meta.get(
            'container_pattern', self.SERVICE_VAR)
        return container_pattern.replace(self.SERVICE_VAR, name)

    def rename_old_image(self, name_tag):
        """If an image with the given name/tag already exists in Docker
        and it has no other tag associated,
        rename it by appending the current timestamp.
        This helps to keep the name information for eventual cleanup"""
        images = self.docker.images(name_tag)
        if images and len(images[0]['RepoTags']) == 1:
            (name, _) = name_tag.split(':')
            self.docker.tag(
                name_tag, name, '{}-{}'.format(name, get_timestamp()))
            # Remove the former tag, otherwise we cannot tag another image
            self.docker.remove_image(name_tag)  # will only "untag" now

    def make_image_name(self, service, tag=None):
        """Return the image name formatted with the pattern in metas."""
        image_pattern = self.kard.meta.get('image_pattern', self.SERVICE_VAR)
        image_name = image_pattern.replace(self.SERVICE_VAR, service)
        if tag is not None:
            image_name = ':'.join((image_name, tag))
        return image_name

    def build_images(self, services, tag=None, verbose=True, logfile=None):
        """Build docker images.

        Args:
          * services: the name of the images to build
          * tag: the tag on which the image will be saved
          * verbose: verbose logs
        """
        with LogOutput(logfile) as logfh:
            if tag is None:
                tag = self.kard.meta['tag']

            if len(services) > 1:
                logfh.write('Building docker images...\n')

            ctx = self.kard.context
            for service in services:
                image_name = self.make_image_name(service, tag)
                logfh.write('Building {} image...\n'.format(image_name))

                dockerfile = self.kard.env.get_container(service)['dockerfile']

                stream = self.docker.build(
                    path=str(ctx.path),
                    dockerfile=str(ctx.relative(dockerfile)),
                    tag=image_name,
                    decode=True,
                    forcerm=True)

                self.print_docker_stream(
                    stream, verbose=verbose, logfile=logfile)

                logfh.write('done.\n')

    def _logon_remote_registry(self, registry):
        """Push images to a remote registry

        Args:
          * registry: a DockerRegistry instance
        """
        write('Logging to {}...'.format(registry.url))
        self.docker.login(username=registry.username,
                          password=registry.password,
                          registry=registry.url)

    def push_images(self, services, registry, tag=None, other_tags=None):
        """Push images to a remote registry

        Args:
          * services: the name of the images to push
          * registry: a DockerRegistry instance
          * tag: the tag of the version to push
        """
        if registry.username is not None:
            self._logon_remote_registry(registry)

        tags = [tag]
        tags.extend(other_tags)

        for service in services:
            image = self.make_image_name(service)
            rep_tag = '{}/{}'.format(registry.url, image)

            if tag != 'latest':
                image = ':'.join([image, tag])

            for dest_tag in tags:
                write('Pushing {} to {}:{}'.format(image, rep_tag, dest_tag))
                sys.stdout.flush()

                try:
                    self.docker.tag(
                        image=image,
                        repository=rep_tag,
                        tag=dest_tag,
                        force=True)

                    ret = self.docker.push(
                        repository=rep_tag,
                        tag=dest_tag,
                        decode=True,
                        stream=True)

                    error = ''
                    for stream in ret:
                        if 'error' in stream:
                            error += '\n' + stream['errorDetail']['message']

                    write(' Done !')
                except docker.errors.APIError as error:
                    error_msg = '\nError while pushing the image {}: {}\n'.format(
                    tag, error)
                    raise error

    def pull_images(self, services, registry, tag=None):
        """Pull images from a remote registry

        Args:
          * services: the name of the images to pull
          * registry: a DockerRegistry instance
          * tag: the tag of the version to pull
        """

        if registry.username is not None:
            self._logon_remote_registry(registry)

        for service in services:
            image_name = self.make_image_name(service)
            image = image_name if tag == 'latest' \
                else ':'.join((image_name, tag))

            write('Pulling {} from {}...'.format(image, registry.url))
            sys.stdout.flush()

            self._pull_image(image_name, registry.url, tag)

            write(' Done !' + '\n')

        write('All images has been pulled successfully !' + '\n')

    @tenacity.retry(
        wait=tenacity.wait_fixed(1),
        stop=tenacity.stop_after_attempt(3),
        reraise=True,
        retry=tenacity.retry_if_exception_type(ImagePullError),
    )
    def _pull_image(self, image_name, registry_url, tag):
        """
        Pull one image, retry few times to be robust to registry or network
        related issues.
        Usually, if an attempt fails, the next one will succeed.

        Args:
          * image_name: the name of the image to pull
          * registry_url: the DockerRegistry instance url
          * tag: the tag of the version to pull
        """

        rep_tag = '{}/{}'.format(registry_url, image_name)

        try:
            self.docker.pull(repository=rep_tag,
                             tag=tag)

            # Strip the repository tag
            self.docker.tag(image=':'.join((rep_tag, tag)),
                            repository=image_name,
                            tag=tag,
                            force=True)

        except docker.errors.APIError as error:
            error_msg = 'Error while pulling the image {}: {}'.format(
                tag, error)
            write(error_msg)
            raise ImagePullError(error_msg)

    def start(self, services):
        """Starts services

        Args:
          * services: a list with the services name to start
        """
        raise NotImplementedError()

    def execute(self, container_name, *args):
        """Execute a command on a container

        Args:
          * container_name: the name of the container
          * *args: the command, like 'ps', 'aux'
        """
        raise NotImplementedError()

    @staticmethod
    def print_docker_stream(stream, verbose=True, logfile=None):
        """Util method to print docker logs"""
        with LogOutput(logfile) as logfh:
            log_keys = set(('status', 'stream'))
            all_logs = []
            last_log_id = [None]

            def print_log(log):
                for key in (log_keys & set(log)):
                    try:
                        if key == 'status' and log.get(key) in (
                                'Downloading', 'Extracting'):
                            status_id = log.get('id')

                            if last_log_id[0] is None:
                                last_log_id[0] = status_id
                            if last_log_id[0] != status_id:
                                last_log_id[0] = status_id
                                logfh.writeln(log['progress'])
                            else:
                                logfh.write_console(log['progress'] + '\r')
                        else:
                            logfh.write_console('\n')
                            logfh.writeln(log.get(key))
                    except:
                        write(traceback.format_exc())
                        raise

            for log in stream:
                last_logs = []
                if log is None:
                    continue

                if isinstance(log, list):
                    last_logs.extend(log)
                    all_logs.extend(log)
                else:
                    last_logs.append(log)
                    all_logs.append(log)

                for last_log in last_logs:
                    if verbose:
                        print_log(last_log)

                    # Catch errors
                    if 'error' in last_log:
                        for log_it in all_logs:
                            print_log(log_it)
                        raise Exception('Error during docker process: ' +
                                        last_log['errorDetail']['message'])

    def purge(self, except_tag=None, tag=None, repository=None):
        """Delete all images of this project.

        Only tag or except_tag can be specified simultaneously.

        Args:
          * except_tag: delete all image but this tag
          * tag: only delete this tag
          * repository: delete image reference in a specified repository
        """
        services = list(self.kard.env.get_container().keys())
        if except_tag is None:
            tag = tag or self.kard.meta['tag']
        else:
            tag = '(?!{})$'.format(except_tag)

        images_to_del = [self.make_image_name(s, '*') for s in services]

        if repository:
            tmp = []
            for image in images_to_del:
                tmp.append(image)
                tmp.append('/'.join((repository, image)))
            images_to_del = tmp

        images_regex = '(' + ')|('.join(images_to_del) + ')'

        for img in self.docker.images():
            for repo_tag in img.get('RepoTags', []):
                if re.match(images_regex, repo_tag):
                    write('Deleting image ' + repo_tag)
                    try:
                        self.docker.remove_image(repo_tag)
                    except BaseException as exc:
                        write(exc.message)


class LogOutput(object):

    def __init__(self, filename=None):
        """Context manager for writing to files or to stdout."""
        if filename is None:
            self.handler = sys.stdout
        else:
            self.handler = None
            self.filename = filename

    def __enter__(self):
        if self.handler != sys.stdout:
            self.handler = open(self.filename, 'a')
        return self

    def __exit__(self, *_):
        if self.handler != sys.stdout:
            self.handler.close()
            self.handler = None

    def write(self, line):
        """Write a string to the configured output."""
        print(line, file=self.handler, end='')
        self.handler.flush()

    def writeln(self, line):
        """Write a string followed by a newline to the configured output."""
        print(line, file=self.handler)
        self.handler.flush()

    def write_console(self, line):
        """Write the string only when it's connected to a console."""
        if self.handler == sys.stdout:
            print(line, file=self.handler, end='')
