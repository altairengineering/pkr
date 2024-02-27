from importlib.machinery import SourceFileLoader

from setuptools import find_packages, setup


def setup_pkr():
    pkr_version = SourceFileLoader("pkr.version", "pkr/version.py").load_module()
    setup(
        name="pkr",
        version=pkr_version.__version__,
        description="Template engine for deploying docker containers.",
        long_description=open("README.md").read(),
        long_description_content_type="text/markdown",
        keywords="docker template deployment",
        author="Altair Engineering",
        author_email="pclm-team@altair.com",
        url="https://github.com/altairengineering/pkr",
        entry_points={
            "console_scripts": [
                "pkr = pkr.__main__:main",
            ],
            "pkr_extensions": [
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
            "importlib-metadata>=0.12",
            "ipaddress==1.0.17",
            "jinja2",
            "jinja2-ansible-filters==1.3.2",
            "kubernetes>=9.0.0",
            "netifaces==0.10.5",
            "passlib>=1.7.1",
            "jinja2-ansible-filters==1.3.2",
            "pybase64==1.3.1",
            "pycryptodome==3.19.0",
            "python-on-whales==0.20.2",
            "tenacity>=7.0.0",
            "bcrypt<=4.0.1",
            "pydantic<2",
            "requests==2.31.0",
            "urllib3==1.26.18",
        ],
        packages=find_packages(exclude=["test", "docs"]),
        python_requires=">=3.8, <4,",
        extras_require={
            "dev": [
                "bandit==1.7.4",
                "mock==2.0.0",
                "pytest==7.4.0",
                "tox==4.11.3",
                "wrapt==1.14.0",
            ],
        },
    )


if __name__ == "__main__":
    setup_pkr()
