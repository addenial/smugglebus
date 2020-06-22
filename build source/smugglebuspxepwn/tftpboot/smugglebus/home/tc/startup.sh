#!/bin/sh

#this gets started with sudo from .profile in tc homedir 
#no need to call sudo again when running python

echo "Hello SmuggleBus!!"
#sudo python smugglebus.py
#/usr/local/bin/python /home/tc/smugglebus.py

echo 'Running HashSnatcher?'
/usr/local/bin/python3.4 /home/tc/hashsnatcher.py

#echo "Done. Powering off"
#sudo poweroff
