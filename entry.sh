#!/bin/bash

if [ $api = "reg" ]; then
    if [ $server = "dev" ]; then
        python3 -u /actors/reg_api.py
    else
        /usr/local/bin/gunicorn -w 2 -b :5000 reg_api:app
    fi
elif [ $api = "admin" ]; then
    if [ $server = "dev" ]; then
        python3 -u /actors/admin_api.py
    else
        /usr/local/bin/gunicorn -w 2 -b :5000 admin_api:app
    fi
elif [ $api = "mes" ]; then
    if [ $server = "dev" ]; then
        python3 -u /actors/mes_api.py
    else
        /usr/local/bin/gunicorn -w 2 -b :5000 mes_api:app
    fi
fi

sleep infinity