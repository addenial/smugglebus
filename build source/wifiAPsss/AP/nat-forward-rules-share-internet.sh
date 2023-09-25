#!/bin/bash

#enable internet sharing-
#assuming wlan0 is connected to wireless AP with internet access 

sysctl -w net.ipv4.ip_forward=1
iptables -P FORWARD ACCEPT
#iptables --table nat -A POSTROUTING -o wlan0 -j MASQUERADE
iptables --table nat -A POSTROUTING -o wlan1 -j MASQUERADE
