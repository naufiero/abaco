from alpine:3.2

RUN apk add --update musl python3 && rm /var/cache/apk/*
RUN apk add --update bash && rm -rf /var/cache/apk/*
ADD requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
ADD registration /registration

EXPOSE 5000
CMD ["python3", "/registration/api.py"]