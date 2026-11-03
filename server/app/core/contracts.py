"""Asking each node's contract generator for a contract covering an order.

Checkout stores what a researcher selected; a contract records who may use it.
The generator has required an `order_id` since it was written, but nothing
called it, so an order was never recorded anywhere. This is that call.

An order can hold datasets from several nodes, and each node signs only its own
data, so the datasets are grouped by `region` and each group goes to that
node's generator (CONTRACT_GENERATORS). A region with no generator gets no
contract. Issuing is best effort: the order is stored whatever happens here,
because the training run that follows (COG) does not use the contract yet.

The generator is strict about two things:

* every item's `id` must have the node's own host (`hus.nextgen.hiro-develop.nl`,
  not the catalog's), so it is built from the node id, not taken from the record;
* `hash` must look like `sha256:<hex>`. The catalog's checksum is passed on
  as it is, with that prefix added when missing.
"""

from typing import Any, Dict, List, Optional

import base64
import binascii
import json
import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# The generator's own pattern (CatalogItem.hash): 32 to 64 lowercase hex.
_HEX_DIGEST = re.compile(r"^[0-9a-f]{32,64}$")


class ContractError(Exception):
    """The generator refused, could not be reached, or the order lacks data."""


@dataclass(frozen=True)
class GeneratorTarget:
    """Where one node's generator is, and the node id it signs for."""

    url: str
    node_id: str


@dataclass(frozen=True)
class IssuedContract:
    region: str
    jti: str
    token: str


def _first(mapping: Dict[str, Any], *keys: str) -> Any:
    """First present, non-empty value among `keys`.

    The payload reaching checkout is a flattened table row with a couple of
    DCAT-prefixed keys laid over it, so the same fact can arrive under more than
    one name depending on which page built it.
    """
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _as_text(value: Any) -> Optional[str]:
    """Unwrap a JSON-LD literal (`{"@value": ...}`) or pass a plain string."""
    if isinstance(value, dict):
        value = value.get("@value")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def consumer_from_bearer(authorization: Optional[str]) -> Optional[str]:
    """Who is ordering: the email in a ds-login JWT sent as `Bearer <token>`.

    Falls back to `keri:<AID>` (the token's subject) when the token has no
    email. The token is read, NOT verified: nothing in the data space checks
    tokens until after the demo, so this only names the consumer in the
    contract. Verifying it against ds-login's keys (JWKS) is the step to add
    when tokens start to be checked.
    """
    match = re.match(r"^Bearer\s+(\S+)\s*$", authorization or "", re.IGNORECASE)
    if not match:
        return None
    parts = match.group(1).split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    if not isinstance(claims, dict):
        return None

    def usable(value: Any) -> Optional[str]:
        text = value.strip() if isinstance(value, str) else ""
        return text if text and not re.search(r"\s", text) else None

    email = usable(claims.get("email"))
    if email:
        return email
    aid = usable(claims.get("sub"))
    return f"keri:{aid}" if aid else None


def normalize_hash(value: Optional[str]) -> Optional[str]:
    """The checksum in the generator's `sha256:<hex>` form, or None.

    The catalog labels its checksums SHA256, but on HUS they are 32-hex values
    (MD5 length). They are recorded as they are: the contract states what the
    catalog states. A real SHA-256 needs the connector to compute one.
    """
    if not value:
        return None
    digest = value.strip().lower()
    if digest.startswith("sha256:"):
        digest = digest[len("sha256:") :]
    if not _HEX_DIGEST.match(digest):
        return None
    return f"sha256:{digest}"


def _dataset_checksum(dataset: Dict[str, Any]) -> Optional[str]:
    distributions = _first(dataset, "dcat:distribution", "distribution") or []
    if isinstance(distributions, dict):
        distributions = [distributions]
    for distribution in distributions:
        if not isinstance(distribution, dict):
            continue
        block = _first(distribution, "checksum", "spdx:checksum")
        if isinstance(block, dict):
            checksum = normalize_hash(
                _as_text(_first(block, "checksumValue", "spdx:checksumValue"))
            )
            if checksum:
                return checksum
    return None


def build_items(datasets: List[Dict[str, Any]], node_id: str) -> List[Dict[str, str]]:
    """Turn one node's ordered datasets into the generator's CatalogItem list.

    Raises ContractError naming the dataset when something required is missing,
    rather than sending a half-filled item for the generator to reject with a
    message that does not say which one.
    """
    items: List[Dict[str, str]] = []

    for index, dataset in enumerate(datasets):
        identifier = _as_text(_first(dataset, "identifier", "dcterms:identifier"))
        title = _as_text(_first(dataset, "title", "dcterms:title", "name"))
        checksum = _dataset_checksum(dataset)

        where = f"dataset at index {index}"
        if not identifier:
            raise ContractError(f"{where} has no identifier")
        if not title:
            raise ContractError(f"{where} ({identifier}) has no title")
        if not checksum:
            raise ContractError(
                f"{where} ({identifier}) has no usable distribution checksum"
            )

        items.append(
            {
                "id": f"https://{node_id}/dataset/{identifier}",
                "identifier": identifier,
                "title": title,
                "hash": checksum,
            }
        )

    return items


def group_by_region(datasets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Datasets per region, in order of first appearance. No region: skipped."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for dataset in datasets:
        region = _as_text(dataset.get("region"))
        if region:
            groups.setdefault(region.lower(), []).append(dataset)
    return groups


async def issue_contract(
    *,
    target: GeneratorTarget,
    order_id: str,
    consumer_id: str,
    datasets: List[Dict[str, Any]],
    ttl_seconds: int,
    timeout_seconds: float = 10.0,
) -> Dict[str, str]:
    """Ask one generator for a contract. Returns its `jti` and `token`."""
    items = build_items(datasets, target.node_id)
    payload = {
        "consumer_id": consumer_id,
        "order_id": order_id,
        "ttl_seconds": ttl_seconds,
        "items": items,
    }

    url = f"{target.url.rstrip('/')}/v1/contracts"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as error:
        raise ContractError(f"contract generator unreachable at {url}: {error}")

    if response.status_code >= 400:
        raise ContractError(
            f"contract generator refused the order ({response.status_code}): "
            f"{response.text[:400]}"
        )

    body = response.json()
    token, jti = body.get("token"), body.get("jti")
    if not token or not jti:
        raise ContractError("contract generator returned no token")
    return {"jti": str(jti), "token": str(token)}


async def issue_contracts_for_order(
    *,
    order_id: str,
    consumer_id: str,
    datasets: List[Dict[str, Any]],
    generators: Dict[str, GeneratorTarget],
    ttl_seconds: int,
) -> List[IssuedContract]:
    """One contract per region that has a generator. Never raises.

    A region without a generator, or one whose generator refuses, is logged and
    skipped: the order itself must still go through.
    """
    issued: List[IssuedContract] = []
    for region, group in group_by_region(datasets).items():
        target = generators.get(region)
        if target is None:
            logger.info(
                "Order %s: no contract generator for region %s (%d dataset(s))",
                order_id,
                region,
                len(group),
            )
            continue
        try:
            result = await issue_contract(
                target=target,
                order_id=order_id,
                consumer_id=consumer_id,
                datasets=group,
                ttl_seconds=ttl_seconds,
            )
        except ContractError as error:
            logger.warning(
                "Order %s: no contract for region %s: %s", order_id, region, error
            )
            continue
        logger.info(
            "Order %s: contract %s for region %s covering %d dataset(s)",
            order_id,
            result["jti"],
            region,
            len(group),
        )
        issued.append(IssuedContract(region=region, **result))
    return issued
