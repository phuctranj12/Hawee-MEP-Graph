# -*- coding: utf-8 -*-
"""Doc va ghi do thi dinh dang .hmepg (GraphML).

GraphML luu moi gia tri duoi dang chuoi. Module nay doi cac truong so ve
float/int khi doc, de phan con lai khong phai doi lien tuc.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx

NS = "{http://graphml.graphdrawing.org/xmlns}"

# Truong can doi ve so khi doc
TRUONG_FLOAT = frozenset({
    "x", "y", "z",
    "dien_ap_V", "dong_dien_dinh_muc_A", "tan_so_Hz", "cong_suat_kVA",
    "dong_ngan_mach_kA", "chieu_dai_m",
    "tuoi_tho_nam", "gio_van_hanh",
    "chi_phi_thay_the_vnd", "he_so_sua_chua",
    "cong_suat_lan_truyen", "diem_rui_ro", "rul_ngay", "rul_nam",
    "dong_bao_ve_A", "sut_ap_V",
})
TRUONG_INT = frozenset({
    "so_pha", "chu_ky_bao_tri_thang", "so_lan_su_co", "do_quan_trong",
    "so_thiet_bi_ha_nguon",
})


def doc(duong_dan: str | Path) -> nx.DiGraph:
    """Doc file .hmepg (hoac .graphml) thanh DiGraph, da doi kieu so."""
    goc = ET.parse(str(duong_dan)).getroot()
    ten_key = {k.get("id"): k.get("attr.name") for k in goc.findall(NS + "key")}

    G = nx.DiGraph()
    do_thi = goc.find(NS + "graph")
    if do_thi is not None:
        for k, v in do_thi.attrib.items():
            if k not in ("id", "edgedefault"):
                G.graph[k] = v
        ten = do_thi.get("id")
        if ten:
            G.graph.setdefault("ten_do_thi", ten)

    for n in goc.iter(NS + "node"):
        G.add_node(n.get("id"), **_doc_data(n, ten_key))
    for e in goc.iter(NS + "edge"):
        d = _doc_data(e, ten_key)
        d.setdefault("loai", "supplies")
        G.add_edge(e.get("source"), e.get("target"), **d)
    return G


def _doc_data(phan_tu, ten_key: dict) -> dict:
    d: dict = {}
    for x in phan_tu:
        if x.tag != NS + "data":
            continue
        ten = ten_key.get(x.get("key")) or x.get("key")
        if x.text is None or x.text.strip() == "":
            continue
        d[ten] = _doi_kieu(ten, x.text.strip())
    return d


def _doi_kieu(ten: str, gia_tri: str):
    if ten in TRUONG_FLOAT:
        try:
            return float(gia_tri)
        except ValueError:
            return gia_tri
    if ten in TRUONG_INT:
        try:
            return int(float(gia_tri))
        except ValueError:
            return gia_tri
    return gia_tri


def ghi(G: nx.DiGraph, duong_dan: str | Path) -> None:
    """Ghi do thi ra file .hmepg.

    Dung networkx de ghi GraphML, nhung doi gia tri None thanh chuoi rong
    truoc, vi GraphML khong bieu dien duoc None.
    """
    H = nx.DiGraph()
    H.graph.update(G.graph)
    for n, d in G.nodes(data=True):
        H.add_node(n, **{k: ("" if v is None else v) for k, v in d.items()})
    for u, v, d in G.edges(data=True):
        H.add_edge(u, v, **{k: ("" if x is None else x) for k, x in d.items()})
    nx.write_graphml(H, str(duong_dan), named_key_ids=True)
