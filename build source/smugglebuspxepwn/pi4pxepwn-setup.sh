#!/bin/bash

###pi4pxepwn#####
#setup script to convert clean image raspberrypi to smugglebux pxepwn
#usage: (sudo) ./pi4pxepwn-setup.sh

if [[ $EUID -ne 0 ]]; then
echo "This script must be run as root"
exit 1
fi


echo 'updating repos...'
apt update -y

echo 'Downloading pxepwn tftp source files...'
wget https://github.com/addenial/smugglebus/raw/master/build%20source/smugglebuspxepwn/tftpboot.7z 

echo 'Downloading tce packages, local web hosted loaded on boot...'
wget https://github.com/addenial/smugglebus/raw/master/build%20source/smugglebuspxepwn/x86.7z
wget https://github.com/addenial/smugglebus/raw/master/build%20source/smugglebuspxepwn/x86_64.7z


echo 'Downloading 7z...'
apt install p7zip-full -y

echo 'Extracting 7z files to /tftpboot'
sleep 1
7z x tftpboot.7z -o/
chown -hR pi:pi /tftpboot/
chmod -R 775 /tftpboot/


echo 'Downloading apache web server...'
apt install apache2 -y
sleep 3
echo 'Extracting web hosted tinycore packages..'
7z x x86.7z -o/var/www/html/
sleep 1
7z x x86_64.7z -o/var/www/html/
sleep 1


echo 'Seting up static IP for eth0 interface'
#echo static ip and dhcpd defaults:
echo 'hostname
clientid
persistent
option rapid_commit
option domain_name_servers, domain_name, domain_search, host_name
option classless_static_routes
option interface_mtu
require dhcp_server_identifier
slaac private
interface eth0
static ip_address=10.0.0.69/24
nolink' > /etc/dhcpcd.conf

sleep 3

echo 'Installing and setting up NFS'
apt install nfs-kernel-server -y
echo '/tftpboot/smugglebus *(rw,no_root_squash)' > /etc/exports
exportfs -a
service nfs-kernel-server restart

echo 'Installing and setting up DNSMASQ'
apt install dnsmasq -y

sleep 1

echo "interface=eth0
dhcp-range=10.0.0.101,10.0.0.200,6h
dhcp-host=`cat /sys/class/net/eth0/address`,10.0.0.69,raspberrypi,infinite
dhcp-boot=pxelinux.0
#dhcp-match=set:efi-x86_64,option:client-arch,7
#dhcp-boot=tag:efi-x86_64,bootx64.efi
enable-tftp
tftp-root=/tftpboot
no-resolv
log-queries
log-dhcp
server=1.1.1.1
#bind-interfaces" > /etc/dnsmasq.conf

#prevent dnsmasq from breaking dns resolvers for wlan0
echo 'DNSMASQ_EXCEPT=lo' >> /etc/default/dnsmasq


echo 'Restarting networking'
systemctl daemon-reload
service dhcpcd restart


sleep 4


echo 'Starting PXE server!'
service dnsmasq restart

#systemctl status dnsmasq.service
#dnsmasq -C /etc/dnsmasq.conf -d
