<p align="center">
  <img src="logo.png" alt="captive-portal logo" width="280">
</p>

# captive-portal

A walled garden for broadband subscribers whose service is suspended, usually
for an unpaid bill. The BNG steers a suspended subscriber's traffic to this
box. The box answers every plain HTTP request with the pay page, lets traffic
to the payment provider through, and drops everything else. When the bill is
paid, the RADIUS platform sends a CoA and the subscriber's traffic stops
arriving here. The box keeps no per-subscriber state, so one small VM serves
tens of thousands of suspended subscribers and more boxes can be added behind
ECMP.

It was built for AuthMesh and works with any BNG and RADIUS platform that can
steer a session by CoA.

nginx, nftables and dnsmasq do the work. `portalctl` renders their
configuration from one YAML file and reloads them when it changes.

## What it does

- Intercepts HTTP from subscribers and serves your own page from `www/`, or
  redirects every request to a URL you choose. IPv4 and, with
  `portal.listen_ip6` set, IPv6.
- Lets subscribers reach the payment provider: networks you list, and domains
  that dnsmasq resolves live and feeds into the nftables whitelist sets.
- Drops everything else, including all HTTPS to other destinations. DNS over
  TLS on port 853 gets a TCP reset so strict private DNS clients fall back to
  plain DNS quickly instead of hanging.
- Answers the connectivity probes that phones, laptops and browsers send, so
  the operating system shows its sign-in sheet with the pay page in it.
- Serves the RFC 8908 Captive Portal API at `/capport` for networks that
  advertise it with DHCP option 114 or an IPv6 RA.
- Validates configuration before applying it. A bad `portal.yml` is rejected
  and the previous rules stay in force.

## Quickstart

Docker with Compose and [uv](https://docs.astral.sh/uv/) are required.

```sh
scripts/bootstrap.sh
vi config/portal.yml
docker compose up -d --build
```

The containers run with host networking and `NET_ADMIN`, because the rules
they install are the host's forwarding rules. `portalctl watch` applies the
configuration on start and again whenever `portal.yml` changes. For a one-off
check without touching the running rules:

```sh
docker compose run --rm portalctl validate
```

`render` and `apply` are also available. Install the host tuning in
[Host](#host) before putting real subscribers through it.

## How it works

![The BNG sends a suspended subscriber's traffic to the portal box. nftables sends HTTP on port 80 to nginx for the pay page, forwards whitelisted destinations to the payment portal with source NAT, and drops everything else including all HTTPS. dnsmasq feeds the addresses of whitelisted domains into nftables. When the bill is paid, the RADIUS platform sends a CoA to the BNG that restores the session.](docs/images/traffic-flow.svg)

`portalctl` is not in the picture because it carries no traffic: it renders
the three configurations from `portal.yml` and reloads the daemons.

### Getting traffic to the box

The box filters forwarded traffic with the subscriber's real source address
and needs only a route back towards the BNG. How the BNG steers a suspended
subscriber here is your choice, and the three common ways behave differently:

![Three options side by side. A, recommended: a CoA applies a filter or service profile, the session keeps its VRF and address, and all traffic except payment goes to the box. B: a CoA moves the session to a quarantine VRF, which most BNGs refuse mid-session, and a new VRF often means a new address and a re-DHCP anyway. C: a Disconnect-Request, then re-authentication into the quarantine VRF, in seconds for PPPoE, and for IPoE after a re-DHCP, usually forced by bouncing the ONU UNI port.](docs/images/steering-options.svg)

- **A policy or filter pushed by CoA.** The subscriber keeps their VRF and
  address. The CoA changes the subscriber's filter or service profile to one
  whose default next hop is this box, with the payment networks excepted.
  Nothing changes on the subscriber's side, the pay page appears on their
  next HTTP request, and a second CoA restores them. This is the recommended
  approach, and the only one that is smooth for IPoE.
- **A quarantine VRF whose default route is this box.** Clean, but almost no
  BNG moves a live session between VRFs by CoA. When the quarantine VRF has
  its own address pool the subscriber also needs a new address, which means
  a re-DHCP anyway, unless the BNG is really doing a redirect or next hop
  override underneath. In practice this becomes the next option.
- **Disconnect and re-authenticate into a quarantine VRF.** Works for PPPoE,
  where the CPE redials in seconds and RADIUS can return the same address.
  For IPoE the CPE keeps its DHCP lease and the subscriber has no session,
  and no pay page, until it sends a new DHCP request. Waiting for the lease
  to renew is too slow, so on PON networks the usual move is to bounce the
  ONU's UNI port from the OLT or the ACS: the CPE sees its WAN link drop and
  re-DHCPs at once.

### How devices find the portal

Every operating system sends a plain HTTP probe to a fixed URL and expects
one exact answer. Any other answer means "captive portal", and the OS opens
its sign-in sheet with whatever came back. The probes are plain HTTP, with no
encrypted DNS, precisely so that captive portals can intercept them. This box
does not need to spoof DNS: the interception is on the TCP connection to
port 80, whatever address the probe resolved to.

| Client | Probe | Expected answer |
|---|---|---|
| Android, Chrome, ChromeOS | `connectivitycheck.gstatic.com/generate_204` | 204, empty body |
| iOS, macOS | `captive.apple.com/hotspot-detect.html` | 200, body `Success` |
| Windows | `www.msftconnecttest.com/connecttest.txt` | 200, body `Microsoft Connect Test` |
| Firefox | `detectportal.firefox.com/success.txt` | 200, body `success` |
| NetworkManager (Linux) | distribution specific, for example `nmcheck.gnome.org/check_network_status.txt` | 200, body `NetworkManager is online` |

When the probe fires matters for a subscriber suspended mid-session. Every
client probes when it joins a network or wakes. Android also re-probes when
it detects traffic stalling, which dropped HTTPS causes within seconds.
NetworkManager probes every 300 seconds by default. Windows, iOS and macOS
only re-probe on a network event, so a device that was already online shows
the sign-in sheet on its next reconnect or wake, not before. Until then the
subscriber finds the pay page by opening any plain HTTP site, and HTTPS sites
fail to load.

HTTPS cannot be intercepted without certificate errors, by anyone, so it is
dropped rather than answered. The optional `portal.tls` serves the portal's
own name over HTTPS with your certificate, for the link on the pay page, and
changes nothing for other destinations.

## Configuration

```yaml
static_page:
  enable: true            # serve your own HTML from www/
redirect:                 # optional, overrides static_page when present
  url: https://pay.example/portal
portal:
  listen_ip: 10.255.0.1   # this box, as the BNG routes to it
  listen_ip6: 2001:db8:255::1   # optional, enables the portal for IPv6
  fqdn: portal.example
  # tls: {cert: /etc/portal/tls/fullchain.pem, key: /etc/portal/tls/privkey.pem}
whitelist:
  networks: [203.0.113.0/24]
  domains: [pay.example]  # resolved live, fed to nftables via dnsmasq nftset
dns:
  upstreams: [1.1.1.1]
interfaces:
  subscriber: eth1        # faces the BNG
  wan: eth0               # egress for whitelisted traffic
```

Either `static_page.enable` or `redirect.url` is required. Without
`listen_ip6`, IPv6 from subscribers is still filtered, whitelisted
destinations forwarded and the rest dropped, but IPv6 HTTP is dropped rather
than intercepted, so an IPv6-only client never sees the portal. Links in your
`www/` HTML must point at whitelisted destinations or subscribers cannot
follow them. The page shipped in `www/` polls the box and tells the subscriber
when their service is back, because after the restoring CoA the box stops
being reachable from their connection.

## Host

```sh
sudo cp host/sysctl.d/*       /etc/sysctl.d/
sudo cp host/modules-load.d/* /etc/modules-load.d/
sudo cp host/modprobe.d/*     /etc/modprobe.d/
sudo modprobe nf_conntrack && sudo sysctl --system
```

These enable IPv4 and IPv6 forwarding, size conntrack for a million flows
with short timeouts, and give nginx accept queue headroom for probe bursts.

The rules filter forwarded traffic only. The input policy is yours: on the
subscriber interface allow tcp/80 (and 443 with `portal.tls`), udp and tcp 53
to `listen_ip` and `listen_ip6`, ICMP, and the ICMPv6 neighbour discovery
types, and block the rest, SSH included. Manage the box over a separate
interface.

## Sandbox

The whole stack runs in containers, with no host networking and no changes
to host nftables: a subscriber container routed through a gateway container
that runs the portal, and a fake payment site on the WAN side.

```sh
docker compose -f docker-compose-sandbox.yml up -d --build --wait
./scripts/sandbox-test.sh
docker compose -f docker-compose-sandbox.yml exec subscriber bash
docker compose -f docker-compose-sandbox.yml down -v
```

The test script checks interception, the detection probe, the HTTPS drop,
the whitelist, and DNS from the subscriber's side, over IPv4 and IPv6. CI
runs it on every
change, together with the `portalctl` tests in `portalctl/tests`. See
[CONTRIBUTING](CONTRIBUTING.md) for the development loop.

## What it deliberately does not do

- Decide who is suspended. That is the RADIUS platform's job. The box treats
  every packet that reaches it the same way and holds no subscriber list.
- Intercept HTTPS. There is no way to do that without certificate errors on
  every device.
- Advertise itself. DHCP option 114 and the IPv6 RA option come from the BNG
  or DHCP server, and until they are configured the `/capport` endpoint is
  unused.
- Take payment or authenticate anyone. The pay page links to your payment
  provider, which is why its networks are whitelisted.

## Current limitations

- The box sends no router advertisements and runs no DHCPv6. Subscribers get
  their IPv6 addressing from the BNG as usual, and the BNG routes it here.
- One tenant per box: one page or redirect, one whitelist, one portal name.
- A device that was online when the suspension happened may not show the
  sign-in sheet until it reconnects or wakes, as described above.
- Proven in the sandbox and CI. Reports from deployments behind real BNGs,
  working or not, are welcome.

## License

Apache-2.0. Copyright ISPX LIMITED. See `LICENSE` and `NOTICE`.
