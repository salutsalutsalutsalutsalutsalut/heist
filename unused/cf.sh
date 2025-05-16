#!/bin/bash

# Reset iptables
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow loopback traffic
iptables -A INPUT -i lo -j ACCEPT

# Allow SSH (port 22)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Download Cloudflare IP ranges
CLOUDFLARE_IPS_V4=$(curl -s https://www.cloudflare.com/ips-v4)
CLOUDFLARE_IPS_V6=$(curl -s https://www.cloudflare.com/ips-v6)

# Allow Cloudflare IPs to port 3000 (IPv4)
for ip in $CLOUDFLARE_IPS_V4; do
    iptables -A INPUT -p tcp --dport 3000 -s $ip -j ACCEPT
done

# Allow Cloudflare IPs to port 3001 (IPv4)
for ip in $CLOUDFLARE_IPS_V4; do
    iptables -A INPUT -p tcp --dport 3001 -s $ip -j ACCEPT
done

# Allow Cloudflare IPs to port 3000 (IPv6)
for ip in $CLOUDFLARE_IPS_V6; do
    ip6tables -A INPUT -p tcp --dport 3000 -s $ip -j ACCEPT
done

# Allow Cloudflare IPs to port 3001 (IPv6)
for ip in $CLOUDFLARE_IPS_V6; do
    ip6tables -A INPUT -p tcp --dport 3001 -s $ip -j ACCEPT
done

# Block all other traffic to port 3000
iptables -A INPUT -p tcp --dport 3000 -j DROP

# Block all other traffic to port 3001
iptables -A INPUT -p tcp --dport 3001 -j DROP

# Save iptables rules
iptables-save > /etc/iptables/rules.v4
ip6tables-save > /etc/iptables/rules.v6