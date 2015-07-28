# Image: jstubbs/abaco_agave_test

from alpine:3.2

RUN apk add --update musl python && rm /var/cache/apk/*
RUN apk add --update musl py-pip && rm /var/cache/apk/*
RUN apk add --update bash && rm -f /var/cache/apk/*
RUN apk add --update git && rm -f /var/cache/apk/*

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD test.py /test.py

CMD ["python", "/test.py"]
