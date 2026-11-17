Port 5222
AuthorizedKeysCommand /ssh/akeycmd.sh
AuthorizedKeysCommandUser nobody
HostKey $PWD/ssh_host_rsa_key
PidFile $PWD/sshd.pid

# Without PAM, a locked root password also prevents SSH key authentication.
# Enable PAM to allow key authentication even when the root password is locked.
UsePAM yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin without-password