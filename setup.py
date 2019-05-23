import imp

from setuptools import find_packages, setup


def setup_pkr():
    __version__ = imp.load_source('pkr.version',
                                  'pkr/version.py').__version__

    setup(
        name='pkr',
        version=__version__,
        description='Template engine for deploying docker containers.',
        keywords='docker template deployment',
        author='Altair Engineering',
        author_email='pclm-team@altair.com',
        url='https://github.com/altairengineering/pkr',
        entry_points={
            'console_scripts': [
                'pkr = pkr.__main__:main',
            ],
            'extensions': [
                'git = pkr.ext.git:Git',
                'auto-volume = pkr.ext.auto_volume:AutoVolume',
            ],
            'drivers': [
                'compose = pkr.driver.docker_compose:Driver',
                'docker_compose = pkr.driver.docker_compose:Driver',
                'k8s = pkr.driver.k8s:Driver',
                'kubernetes = pkr.driver.k8s:Driver',
                'minikube = pkr.driver.minikube:Driver',
            ],
        },
        license='AGPLv3 (See LICENSE file for terms)',
        classifiers=[
            'Intended Audience :: Developers',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Topic :: Software Development :: Build Tools',
            'Topic :: Software Development :: Testing',
            'License :: OSI Approved :: Apache Software License',
        ],
        install_requires=[
            'docker-compose==1.24.0-rc1',
            'docker==3.7.0',
            'future==0.16.0',
            'GitPython==2.1.5',
            'ipaddress==1.0.17',
            'jinja2',
            'kubernetes>=9.0.0',
            'netifaces==0.10.5',
            'paramiko == 2.4.2',
            'passlib>=1.7.1',
            'pathlib2==2.3.0',
            'pyyaml>=4.2b1,<5',
            'stevedore==1.21.0',
            'tenacity==5.0.3',
            'urllib3<1.25'
        ],
        packages=find_packages(exclude=['test', 'docs']),
        python_requires='>=2.7, !=3.0., !=3.1., !=3.2., !=3.3., !=3.4.*, '
                        '!=3.5.*, <4,',
    )


if __name__ == '__main__':
    setup_pkr()
