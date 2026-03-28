from __future__ import annotations

from urllib.parse import urlparse

ELECTRONET_DOMAINS = {"electronet.gr", "www.electronet.gr"}
SKROUTZ_DOMAINS = {"skroutz.gr", "www.skroutz.gr", "skroutz.cy", "www.skroutz.cy"}
TEFAL_MANUFACTURER_DOMAINS = {"shop.tefal.gr", "www.shop.tefal.gr"}
SKROUTZ_PRODUCT_PATH_PREFIX = "/s/"
TEFAL_PRODUCT_PATH_PREFIX = "/products/"


def normalize_host(url: str) -> str:
    return urlparse(url).netloc.strip().lower()


def detect_source(url: str) -> str:
    host = normalize_host(url)
    if host in ELECTRONET_DOMAINS:
        return "electronet"
    if host in SKROUTZ_DOMAINS:
        return "skroutz"
    if host in TEFAL_MANUFACTURER_DOMAINS:
        return "manufacturer_tefal"
    raise ValueError("Input URL must be an Electronet, Skroutz, or supported manufacturer product URL")


def is_skroutz_product_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.strip().lower() in SKROUTZ_DOMAINS and parsed.path.startswith(SKROUTZ_PRODUCT_PATH_PREFIX)


def is_tefal_product_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.strip().lower() in TEFAL_MANUFACTURER_DOMAINS and parsed.path.startswith(TEFAL_PRODUCT_PATH_PREFIX)


def validate_url_scope(url: str) -> tuple[str, bool, str]:
    source = detect_source(url)
    if source == "electronet":
        return source, True, "electronet_domain"
    if is_skroutz_product_url(url):
        return source, True, "skroutz_product_path"
    if source == "skroutz":
        return source, False, "skroutz_non_product_path"
    if is_tefal_product_url(url):
        return source, True, "manufacturer_tefal_product_path"
    return source, False, "manufacturer_tefal_non_product_path"
