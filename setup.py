import imp

from setuptools import find_packages, setup


def setup_pkr():
    __version__ = imp.load_source("pkr.version", "pkr/version.py").__version__

    setup(
        name="pkr",
        version=__version__,
        description="Template engine for deploying docker containers.",
        keywords="docker template deployment",
        author="Altair Engineering",
        author_email="pclm-team@altair.com",
        url="https://github.com/altairengineering/pkr",
        entry_points={
            "console_scripts": [
                "pkr = pkr.__main__:main",
            ],
            "pkr_extensions": [
                "git = pkr.ext.git:Git",
                "auto-volume = pkr.ext.auto_volume:AutoVolume",
                "basic-template = pkr.ext.basic_template:BasicTemplate",
            ],
        },
        license="AGPLv3 (See LICENSE file for terms)",
        classifiers=[
            "Intended Audience :: Developers",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Topic :: Software Development :: Build Tools",
            "Topic :: Software Development :: Testing",
            "License :: OSI Approved :: Apache Software License",
        ],
        install_requires=[
            "docker==4.4.4",
            "GitPython==3.1.30",
            "ipaddress==1.0.17",
            "jinja2",
            "kubernetes>=9.0.0",
            "netifaces==0.10.5",
            "passlib>=1.7.1",
            "jinja2-ansible-filters==1.3.2",
            'importlib-metadata>=0.12;python_version<"3.8"',
            'python-on-whales==0.20.2;python_version>="3.8"',
            "pybase64==1.3.1",
            "pycryptodome==3.19.0",
        ],
        packages=find_packages(exclude=["test", "docs"]),
        python_requires=">=3.8, <4,",
    )


if __name__ == "__main__":
    setup_pkr()
