cat /var/log/syslog | grep -a dnsmasq |grep "from 10.0.0.105" | cut -d"]" -f3 | cut -d" " -f2 | uniq
