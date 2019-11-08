.. _installation:

Installation
============

Python Version
--------------

We recommend using the latest version of Python 3. Pkr supports Python 3.6
and newer and Python 2.7.

Dependencies
------------

These distributions will be installed automatically when installing Pkr.

* `docker-compose`_
* `docker`_
* `future`_
* `GitPython`_
* `ipaddress`_
* `jinja2`_
* `kubernetes`_
* `netifaces`_
* `paramiko`_
* `passlib`_
* `pathlib2`_
* `pyyaml`_
* `stevedore`_
* `tenacity`_
* `urllib3`_

.. _docker-compose: https://pypi.org/project/docker-compose/
.. _docker: https://pypi.org/project/docker/
.. _future: https://pypi.org/project/future/
.. _GitPython: https://pypi.org/project/gitpython/
.. _ipaddress: https://pypi.org/project/ipaddress/
.. _jinja2: https://pypi.org/project/jinja2/
.. _kubernetes: https://pypi.org/project/kubernetes/
.. _netifaces: https://pypi.org/project/netifaces/
.. _paramiko: https://pypi.org/project/paramiko/
.. _passlib: https://pypi.org/project/passlib/
.. _pathlib2: https://pypi.org/project/pathlib2/
.. _pyyaml: https://pypi.org/project/pyyaml/
.. _stevedore: https://pypi.org/project/stevedore/
.. _tenacity: https://pypi.org/project/tenacity/
.. _urllib3: https://pypi.org/project/urllib3/

Virtual environments
--------------------

Use a virtual environment to manage the dependencies for your project, both in
development and in production.

What problem does a virtual environment solve? The more Python projects you
have, the more likely it is that you need to work with different versions of
Python libraries, or even Python itself. Newer versions of libraries for one
project can break compatibility in another project.

Virtual environments are independent groups of Python libraries, one for each
project. Packages installed for one project will not affect other projects or
the operating system's packages.


Create an environment with python 2
-----------------------------------

When using Python 2, the `virtualenv`_ module is not available. You need to
install it.

On Linux, virtualenv is provided by your package manager:

.. code-block:: sh

    # Debian, Ubuntu
    $ sudo apt-get install python-virtualenv

    # CentOS, Fedora
    $ sudo yum install python-virtualenv

Create a project folder and a :file:`venv` folder within:

.. code-block:: sh

    $ mkdir myproject
    $ cd myproject
    $ python2 -m virtualenv venv

.. _virtualenv: https://virtualenv.pypa.io/

Create an environment with python 3
-----------------------------------

Python 3 comes bundled with the :mod:`venv` module to create virtual
environments.

Create a project folder and a :file:`venv` folder within:

.. code-block:: sh

    $ mkdir myproject
    $ cd myproject
    $ python3 -m venv venv


Activate the environment
~~~~~~~~~~~~~~~~~~~~~~~~

Before working on your project, activate the corresponding environment:

.. code-block:: sh

    $ . venv/bin/activate


Your shell prompt will change to show the name of the activated environment.

Install Pkr
-----------

pkr requires gcc and the python-devel libraries.

.. code-block:: sh

    # Debian, Ubuntu
    $ sudo apt-get install gcc python-dev

    # CentOS, Fedora
    $ sudo yum install gcc python-devel

Within the activated environment, use the following command to install Pkr:

.. code-block:: sh

    $ pip install pkr

Pkr is now installed. Check out the :doc:`/quickstart`.

Install Docker
--------------

See https://docs.docker.com/install/
