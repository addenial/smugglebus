#!/bin/sh

#this gets started with sudo from .profile in tc homedir 
#no need to call sudo again when running python

echo "Hello SmuggleBus!!"

#legacy USB python2.7 version
#python smugglebus.py
#/usr/local/bin/python /home/tc/smugglebus-legacy.py

echo 'Running HashSnatcher?'
/usr/local/bin/python3.6 /home/tc/smugglebus3.py -pd

#echo "Done. Powering off"
#sudo poweroff

