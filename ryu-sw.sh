docker exec sw1 ovs-vsctl set-controller br-sw1 tcp:10.255.255.254:6633 \
  -- set Bridge br-sw1 protocols=OpenFlow13 fail-mode=secure

docker exec sw2 ovs-vsctl set-controller br-sw2 tcp:10.255.255.254:6633 \
  -- set Bridge br-sw2 protocols=OpenFlow13 fail-mode=secure

docker exec sw3 ovs-vsctl set-controller br-sw3 tcp:10.255.255.254:6633 \
  -- set Bridge br-sw3 protocols=OpenFlow13 fail-mode=secure

docker exec sw4 ovs-vsctl set-controller br-sw4 tcp:10.255.255.254:6633 \
  -- set Bridge br-sw4 protocols=OpenFlow13 fail-mode=secure
