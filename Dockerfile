# Image: abaco/core

from alpine:3.2

RUN apk add --update musl python3 && rm /var/cache/apk/*
RUN apk add --update bash && rm -f /var/cache/apk/*
RUN apk add --update git && rm -f /var/cache/apk/*
RUN apk add --update g++ -f /var/cache/apk/*
RUN apk add --update python3-dev -f /var/cache/apk/*
ADD actors/requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
ADD abaco.conf /etc/abaco.conf
RUN touch /var/log/abaco.log

ADD actors /actors
RUN chmod +x /actors/health_check.sh

ADD entry.sh /entry.sh
RUN chmod +x /entry.sh

EXPOSE 5000

CMD ["./entry.sh"]
