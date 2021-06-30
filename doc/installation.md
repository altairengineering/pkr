# Installation

## Use pkr from docker

You can directly use `pkr` building a docker image from source. [Docker installation](https://docs.docker.com/install/)

```
docker build -t pkr:latest .
docker run --rm -v /run/docker.sock:/run/docker.sock -v <host_pkr_dir>:/pkr pkr:latest pkr <pkr_command>
```

Interactive mode:
```
docker run --rm -it -v /run/docker.sock:/run/docker.sock -v <host_pkr_dir>:/pkr pkr:latest bash
$ pkr
```

## Python Version

We recommend using the latest version of Python 3. Pkr supports python 3.7 and newer.

## Dependencies

### System

Some system packages might be required to install pkr with pip.

  * gcc
  * python-devel (python-dev on debian)
  * python-pip (python3-pip on older releases)

## Virtual environments

Virtual environments are independent groups of Python libraries, one for each project. Packages installed for one project will not affect other projects or the operating system's packages.

You may prefer to install `pkr` in a virtualenv in order to avoid any conflict.

[Virtualenv documentation](https://docs.python.org/3/tutorial/venv.html)

[Virtualenvwrapper quickstart](https://virtualenvwrapper.readthedocs.io/en/latest/)

With both those solutions, your shell prompt will change to show the name of the activated environment.

### Install with pip

To install from published releases:
```
pip install pkr
```

To install from source:
```
git clone https://github.com/altairengineering/pkr
pip install -e ./pkr
```

### Python

Some python packages are installed alongside `pkr` as dependencies, most notably :

  * docker-compose
  * docker
  * GitPython
  * jinja2
  * kubernetes
  * pyyaml

For a complete list, please refer to [requirements file](../requirements.txt).

### Docker

`pkr` requires `docker` to be installed in order to provide docker functionnality (build images, start software, ...)

[Docker installation](https://docs.docker.com/install/)
