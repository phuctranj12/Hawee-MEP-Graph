# -*- coding: utf-8 -*-
"""Tinh cong suat lan truyen va diem rui ro cho tung node.

Phuong phap ke thua tu luan van MACAD (xem NOTICE), viet lai va mo rong:

    diem_rui_ro = (ty_trong_cong_suat + ty_trong_ha_nguon) / 2  *  he_so_quan_trong

trong do:
    ty_trong_cong_suat = cong suat lan truyen qua node / tong tai toan he
    ty_trong_ha_nguon  = so thiet bi ha nguon / so lon nhat trong he

Y nghia: mot node vua tai nhieu cong suat, vua co nhieu thiet bi phu thuoc
phia sau thi hong se gay thiet hai lon nhat.

Mo rong so voi ban goc: nhan them he so do_quan_trong (1..5) do nguoi van
hanh dat, de phan anh muc do quan trong nghiep vu ma topo khong thay duoc
(vi du tu cap dien cho phong may chu).
"""
from __future__ import annotations

import networkx as nx

from .model import LOAI_BO_QUA_BAO_TRI, do_thi_cap_nguon


def tinh_cong_suat_lan_truyen(G: nx.DiGraph) -> dict[str, float]:
    """Don tai tu phu tai cuoi nguoc len thuong nguon.

    Cong suat cua mot node = cong suat rieng + tong cong suat cac node ha nguon.

    QUAN TRONG: chi phu tai cuoi (loai='phu_tai') duoc phep mang cong_suat_kVA.
    Neu tu dien cung mang cong_suat_kVA thi phep don tai se dem trung, vi con
    so cua tu vo'n da la tong cong don ha nguon. Bo trich xuat Revit chuyen
    con so cua tu sang truong cong_suat_cong_don_revit_kVA de tranh viec nay.
    Khi mot node co nhieu nguon cap (du phong), tai duoc chia deu cho cac
    nguon de khong tinh trung.
    """
    S = do_thi_cap_nguon(G)
    if not nx.is_directed_acyclic_graph(S):
        S = _pha_chu_trinh(S)

    kq: dict[str, float] = {}
    for n in reversed(list(nx.topological_sort(S))):
        rieng = float(S.nodes[n].get("cong_suat_kVA") or 0.0)
        tong = rieng
        for con in S.successors(n):
            so_nguon = max(1, S.in_degree(con))
            tong += kq.get(con, 0.0) / so_nguon
        kq[n] = tong

    # Du phong: nhieu model Revit chi ghi cong suat o TU, khong ghi o phu tai
    # cuoi. Khi do phep don tai tu duoi len cho ket qua 0 va diem rui ro mat
    # thong tin cong suat. Truong hop nay dung chinh con so cong don ma Revit
    # ghi cho tu - voi mot node rieng le thi con so nay dung va khong dem trung.
    for n, d in S.nodes(data=True):
        if kq.get(n, 0.0) == 0.0:
            du_phong = d.get("cong_suat_cong_don_revit_kVA")
            if du_phong not in (None, ""):
                try:
                    kq[n] = float(du_phong)
                except (TypeError, ValueError):
                    pass
    return kq


def dem_thiet_bi_ha_nguon(G: nx.DiGraph) -> dict[str, int]:
    """Dem so thiet bi ha nguon, bo qua mach va phu tai cuoi.

    Bo qua phu tai cuoi vi neu dem ca thi moi tu deu bi keo len rat cao va
    diem rui ro mat kha nang phan biet.
    """
    S = do_thi_cap_nguon(G)
    if not nx.is_directed_acyclic_graph(S):
        S = _pha_chu_trinh(S)
    kq: dict[str, int] = {}
    for n in S.nodes:
        hau_due = nx.descendants(S, n)
        kq[n] = sum(
            1 for m in hau_due
            if S.nodes[m].get("loai") not in LOAI_BO_QUA_BAO_TRI
        )
    return kq


def tinh_diem_rui_ro(G: nx.DiGraph) -> dict[str, float]:
    """Tra ve diem rui ro 0..1 cho tung node, cao nhat duoc chuan hoa ve 1."""
    cs = tinh_cong_suat_lan_truyen(G)
    hn = dem_thiet_bi_ha_nguon(G)

    # Chuan hoa theo GIA TRI LON NHAT, khong theo tong tai.
    # Ban goc chia cho tong tai toan he; cach do chi dung khi moi node deu
    # mang tai rieng va khong cong don. Voi du lieu Revit thuc te (tai ghi o
    # tu, da cong don) thi mau so sai. Chia cho gia tri lon nhat luon dung,
    # bat ke so lieu nam o tang nao.
    max_cs = max(cs.values(), default=0.0) or 1.0
    max_hn = max(hn.values(), default=0) or 1

    tho: dict[str, float] = {}
    for n, d in G.nodes(data=True):
        tt_cs = cs.get(n, 0.0) / max_cs
        tt_hn = hn.get(n, 0) / max_hn
        qt = d.get("do_quan_trong")
        he_so = 1.0 if qt in (None, "") else (0.6 + 0.2 * float(qt))
        tho[n] = (tt_cs + tt_hn) / 2 * he_so

    cao_nhat = max(tho.values(), default=0.0) or 1.0
    return {n: v / cao_nhat for n, v in tho.items()}


def gan_vao_do_thi(G: nx.DiGraph) -> nx.DiGraph:
    """Tinh va ghi cong_suat_lan_truyen, so_thiet_bi_ha_nguon, diem_rui_ro."""
    cs = tinh_cong_suat_lan_truyen(G)
    hn = dem_thiet_bi_ha_nguon(G)
    rr = tinh_diem_rui_ro(G)
    for n in G.nodes:
        G.nodes[n]["cong_suat_lan_truyen"] = round(cs.get(n, 0.0), 3)
        G.nodes[n]["so_thiet_bi_ha_nguon"] = hn.get(n, 0)
        G.nodes[n]["diem_rui_ro"] = round(rr.get(n, 0.0), 4)
    return G


def _pha_chu_trinh(S: nx.DiGraph) -> nx.DiGraph:
    """Bo canh gay chu trinh de tinh toan duoc tiep.

    Chu trinh hop le duy nhat trong he phan phoi la mach vong qua ATS.
    Ham nay giu nguyen do thi goc va chi lam viec tren ban sao.
    """
    H = S.copy()
    while not nx.is_directed_acyclic_graph(H):
        try:
            vong = next(nx.simple_cycles(H))
        except StopIteration:
            break
        H.remove_edge(vong[-1], vong[0])
    return H
