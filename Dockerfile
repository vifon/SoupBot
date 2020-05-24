FROM ubuntu:eoan

RUN adduser --disabled-password --gecos '' app
WORKDIR /home/app

ADD requirements*.txt /home/app/

RUN apt-get update -y \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip \
 && apt-get -y clean \
 && pip3 install -r requirements.txt -r /home/app/requirements-plugins.txt

RUN chown -R app:app /home/app

USER app
ADD . /home/app

RUN ./setup.py install

CMD ["/usr/bin/python3", "soupbot", "./config.yml"]
