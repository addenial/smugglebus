#!/bin/bash

###pi2pxepwn#####
#script to image raspberrypi onto sd card
#usage: (sudo) ./pi2pxepwn-flash.sh <iso> <device>
#example: (sudo) ./pi2pxepwn-flash.sh 2018-11-13-raspbian-stretch-lite.img /dev/sdb
#   assuming /dev/sdb is your sd-card


#flash pi with
#dd bs=4M if=2018-11-13-raspbian-stretch-lite.img of=/dev/sdb status=progress


if [[ $EUID -ne 0 ]]; then
echo "This script must be run as root"
exit 1
fi

if [[ $# -eq 0 ]] ; then
    echo 'Usage: (sudo) ./pi2pxepwn-flash.sh <iso> <device>
    
Example: sudo ./pi2pxepwn-flash.sh 2018-11-13-raspbian-stretch-lite.img /dev/sdb
   assuming /dev/sdb is your sd-card'
    exit 0
fi

iso=${1}
device=${2}

echo 'Flashing device...'
dd bs=4M if=$iso of=$device status=progress


echo 'Unplug the sd-card and plug back in. Hit enter when mounted'
read

#identify mount point of boot partition. typically looking for /dev/sdb1 partition
bootmnt=`mount | grep $device"1" | cut -d' ' -f 3`


echo 'Enabling SSH...'
touch $bootmnt/ssh

echo 'Configuring wifi to connect to our AP on boot...'
echo 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
ssid="wifi"
psk="password"
}' > $bootmnt/wpa_supplicant.conf

echo 'done!'
echo 'boot cycle your pi for partitions to expand to maximum available size'

exit 0

