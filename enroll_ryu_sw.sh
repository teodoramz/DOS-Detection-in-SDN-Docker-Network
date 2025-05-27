for sw in sw1 sw2 sw3; do
    docker exec $sw ovs-vsctl set-controller br-$sw tcp:127.0.0.1:6633
    docker exec $sw ovs-vsctl set-fail-mode br-$sw secure
done
