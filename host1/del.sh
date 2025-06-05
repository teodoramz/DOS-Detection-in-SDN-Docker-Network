# şterge porturi/bridge-uri dacă le-ai creat deja
for br in br-sw1 br-sw2 br-sw3 br-sw4 ; do
    docker exec ${br%-*} ovs-vsctl --if-exists del-br $br
done
sudo ovs-vsctl --if-exists del-port br0 veth-br-sw1
sudo ovs-vsctl --if-exists del-port br0 veth-br-sw4
