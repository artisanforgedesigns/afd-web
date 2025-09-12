#!/bin/bash 

sleep 30

# Check for internet connectivity
if ping -c 3 -W 5 8.8.8.8 > /dev/null 2>&1; then
    echo "Internet connectivity detected - wifi-connect not needed"
    exit 0
else
    echo "No internet connectivity - starting wifi-connect"
    /usr/local/sbin/wifi-connect --portal-ssid PiLock
fi