#!/usr/bin/env bash
# Verify the captive portal from the sandbox subscriber container.
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose-sandbox.yml"
sub() { $COMPOSE exec -T subscriber "$@"; }

pass=0
fail=0
check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "PASS: $desc"
    pass=$((pass + 1))
  else
    echo "FAIL: $desc"
    fail=$((fail + 1))
  fi
}
check_blocked() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "FAIL: $desc (traffic was NOT blocked)"
    fail=$((fail + 1))
  else
    echo "PASS: $desc"
    pass=$((pass + 1))
  fi
}

page_enabled=$(awk '/^static_page:/ {f=1; next} f && /enable:/ {print $2; exit}' config/portal-sandbox.yml)
has_redirect=$(grep -c '^redirect:' config/portal-sandbox.yml || true)
mode=redirect
expected_code=302
# redirect, when present, overrides the static page
if [ "$page_enabled" = "true" ] && [ "$has_redirect" = "0" ]; then
  mode=static_page
  expected_code=200
fi
echo "== captive portal sandbox tests (mode: $mode) =="

code=$(sub curl -s -o /dev/null -w '%{http_code}' -m 5 http://192.0.2.99/)
check "HTTP to arbitrary IP intercepted with $expected_code (got $code)" \
  test "$code" = "$expected_code"

code=$(sub curl -s -o /dev/null -w '%{http_code}' -m 5 http://192.0.2.99/generate_204)
check "detection probe /generate_204 intercepted with $expected_code (got $code)" \
  test "$code" = "$expected_code"

if [ "$mode" = "static_page" ]; then
  check "intercepted request serves the local portal page" \
    sh -c "$COMPOSE exec -T subscriber curl -s -m 5 http://192.0.2.99/ | grep -q 'suspended'"
else
  check "following the redirect lands on the payment portal" \
    sh -c "$COMPOSE exec -T subscriber curl -sL -m 5 http://192.0.2.99/ | grep -q 'Welcome to nginx'"
fi

check_blocked "HTTPS to arbitrary IP is dropped" sub curl -s -m 3 https://192.0.2.99/

check "whitelisted payment portal reachable directly" \
  sub curl -s -o /dev/null -m 5 http://203.0.113.10/

check "ping whitelisted payment portal" sub ping -c1 -W2 203.0.113.10

check_blocked "ping non-whitelisted destination is dropped" sub ping -c1 -W2 198.18.0.1

check "portal FQDN resolves to portal via dnsmasq" \
  sh -c "$COMPOSE exec -T subscriber dig +short @10.255.0.1 portal.company.example | grep -q 10.255.0.1"

# IPv6: the same path, with the subscriber's default route pointing at the
# gateway's fd00:255::1 and fd00:113::10 whitelisted.
code=$(sub curl -s -o /dev/null -w '%{http_code}' -m 5 'http://[fd00:dead::99]/')
check "IPv6 HTTP to arbitrary address intercepted with $expected_code (got $code)" \
  test "$code" = "$expected_code"

check_blocked "IPv6 HTTPS to arbitrary address is dropped" sub curl -s -m 3 'https://[fd00:dead::99]/'

check "IPv6 whitelisted payment portal reachable directly" \
  sub curl -s -o /dev/null -m 5 'http://[fd00:113::10]/'

check "ping IPv6 whitelisted payment portal" sub ping -6 -c1 -W2 fd00:113::10

check_blocked "ping IPv6 non-whitelisted destination is dropped" sub ping -6 -c1 -W2 fd00:dead::1

check "portal FQDN has an AAAA record from dnsmasq over IPv6" \
  sh -c "$COMPOSE exec -T subscriber dig +short @fd00:255::1 AAAA portal.company.example | grep -q fd00:255::1"

# DNS over TLS is reset, not dropped: curl exits 7 (refused) rather than 28
# (timed out), so strict private DNS clients fail over to plain DNS at once.
check "DoT port 853 is refused with a reset" \
  sh -c "$COMPOSE exec -T subscriber curl -s -m 3 http://192.0.2.99:853/; test \$? -eq 7"
check "IPv6 DoT port 853 is refused with a reset" \
  sh -c "$COMPOSE exec -T subscriber curl -s -m 3 'http://[fd00:dead::99]:853/'; test \$? -eq 7"

echo "== $pass passed, $fail failed =="
exit "$((fail > 0))"
