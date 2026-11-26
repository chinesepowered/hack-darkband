#!/usr/bin/env bash
# Environment step for a machine behind a TLS-intercepting egress proxy (our cloud build box).
#
# Containers there reach the internet through a proxy whose CA they don't trust, so any
# Dockerfile that downloads packages (pip, apk, playwright) fails, including the event's
# own mock web and test runner. This rebuilds this machine's local copies of common base
# images with the proxy's CA added, under their usual tags. Every Dockerfile then builds
# unmodified here; nothing in a submission changes, and other machines use the real images.
#
#   scripts/trust-proxy-ca.sh [/path/to/ca-bundle.crt] [image ...]
set -euo pipefail
CA=${1:-/root/.ccr/ca-bundle.crt}
shift || true
IMAGES=("$@")
[ ${#IMAGES[@]} -gt 0 ] || IMAGES=(python:3.12-slim python:3.12-alpine python:3.12 python:3.12-slim-bookworm python:3.13-slim python:3.11-slim)
ctx=$(mktemp -d); trap 'rm -rf "$ctx"' EXIT
cp "$CA" "$ctx/proxy-ca.crt"
for image in "${IMAGES[@]}"; do
  docker pull -q "$image" >/dev/null
  if docker image inspect "$image" --format '{{index .Config.Labels "onsen.proxy-ca"}}' | grep -q yes; then
    echo "$image: already trusts the proxy CA"; continue
  fi
  digest=$(docker image inspect "$image" --format '{{index .RepoDigests 0}}')
  cat > "$ctx/Dockerfile" <<DOCKERFILE
FROM $digest
COPY proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt
RUN cat /usr/local/share/ca-certificates/proxy-ca.crt >> /etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/proxy-ca.crt
LABEL onsen.proxy-ca=yes onsen.base=$digest
DOCKERFILE
  docker build -q -t "$image" "$ctx" >/dev/null
  echo "$image: trusts the proxy CA (from $digest)"
done
