FROM python:3.9-slim-bullseye

ARG item

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN mkdir /sms_rpc_check_app/
COPY sms_rpc_check_app/ /sms_rpc_check_app/
COPY requirements.txt  /sms_rpc_check_app/

RUN pip3 install -r /sms_rpc_check_app/requirements.txt
RUN pip3 install --upgrade pip

WORKDIR /sms_rpc_check_app/

ADD startup.sh .
RUN chmod +x ./startup.sh

ENTRYPOINT ["bash","startup.sh"]
