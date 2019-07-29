#!/bin/bash
if [[ $EUID -ne 0 ]]; then
echo "This script must be run as root"
exit 1
fi

echo 'Enter USB device (example "/dev/sdb")'
read usbdev

#make sure drive is unmounted
umount $usbdev"1"

#wget clean tc iso
wget https://github.com/addenial/smugglebus/releases/download/1.5/tc_clean.iso.zip
unzip tc_clean.iso.zip

#image onto the flashdrive
dd if=tc_clean.iso of=$usbdev bs=1M status=progress

sleep 5

#mount the newly imaged iso
mount=/mnt/usbmnt
mkdir $mount
mount $usbdev"1" $mount
	
#read USB UUID
usbUUID=`blkid $usbdev"1" -sUUID -ovalue`

#download necessary packages
mkdir $mount/tce/optional
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/python.tcz  -P $mount/tce/optional/
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/openssl.tcz -P $mount/tce/optional/
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/ntfs-3g.tcz -P $mount/tce/optional/
	
echo "python.tcz
openssl.tcz
ntfs-3g.tcz" > $mount/tce/onboot.lst

#make home and opt folder persistent between reboots on the USB device 
echo "DEFAULT core
LABEL core
KERNEL /tce/boot/vmlinuz
INITRD /tce/boot/core.gz
APPEND quiet  waitusb=5:UUID=\"$usbUUID\" tce=UUID=\"$usbUUID\" opt=UUID=\"$usbUUID\" home=UUID=\"$usbUUID\" 
" > $mount/tce/boot/extlinux/extlinux.conf

#clone smugglebus github repository, we need to copy the home folder with the code 
git clone https://github.com/addenial/smugglebus.git
cp -r smugglebus/home/ $mount
	
#fix permissions for the tc user
chown -R 1001:staff $mount/home/tc/. 
chmod +x $mount/home/tc/startup.sh

#clean up the temp folder and unmount
umount $usbdev"1"
rmdir $mount

echo "DONE!"
