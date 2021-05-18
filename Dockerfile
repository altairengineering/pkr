### BUILDER ###
ARG PYTHON_VERSION=3.7-alpine3.12
FROM python:${PYTHON_VERSION} as builder

WORKDIR /wheels
RUN \
  apk add --no-cache --upgrade \
  build-base linux-headers libxml2-dev libxslt-dev libffi-dev openssl-dev

COPY requirements.txt /wheels/
RUN \
  pip wheel --no-cache-dir -r ./requirements.txt

### IMAGE ###
FROM python:${PYTHON_VERSION}

ENV TZ=UTC
ENV PS1='\h:\w\$ '
ENV PKR_PATH=/pkr
RUN \
  echo "alias ll='ls -al'" >> ~/.bashrc \
  && echo -e "\"\\e[1~\": beginning-of-line\n\"\\e[4~\": end-of-line" >> ~/.inputrc

RUN \
  apk add --no-cache --upgrade bash curl docker-cli git \
  && rm -rf /var/cache/apk/*

WORKDIR $PKR_PATH
COPY --from=builder /wheels /wheels
COPY pkr $PKR_PATH/pkr
COPY setup.py requirements.txt $PKR_PATH/

RUN \
  pip3 install --no-cache-dir -r /wheels/requirements.txt -f /wheels \
  && pip3 install --no-cache-dir .

# COPY your environment here (or use volume)
#COPY env $PKR_PATH/env
#COPY templates $PKR_PATH/templates

VOLUME $PKR_PATH/kard

CMD pkr
