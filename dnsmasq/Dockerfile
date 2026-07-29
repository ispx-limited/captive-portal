# Debian's dnsmasq is built with nftset support, which we rely on for
# domain-based whitelisting.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends dnsmasq \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["dnsmasq"]
CMD ["--conf-file=/run/portal/dnsmasq.conf", "--keep-in-foreground", "--log-facility=-"]
