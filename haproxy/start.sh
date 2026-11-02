#!/bin/sh
set -eu
case "${POLICY:-reactive}" in
  round_robin|static_weighted|reactive|predictive) balance=roundrobin ;;
  least_connections) balance=leastconn ;;
  *) echo "Invalid POLICY: $POLICY" >&2; exit 1 ;;
esac
sed "s/__BALANCE__/$balance/" /usr/local/etc/haproxy/haproxy.cfg.template >/tmp/haproxy.cfg
if [ "${POLICY:-reactive}" = round_robin ]; then
  sed -i 's/weight 50/weight 100/; s/weight 150/weight 100/' /tmp/haproxy.cfg
fi
haproxy -c -f /tmp/haproxy.cfg
exec haproxy -W -db -f /tmp/haproxy.cfg
