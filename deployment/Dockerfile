FROM python:3.11-slim-bookworm AS builder

ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:${PATH}"
ENV PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"

WORKDIR /build

RUN python -m venv /venv \
    && pip install --no-cache-dir --upgrade "pip>=26.1" "wheel>=0.46.2" "setuptools>=80"

COPY requirements-runtime.txt /build/requirements-runtime.txt
RUN pip install --no-cache-dir -r /build/requirements-runtime.txt


FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:${PATH}"
ENV PYTHONPATH="/app:/app/holmes"

WORKDIR /app

# HolmesGPT 的 bash/network 工具集会调用这些系统命令。使用阿里云 Debian
# 镜像，避免境内服务器访问 deb.debian.org 时长时间阻塞。
RUN sed -i \
        -e 's|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
        -e 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        coreutils \
        curl \
        dnsutils \
        findutils \
        gawk \
        git \
        grep \
        gzip \
        jq \
        librdkafka1 \
        sed \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
ARG KUBECTL_VERSION=1.37.0-1.1
ARG KUBECTL_SHA256=c0ad376d20120f876b9846232795277f7c1a4f004702fd40117ae6456949e056

# 保留 HolmesGPT 最核心的 Kubernetes 诊断客户端。服务器到 Google
# Storage 不稳定，因此使用阿里云镜像中的官方 deb，并固定 SHA-256。
RUN curl -fsSLo /tmp/kubectl.deb \
        "https://mirrors.aliyun.com/kubernetes-new/core/stable/v1.37/deb/${TARGETARCH}/kubectl_${KUBECTL_VERSION}_${TARGETARCH}.deb" \
    && echo "${KUBECTL_SHA256}  /tmp/kubectl.deb" | sha256sum -c - \
    && dpkg-deb -x /tmp/kubectl.deb /tmp/kubectl-root \
    && install -m 0755 /tmp/kubectl-root/usr/bin/kubectl /usr/local/bin/kubectl \
    && rm -rf /tmp/kubectl.deb /tmp/kubectl-root \
    && kubectl version --client

COPY --from=builder /venv /venv
COPY app/holmes /app/holmes
COPY app/server.py /app/server.py
COPY app/holmes_cli.py /app/holmes_cli.py

# macOS 复制目录时可能生成 AppleDouble（._*）元数据文件。HolmesGPT 会把
# 其中以 .yaml 结尾的文件当作工具集解析，因此在镜像中做最后一道清理。
RUN find /app -name '._*' -type f -delete \
    && git config --global core.symlinks false

EXPOSE 5050
ENTRYPOINT ["python", "-u", "server.py"]
