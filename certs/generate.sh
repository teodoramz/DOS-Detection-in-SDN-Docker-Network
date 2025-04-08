#!/bin/bash

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ./ssl/cyberstuff.key -out ./ssl/cyberstuff.crt \
  -config openssl.cnf

