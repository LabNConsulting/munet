Port 5222
AuthorizedKeysCommand /ssh/akeycmd.sh
AuthorizedKeysCommandUser nobody
HostKey $PWD/ssh_host_rsa_key
PidFile $PWD/sshd.pid
UsePAM no
PermitEmptyPasswords yes
PermitRootLogin without-password