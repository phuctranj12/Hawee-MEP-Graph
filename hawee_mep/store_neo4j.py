# -*- coding: utf-8 -*-
"""Nap do thi vao Neo4j - backend cho giai doan B.

Yeu cau: pip install neo4j, va mot Neo4j dang chay (Neo4j Desktop hoac
Docker Desktop tren Windows).

    from hawee_mep import io_graphml, store_neo4j
    G = io_graphml.doc("examples/mau_tu_revit.hmepg")
    store_neo4j.nap(G, "bolt://localhost:7687", "neo4j", "<mat khau>")

Module nay CHI nap du lieu. Lop truy xuat dung Neo4j se duoc viet sau, giu
nguyen chu ky ham nhu hawee_mep/query.py de MCP server khong phai doi.
"""
from __future__ import annotations

import networkx as nx

from .cypher import LOAI_CANH_NEO4J, NHAN_NEO4J

# Thuoc tinh Neo4j khong luu duoc neu la None hoac kieu phuc tap
def _sach(d: dict) -> dict:
    kq = {}
    for k, v in d.items():
        if v is None or v == "":
            continue
        kq[k] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return kq


def nap(G: nx.DiGraph, uri: str, nguoi_dung: str, mat_khau: str,
        co_so_du_lieu: str = "neo4j", xoa_cu: bool = False,
        kich_thuoc_lo: int = 500) -> dict:
    """Nap toan bo do thi vao Neo4j. Tra ve so node va canh da nap."""
    from neo4j import GraphDatabase  # import tai cho de khong bat buoc

    so_node = so_canh = 0
    with GraphDatabase.driver(uri, auth=(nguoi_dung, mat_khau)) as driver:
        with driver.session(database=co_so_du_lieu) as s:
            if xoa_cu:
                s.run("MATCH (n:ThietBi) DETACH DELETE n")

            s.run(
                "CREATE CONSTRAINT thiet_bi_id IF NOT EXISTS "
                "FOR (n:ThietBi) REQUIRE n.id IS UNIQUE"
            )

            # Node, chia lo theo nhan de dung duoc label dong
            theo_nhan: dict[str, list[dict]] = {}
            for n, d in G.nodes(data=True):
                nhan = NHAN_NEO4J.get(d.get("loai", ""), "KhongRo")
                theo_nhan.setdefault(nhan, []).append({**_sach(d), "id": str(n)})

            for nhan, ds in theo_nhan.items():
                for i in range(0, len(ds), kich_thuoc_lo):
                    lo = ds[i:i + kich_thuoc_lo]
                    s.run(
                        f"UNWIND $lo AS d "
                        f"MERGE (n:ThietBi {{id: d.id}}) "
                        f"SET n += d, n:{nhan}",
                        lo=lo,
                    )
                    so_node += len(lo)

            # Canh, chia lo theo loai quan he
            theo_loai: dict[str, list[dict]] = {}
            for u, v, d in G.edges(data=True):
                qh = LOAI_CANH_NEO4J.get(d.get("loai", "supplies"), "CAP_NGUON")
                theo_loai.setdefault(qh, []).append(
                    {"u": str(u), "v": str(v), **_sach(d)}
                )

            for qh, ds in theo_loai.items():
                for i in range(0, len(ds), kich_thuoc_lo):
                    lo = ds[i:i + kich_thuoc_lo]
                    s.run(
                        f"UNWIND $lo AS d "
                        f"MATCH (a:ThietBi {{id: d.u}}), (b:ThietBi {{id: d.v}}) "
                        f"MERGE (a)-[r:{qh}]->(b) "
                        f"SET r.so_mach = d.so_mach, "
                        f"    r.thiet_bi_bao_ve = d.thiet_bi_bao_ve",
                        lo=lo,
                    )
                    so_canh += len(lo)

    return {"so_node": so_node, "so_canh": so_canh}
