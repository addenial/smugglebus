tail -n 25 -f /var/log/syslog | while read line; do echo "$line" | grep -a "dnsmasq\[" |  grep -a -E "from| reply"  |  cut -d" " -f 7,9 ; done