 tail -n 25 -f /var/log/syslog | while read line; do echo "$line" | grep -a dnsmasq ; done
