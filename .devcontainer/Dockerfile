FROM mcr.microsoft.com/devcontainers/base@sha256:bb7b81b6e5be17b5267f92f4ffda534fea37dab1df97b5e86c1f9b91da5c0b5d

# The official Codespaces CLI requires a server inside the container. Install
# only the public package; Codespaces manages its tunnel and authentication.
USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        openssh-server=1:9.2p1-2+deb12u10 \
    && rm -f /etc/ssh/ssh_host_* \
    && rm -rf /var/lib/apt/lists/*
USER vscode
