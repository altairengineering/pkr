# -*- coding: utf-8 -*-
# Copyright© 1986-2018 Altair Engineering Inc.

"""Pkr functions for handling the life cycle with k8s"""

from passlib.apache import HtpasswdFile

from .base import DOCKER_SOCK, AbstractDriver, Pkr
from ..utils import TemplateEngine, get_pkr_path, ensure_definition_matches, merge


class Driver(AbstractDriver):
    """Concrete class for k8s driver"""

    @staticmethod
    def get_docker_client(kard):
        return KubernetesPkr(kard, DOCKER_SOCK)

    @staticmethod
    def get_meta(extras, kard):
        metas = ['tag']

        default = kard.env.get('default_meta', {}).copy()
        merge(extras, default)

        return ensure_definition_matches(
            definition=metas,
            defaults=default,
            data=kard.meta)


class KubernetesPkr(Pkr):
    """K8s implementation"""

    K8S_FOLDER = 'k8s'

    def _get_registry(self):
        return self.kard.meta['registry']

    def populate_kard(self):
        data = self.kard.meta

        def read_kard_file(conf_file_name):
            conf_path = self.kard.path / conf_file_name
            return conf_path.read_text()

        def format_image(image_name):
            if 'launcher' in self.kard.meta['features']:
                pattern = '{{{{ pillar[\'registry\'] }}}}/{}:' \
                          '{{{{ pillar[\'tag\'] }}}}'
                return pattern.format(image_name)

            pattern = '{}/{}:{}'
            return pattern.format(
                self._get_registry(), image_name, self.kard.meta['tag'])

        def format_htpasswd(username, password):
            ht = HtpasswdFile()
            ht.set_password(username, password)
            return ht.to_string().rstrip()

        data.update({
            'kard_file_content': read_kard_file,
            'format_image': format_image,
            'format_htpasswd': format_htpasswd,
        })
        tpl_engine = TemplateEngine(data)

        k8s_files = self.kard.env.env.get('driver', {}).get('k8s', {}).get('k8s_files', [])

        if k8s_files is not None:
            for k8s_file in k8s_files:
                path = get_pkr_path() / k8s_file
                tpl_engine.copy(path=path,
                                origin=path.parent,
                                local_dst=self.kard.path / self.K8S_FOLDER,
                                excluded_paths=[],
                                gen_template=True)
