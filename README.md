# SmuggleBus
![alt text](https://raw.githubusercontent.com/addenial/smugglebus/logo.png)
SmuggleBus is a USB bootable tool, built on barebones Linux, designed to aid penetration testers and red teamers performing physical social engineering exercises. 

Upon obtaining physical premises access to the target organization, the SmuggleBus can be used to aid in collection of local credentials and implanting backdoors. This is accomplished by taking advantage of unencrypted system hard drives. 

A typical attack flow would consist of the following:

	- Pentester obtains a physical access and identifies a desktop system not in use
            - unattended, conference room, or kiosk 
	- The pentester shutsdown the target system and boots into the SmuggleBus
	- In seconds, SmuggleBus will then:
		- Find and mount the unencrypted system hard drive
		- Copy local hives (SAM, SYSTEM, SECURITY, SOFTWARE) onto the SmuggleBus.
                - Uses a combination of symmetric and asymmetric cryptography to encrypt files prior writing to flashdrive storage (optional)
		- Implant a payload (Meterpreter, Empire, or Cobalt Strike), configured to run as SYSTEM. 
		- The SmuggleBus will then safely shutdown and return to the standard Windows OS boot. 
	- Upon boot the system executes the payload.  Any uploaded or modified files get cleaned up.



## Operating System
The SmuggleBus is built on Tiny Core Linux OS (http://distro.ibiblio.org/tinycorelinux), with only the essential packages loaded in. No networking is loaded to avoid tripping any Network Access Controls. 

Refer to wiki for detailed build instructions or download premade ISO from releases (link)

When imaged, the following will reside in the SmuggleBus home folder under /home/tc/:

| File | Description |
| --- | --- |
|startup.sh| Executed on boot. Launches smugglebus.py script, restarts the system upon completion.|
|smugglebus.py|	Python code that will identify, mount the Windows OS partition, export the hashes, and setup the backdoor. (Based on HashGrab v2.0 by s3my0n, under GNU General Public License)|
|public_key.pem| Public key used to encrypt the exported hives prior to writing to flash memory. Optional, encrypts if file exists. |
|payload| Placeholder location for the backdoor implant files (spoolsv.exe and start.exe)|
|reged|	Registry editor, export and import tool. (*Placeholder, not used in current version. Part of chntpw, the Offline Windows Password Editor, under GNU Lesser General Public License https://github.com/rescatux/chntpw)|
|.profile| Used to Launch startup.sh when TinyCore is fully loaded|


## Encryption
Using a combination of symmetric and asymmetric cryptography, files get encrypted prior being written to flashdrive storage. 

Setup:

    1. Generate RSA public/private key pair ./generate_keys.sh
    2. Copy the public key onto the SmuggleBus home directory /home/tc/public_key.pem
		
Execution Workflow:

	1. SmuggleBus generates a random 32 byte value (symmetric-key)
	2. The symmetric-key is used to AES 256 encrypt the collected registry hives
	3. Public key is used to encrypt the symmetric-key
	4. Once ran, new folder will be created in home directory, containing:
		- SAM.enc
		- SYSTEM.enc
		- SECURITY.enc
		- SOFTWARE.enc
		- KEY.enc

Decryption:

    1. Private key is used to decrypt the symmetric-key
    2. Decrypted symmetric-key is used to decrypt the registry hives ./decrypt.sh [arguments]
		
		Required arguments:
			-i DIRECTORY    Directory with SAM/SYSTEM/SECURITY & key.enc files    
			-o DIRECTORY    Output location                                       
			-p FILE         Private key location                                  
		Optional arguments:
			-x              Run secretsdump.py when done (Default: False) 
		
		
## Backdoor Implant
The design goal of the SmuggleBus payload injection was to have minimal impact on the targeted system. Any added or modified files get cleaned-up upon successful execution. 

Since pentesters often times will target machines onto which users rarely log into (conference room PCs, kiosks, etc.) the payload needs to execute prior to user logon with "NT AUTHORITY\SYSTEM" account. Due to security updates/enhancements of modern Windows Operating Systems, service implant technique is used for all flavors of Windows. 

### Service
The service backdoor implant works by swapping a Windows service binary with attacker's binary. Use generate_payload.sh to create spoolsv.exe implant and choose a URL where web-hosted-stage.txt will be hosted. When executed, the web hosted stage will create two scheduled tasks via PowerShell: a payload task, and a clean-up task. Save the newly created spoolsv.exe in the "/home/tc/payload" folder. 


By default, the payload task will attempt to execute "%appdata%\start.exe", which SmuggleBus uploads from "/home/tc/payload" folder to "C:\Windows\System32\config\systemprofile\AppData\Roaming\start.exe" (SYSTEM profile %appdata% folder). THIS IS YOUR REVERSE SHELL BINARY (Metasploit, Empire, Cobalt Strike, etc.) which could potentially get flagged by AV. Uploading a compiled binary and since scheduled task is being configured to execute a file that is already residing on disk is the perfered method to go undetected.


The following is the execution flow:
	1. Backdoor is injected
		• Offline drive, "spoolsv.exe" is renamed to "spoolsv.exe.bak"
		• Hacked spoolsv.exe is uploaded
		• Reverse shell binary start.exe is uploaded
	2. System reboots, hacked spoolsv.exe executes
		• Configured to execute a web hosted PowerShell code that create two scheduled tasks
	3. New Scheduled Task is created (payload)
		• Executes start.exe as SYSTEM 
	4. 2nd task is created (clean-up)
		• Cleans up the scheduled tasks
		• Deletes hacked spoolsv.exe and restores original exe
		• Fixes temporarily modified service permissions
		• Service is started, resumes normal operation


# Build Instructions Quick Reference
Refer to wiki for detailed build instructions or download premade ISO from releases (link)

1. Download Core Plus from http://www.tinycorelinux.net/downloads.html
2. Install Tinycore to a USB flashdrive,
    - Use Ext2 as the partition
    - Select “Core Only” for the installation
3. Mount the flash drive into a linux distribution
4. Open boot/extlinux/extlinux.conf in an editior
5. Copy your UUID from the last line and append home=UUID=”YOUR UUID” and opt=UUID=”YOUR UUID”. This should all be on one line
    - Example: 
    APPEND initrd=/boot/core.gz quiet norestore waitusb=5:UUID="a13c5174-bde8-48f2-ac19-d9a6b73bb7c5" tce=UUID="a13c5174-bde8-48f2-ac19-d9a6b73bb7c5" home=UUID="a13c5174-bde8-48f2-ac19-d9a6b73bb7c5" opt=UUID="a13c5174-bde8-48f2-ac19-d9a6b73bb7c5"
6. Download Python, OpenSSL, and NTFS-3G tcz packages (python.tcz, openssl.tcz, ntfs-3g.tcz) from http://distro.ibiblio.org/tinycorelinux/8.x/x86/tcz/
7. Place Python, OpenSSL, and NTFS-3G inside /tce/optional
8. Edit OnBoot.lst and add the entries, separated by a new line:
    - python.tcz 
    - openssl.tcz
    - ntfs-3g.tcz
9. Overwrite tc folder with the one in github (/home/tc)
