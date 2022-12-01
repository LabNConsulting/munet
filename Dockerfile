FROM ubuntu:20.04

ENV LANG=en_US.UTF-8 \
    LC_ALL="en_US.UTF-8" \
    LC_CTYPE="en_US.UTF-8"

RUN apt-get update -qy && apt-get dist-upgrade -y && \
    apt-get install -y apt-transport-https dirmngr software-properties-common curl && \
    # Add podman
    sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_20.04/ /' > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list" && \
    curl -fL https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_20.04/Release.key | apt-key add - && \
    # Add docker.
    # curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - &&
    # add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $UNAME stable" &&
    apt-get update -qy && apt-get dist-upgrade -y && \
    # Add useful stuff for building/CI-testing
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        autoconf \
        bash \
        bash-completion \
        bison \
        bridge-utils \
        build-essential \
        clang \
        clang-9 \
        cpio \
        curl \
        flex \
        gawk \
        gdb \
        gettext \
        git \
        gperf \
        iperf \
        iproute2 \
        iputils-ping \
        jq \
        kmod \
        libedit-dev \
        libev-dev \
        libffi-dev \
        libgmp-dev \
        libssl-dev \
        libxslt-dev \
        locales \
        locales-all \
        make \
        net-tools \
        netcat-openbsd \
        pciutils \
        podman \
        python \
        python-cffi \
        python-dev \
        python3 \
        python3-cffi \
        python3-dev \
        python3-pip \
        python3-venv \
        rsync \
        snmp \
        ssh \
        systemd-coredump \
        sudo \
        tcpdump \
        tidy \
        traceroute \
        vim \
        xsltproc \
        zlib1g-dev \
        # From VPP install-dep
        autoconf \
        automake \
        build-essential \
        ccache \
        check \
        chrpath \
        clang-format \
        cmake \
        cscope \
        curl \
        debhelper \
        dh-systemd \
        dkms \
        exuberant-ctags \
        git \
        git-review \
        indent \
        lcov \
        libapr1-dev \
        libboost-all-dev \
        libconfuse-dev \
        libffi-dev \
        libmbedtls-dev \
        libnuma-dev \
        libmnl-dev \
        libssl-dev \
        libtool \
        ninja-build \
        pkg-config \
        python-all \
        python-dev \
        python3-all \
        python3-jsonschema \
        python3-ply \
        python3-setuptools \
        uuid-dev \
        # For FRR build
        bison \
        flex \
        install-info \
        libarchive-tools \
        libc-ares-dev \
        libcap-dev \
        libjson-c-dev \
        libpam0g-dev \
        libprotobuf-c-dev \
        libreadline-dev \
        libsnmp-dev \
        libsystemd-dev \
        libzmq3-dev \
        libzmq5 \
        perl \
        protobuf-c-compiler \
        python-ipaddress \
        python3-attr \
        python3-pluggy \
        python3-py \
        python3-pytest \
        python3-sphinx \
        texinfo \
        # For libyang build
        libpcre3-dev \
        # For libyang and sysrepo
        libpcre2-dev \
        swig \
        && \
    echo en_US.UTF-8 UTF-8 >> /etc/locale.gen && \
    locale-gen && \
    #pip install -U \
    #    cffi coverage cryptography docker docker-compose lxml nose        pyang pylint pysnmp \
    #    pytest pyyaml remarshal tox twine wheel && \
    pip3 install -U \
        cffi coverage cryptography                        lxml nose poetry pyang pylint pysnmp \
        pytest pyyaml remarshal tox twine wheel && \
    # Install MIBs
    apt-get install -y snmp-mibs-downloader && download-mibs

COPY . munet/
WORKDIR munet
RUN pip install .
