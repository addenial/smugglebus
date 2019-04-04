#!/bin/bash

###pi2smugglebuspxepwn.sh#####
#setup script to convert clean image raspberrypi to smugglebux pxepwn

##once rasbian is flashed, ideally only this sigle bash script will need to be ran to set everything up 
#update wiki on how to run this on raspbian-stretch-lite imaged sd card
#by mounting imaged sd and dropping a shell script in rootfs partition 
#	 goal is we want to set this up without having to use a montior

#flash pi with
#dd bs=4M if=2018-11-13-raspbian-stretch-full.img of=/dev/sdb status=progress


if [[ $EUID -ne 0 ]]; then
echo "This script must be run as root"
exit 1
fi

#assuming clean image pi
#enable ssh
#touch /boot/ssh

#configure the pi to connect to wifi hot spot on boot. 
#so it gets internet and allow us to connect in
#...this doesn't work, conf doesn't get picked up from boot folder
#echo 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
#update_config=1
#country=US
#
#network={
#ssid="Wifi2.4"
#psk="password"
#key_mgmt=WPA-PSK
#}' > /boot/wpa_supplicant.conf






#download source files pxe and smugglebus files
wget https://github.com/addenial/smugglebus/blob/master/build%20source/smugglebuspxepwn/tftpboot.7z 
echo 'Extracting 7z files to /tftpboot'
7z x tftpboot.7z -o/

echo 'Seting up static IP for eth0 interface'
#first line assumping pi
echo 'source-directory /etc/network/interfaces.d
auto eth0
iface eth0 inet static
address 10.0.0.69/24' > /etc/network/interface
echo 'Restarting networking'
systemctl restart networking.service

echo 'Installing and setting up NFS'
apt install nfs-kernel-server -y
echo '/tftpboot/smugglebus *(rw,no_root_squash)' > /etc/exports
exportfs -a
service nfs-kernel-server start

echo 'Installing and setting up DNSMASQ'
apt install dnsmasq -y

echo "interface=eth0
dhcp-range=10.0.0.101,10.0.0.200,6h
dhcp-host=`cat /sys/class/net/eth0/address`,10.0.0.69,raspberrypi,infinite
dhcp-boot=pxelinux.0
enable-tftp
tftp-root=/tftpboot
no-resolv
bind-interfaces" > /etc/dnsmasq.conf

echo 'Starting PXE server!'
dnsmasq -C /etc/dnsmasq.conf -d
