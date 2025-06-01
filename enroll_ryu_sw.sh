for sw in sw1 sw2 sw3; do
    docker exec $sw ovs-vsctl set-controller br-$sw tcp:10.255.255.254:6633
    docker exec $sw ovs-vsctl set-fail-mode br-$sw secure
done
