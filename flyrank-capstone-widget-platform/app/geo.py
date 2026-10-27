"""IP -> country/city with a fallback chain: provider A, then B, then give up quietly (never raise)."""
import ipaddress
import logging

import requests

from . import config, dev_state

log = logging.getLogger("geo")


class ProviderDown(Exception):
    pass


def _check_toggle(name):
    if dev_state.get()[f"geo_{name.lower()}_down"]:
        raise ProviderDown(f"provider {name} is down (forced by dev toggle)")


def _mock(name):
    def lookup(ip):
        _check_toggle(name)
        return {"country": "Mockland", "city": f"{name}-ville", "provider": name}
    return lookup


def _ip_api(ip):                      # provider A: ip-api.com, no key
    _check_toggle("A")
    resp = requests.get(f"http://ip-api.com/json/{ip}", params={"fields": "status,country,city"},
                        timeout=config.GEO_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise ProviderDown("ip-api.com returned no result")
    return {"country": data.get("country"), "city": data.get("city"), "provider": "A"}


def _ipapi_co(ip):                    # provider B: ipapi.co, no key
    _check_toggle("B")
    resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=config.GEO_TIMEOUT_SECONDS,
                        headers={"User-Agent": "flyrank-capstone-widget-platform/1.0"})
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise ProviderDown("ipapi.co returned an error")
    return {"country": data.get("country_name"), "city": data.get("city"), "provider": "B"}


def _providers():
    if config.GEO_MODE == "real":
        return [("A", _ip_api), ("B", _ipapi_co)]
    return [("A", _mock("A")), ("B", _mock("B"))]


def _is_public_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def enrich(ip):
    """Return {"country", "city", "provider"} or None. Never raises: no geo is better than no submission."""
    if config.GEO_MODE == "real" and not _is_public_ip(ip):
        return None                   # localhost / private addresses have no location
    for name, lookup in _providers():
        try:
            return lookup(ip)
        except Exception as e:        # any failure of this provider -> try the next one
            log.warning("geo provider %s failed: %s", name, e)
    return None
