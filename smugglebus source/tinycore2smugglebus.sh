#!/bin/bash
echo 'Enter device mount point (example "/media/root/960fec6a-fdf0-429d-a35c-5c7f4f6af5a4")'
read mount
	
#download necessary packages
mkdir $mount/tce/optional
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/python.tcz  -P $mount/tce/optional/
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/openssl.tcz -P $mount/tce/optional/
wget http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/ntfs-3g.tcz -P $mount/tce/optional/
	
echo "python.tcz
openssl.tcz
ntfs-3g.tcz" > $mount/tce/onboot.lst

git clone https://github.com/addenial/smugglebus.git
cp -r smugglebus/home/ $mount
	
#fix permissions for the tc user
chown -R 1001:staff $mount/home/tc/. 
chmod +x $mount/home/tc/startup.sh
