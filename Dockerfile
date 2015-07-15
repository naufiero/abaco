from alpine:3.2

RUN apk add --update musl python3 && rm /var/cache/apk/*
RUN apk add --update bash && rm -rf /var/cache/apk/*
RUN apk add --update git && rm -rf /var/cache/apk/*
ADD actors/requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
ADD abaco.conf /etc/abaco.conf

ADD actors /actors

EXPOSE 5000

CMD ["python3", "/actors/reg_api.py"]
