# PKR

[![Build Status](https://travis-ci.org/altairengineering/pkr.svg?branch=master)](https://travis-ci.org/altairengineering/pkr)

[![Documentation Status](https://readthedocs.org/projects/pkr/badge/?version=latest)](https://pkr.readthedocs.io/en/latest)

# Introduction
This repository provide a tool which allows generating docker images using templates.

`pkr` comes from `pocker`, which was the first name of this software.


# How to use pkr ?

To learn how to use pkr, you can have a look at our examples [here](https://github.com/altairengineering/pkr-demo).


# Docker installation

See https://docs.docker.com/install/

# pkr installation


## Install required packages

pkr requires gcc and the python-devel libraries.


## Install the environment

1. Install its system dependencies

    ```
    yum install epel-release
    yum update
    yum install gcc python-pip python-devel
    ```
Note: you might also want to install git to automatically fetch sources from the Git repository.

3. Update pip and setuptools to their latest version

    ```
    pip install --upgrade setuptools
    pip install --upgrade pip
    ```
    

## Install with pip


Install it on your machine, or in a virtual env

    ```
    pip install pkr
    ```


## Install from the sources

1. Clone the repository

    ```
    git clone XXX
    ```

2. Install it on your machine, or in a virtual env

    ```
    cd pkr
    pip install -e .
    ```


## Using the docker image

1. Use either directly the pkr command by running the image, or via the interactive mode.
   The image has a volume for storing its Kard (See pkr documentation), and also needs to access the docker socket.

    ```
    # Direct mode
    docker run \
        -v /run/docker.sock:/run/docker.sock \ 
        -v /home/sami/pkr/kard:/pkr/kard \
        pkr:dev pkr <command>

    # Interactive mode
    docker run -ti \
        -v /run/docker.sock:/run/docker.sock \
        -v /home/sami/pkr/kard:/pkr/kard \
        pkr:dev bash
    ```


# Generate the pkr image

In the source folder, run the following command:

    docker build -t pkr:<TAG_NAME> .


