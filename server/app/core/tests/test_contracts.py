"""Tests for issuing contracts for an order (app/core/contracts.py)."""

from typing import Any, Callable, Dict, List

import base64
import json

import httpx
import pytest

from app.core.contracts import (
    ContractError,
    GeneratorTarget,
    build_items,
    consumer_from_bearer,
    group_by_region,
    issue_contracts_for_order,
    normalize_hash,
)

HUS = GeneratorTarget(
    url="http://ds-contract-generator.hus.svc.cluster.local:8082",
    node_id="hus.nextgen.hiro-develop.nl",
)


def dataset(
    identifier: str = "hospital-cardiology-gwas",
    region: str = "hus",
    checksum: str = "fb02d8b5ec7c319c1242eb327acc7015",
) -> Dict[str, Any]:
    """A dataset as the website sends it: a flattened row plus DCAT keys."""
    return {
        "@type": "dcat:Dataset",
        "identifier": identifier,
        "title": f"Title of {identifier}",
        "region": region,
        "dcat:distribution": [
            {
                "dcat:accessURL": f"https://example.org/{identifier}.csv",
                "spdx:checksum": {
                    "@type": "spdx:Checksum",
                    "spdx:algorithm": {"@id": "spdx:SHA256"},
                    "spdx:checksumValue": {
                        "@type": "xsd:hexBinary",
                        "@value": checksum,
                    },
                },
            }
        ],
    }


class TestNormalizeHash:
    def test_adds_the_prefix_the_generator_needs(self) -> None:
        # A 32-hex value as the HUS catalog holds today.
        assert normalize_hash("FB02D8B5EC7C319C1242EB327ACC7015") == (
            "sha256:fb02d8b5ec7c319c1242eb327acc7015"
        )

    def test_keeps_a_prefixed_sha256(self) -> None:
        digest = "a" * 64
        assert normalize_hash(f"sha256:{digest}") == f"sha256:{digest}"

    def test_refuses_what_the_generator_would_refuse(self) -> None:
        for value in (None, "", "not-hex", "abc", "a" * 65, "md5:" + "a" * 32):
            assert normalize_hash(value) is None, value


class TestBuildItems:
    def test_builds_the_id_from_the_node_not_the_catalog(self) -> None:
        [item] = build_items([dataset()], HUS.node_id)
        node = "https://hus.nextgen.hiro-develop.nl"
        assert item == {
            "id": f"{node}/dataset/hospital-cardiology-gwas",
            "identifier": "hospital-cardiology-gwas",
            "title": "Title of hospital-cardiology-gwas",
            "hash": "sha256:fb02d8b5ec7c319c1242eb327acc7015",
        }

    def test_reads_json_ld_literals_and_prefixed_keys(self) -> None:
        row = dataset()
        row.pop("identifier")
        row.pop("title")
        row["dcterms:identifier"] = {"@value": "metabolic-disease-genomics"}
        row["dcterms:title"] = {"@value": "Metabolic disease genomics"}
        [item] = build_items([row], HUS.node_id)
        assert item["identifier"] == "metabolic-disease-genomics"
        assert item["title"] == "Metabolic disease genomics"

    def test_names_the_dataset_that_has_no_checksum(self) -> None:
        with pytest.raises(ContractError, match="gene-expression-profiling"):
            build_items(
                [dataset("gene-expression-profiling", checksum="")], HUS.node_id
            )


class TestGroupByRegion:
    def test_groups_case_insensitively_and_skips_rows_without_region(self) -> None:
        rows = [dataset("a", "hus"), dataset("b", "KI"), dataset("c", "HUS")]
        rows.append({"identifier": "no-region"})
        groups = group_by_region(rows)
        assert list(groups) == ["hus", "ki"]
        assert [d["identifier"] for d in groups["hus"]] == ["a", "c"]


def fake_generator(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> List[Dict[str, Any]]:
    """Route the module's httpx calls to `handler`; returns the request bodies."""
    seen: List[Dict[str, Any]] = []
    real_client = httpx.AsyncClient

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return handler(request)

    def client(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(wrapped), **kwargs)

    # app.core.contracts creates its client as httpx.AsyncClient(...).
    monkeypatch.setattr(httpx, "AsyncClient", client)
    return seen


class TestIssueContractsForOrder:
    @pytest.mark.asyncio
    async def test_one_contract_per_region_with_a_generator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = fake_generator(
            monkeypatch,
            lambda request: httpx.Response(201, json={"jti": "j-1", "token": "t.o.k"}),
        )
        issued = await issue_contracts_for_order(
            order_id="order-1",
            consumer_id="researcher@hus.example",
            datasets=[dataset("a", "hus"), dataset("b", "ki"), dataset("c", "hus")],
            generators={"hus": HUS},
            ttl_seconds=7200,
        )

        # ki has no generator: only the hus datasets are covered, in one call.
        assert [(c.region, c.jti, c.token) for c in issued] == [("hus", "j-1", "t.o.k")]
        assert len(seen) == 1
        assert seen[0]["order_id"] == "order-1"
        assert seen[0]["consumer_id"] == "researcher@hus.example"
        assert seen[0]["ttl_seconds"] == 7200
        assert [i["identifier"] for i in seen[0]["items"]] == ["a", "c"]

    @pytest.mark.asyncio
    async def test_a_refusal_is_logged_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_generator(
            monkeypatch,
            lambda request: httpx.Response(400, json={"detail": "host mismatch"}),
        )
        issued = await issue_contracts_for_order(
            order_id="order-2",
            consumer_id="x@y",
            datasets=[dataset()],
            generators={"hus": HUS},
            ttl_seconds=60,
        )
        assert issued == []

    @pytest.mark.asyncio
    async def test_an_unreachable_generator_is_logged_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        fake_generator(monkeypatch, down)
        issued = await issue_contracts_for_order(
            order_id="order-3",
            consumer_id="x@y",
            datasets=[dataset()],
            generators={"hus": HUS},
            ttl_seconds=60,
        )
        assert issued == []

    @pytest.mark.asyncio
    async def test_bad_data_skips_the_region_without_calling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = fake_generator(
            monkeypatch,
            lambda request: httpx.Response(201, json={"jti": "j", "token": "t"}),
        )
        issued = await issue_contracts_for_order(
            order_id="order-4",
            consumer_id="x@y",
            datasets=[dataset(checksum="not-a-hash")],
            generators={"hus": HUS},
            ttl_seconds=60,
        )
        assert issued == [] and seen == []


def bearer(claims: Any) -> str:
    """A ds-login-shaped JWT; the signature is not read."""

    def b64(value: Any) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()

    return f"Bearer {b64({'alg': 'RS256'}).rstrip('=')}.{b64(claims).rstrip('=')}.sig"


class TestConsumerFromBearer:
    def test_names_the_email_in_the_token(self) -> None:
        token = bearer({"sub": "EAID", "email": " researcher@hus.example "})
        assert consumer_from_bearer(token) == "researcher@hus.example"

    def test_falls_back_to_the_aid(self) -> None:
        assert consumer_from_bearer(bearer({"sub": "EAID123"})) == "keri:EAID123"

    def test_is_none_without_a_usable_token(self) -> None:
        for header in (
            None,
            "",
            "Basic dXNlcg==",
            "Bearer not-a-jwt",
            "Bearer a.%%%.c",
            bearer(["not", "an", "object"]),
            bearer({"email": "a b", "sub": "x y"}),
            bearer({"role": "researcher"}),
        ):
            assert consumer_from_bearer(header) is None, header
