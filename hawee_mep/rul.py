# -*- coding: utf-8 -*-
"""Tinh tuoi tho con lai (RUL - Remaining Useful Life).

Mo hinh: tuoi tho con lai giam dan theo tuoi thiet bi, co dieu chinh theo
gio van hanh, so lan su co va viec bao tri dinh ky.

    rul_nam = tuoi_tho_nam - tuoi_hien_tai - phat_su_co + thuong_bao_tri

Cac he so mac dinh nam trong data/loai_thiet_bi.csv de nguoi van hanh sua
duoc ma khong phai sua code. Day la diem khac ban goc, noi cac so nay bi
viet cung trong file Python.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import networkx as nx

THU_MUC_DATA = Path(__file__).resolve().parent.parent / "data"

# Dung khi khong tim thay loai trong bang dinh muc
MAC_DINH = {
    "tuoi_tho_nam": 20.0,
    "suy_giam_nam": 0.03,
    "do_quan_trong": 3,
    "chi_phi_thay_the_vnd": 0.0,
    "he_so_sua_chua": 0.3,
    "chu_ky_bao_tri_thang": 12,
}


def nap_dinh_muc(duong_dan: str | Path | None = None) -> dict[str, dict]:
    """Nap data/loai_thiet_bi.csv thanh dict theo ma loai."""
    p = Path(duong_dan) if duong_dan else THU_MUC_DATA / "loai_thiet_bi.csv"
    bang: dict[str, dict] = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for dong in csv.DictReader(f):
            ma = (dong.get("loai") or "").strip()
            if not ma:
                continue
            bang[ma] = {
                "tuoi_tho_nam": _f(dong.get("tuoi_tho_nam"), 20.0),
                "suy_giam_nam": _f(dong.get("suy_giam_nam"), 0.03),
                "do_quan_trong": int(_f(dong.get("do_quan_trong"), 3)),
                "chi_phi_thay_the_vnd": _f(dong.get("chi_phi_thay_the_vnd"), 0.0),
                "he_so_sua_chua": _f(dong.get("he_so_sua_chua"), 0.3),
                "chu_ky_bao_tri_thang": int(_f(dong.get("chu_ky_bao_tri_thang"), 12)),
                "ten_hien_thi": (dong.get("ten_hien_thi") or ma).strip(),
            }
    return bang


def tinh_rul_node(thuoc_tinh: dict, dinh_muc: dict,
                  ngay_tinh: date | None = None) -> dict:
    """Tinh RUL cho mot node.

    Tra ve dict: rul_nam, rul_ngay, tuoi_nam, ty_le_con_lai, can_thay_the,
    ghi_chu (ly do khong tinh duoc, neu co).
    """
    ngay_tinh = ngay_tinh or date.today()
    loai = thuoc_tinh.get("loai", "")
    dm = dinh_muc.get(loai, MAC_DINH)

    tuoi_tho = _f(thuoc_tinh.get("tuoi_tho_nam"), dm["tuoi_tho_nam"])

    ngay_lap = _ngay(thuoc_tinh.get("ngay_lap_dat"))
    if ngay_lap is None:
        return {
            "rul_nam": None, "rul_ngay": None, "tuoi_nam": None,
            "ty_le_con_lai": None, "can_thay_the": None,
            "ghi_chu": "Thiếu ngay_lap_dat, không tính được RUL",
        }

    tuoi_nam = (ngay_tinh - ngay_lap).days / 365.25

    # Phat theo gio van hanh vuot muc ky vong (8h/ngay)
    gio = _f(thuoc_tinh.get("gio_van_hanh"), None)
    phat_gio = 0.0
    if gio is not None and tuoi_nam > 0:
        gio_ky_vong = tuoi_nam * 365.25 * 8
        if gio_ky_vong > 0 and gio > gio_ky_vong:
            phat_gio = tuoi_tho * dm["suy_giam_nam"] * (gio / gio_ky_vong - 1)

    # Phat theo su co: moi lan su co mat 1 nam tuoi tho nhan suy_giam
    so_su_co = _f(thuoc_tinh.get("so_lan_su_co"), 0.0) or 0.0
    phat_su_co = so_su_co * tuoi_tho * dm["suy_giam_nam"]

    # Thuong neu bao tri dung han: toi da 10% tuoi tho
    thuong = 0.0
    ngay_bt = _ngay(thuoc_tinh.get("ngay_bao_tri_cuoi"))
    chu_ky = int(_f(thuoc_tinh.get("chu_ky_bao_tri_thang"),
                    dm["chu_ky_bao_tri_thang"]))
    if ngay_bt is not None and chu_ky > 0:
        thang_tu_lan_cuoi = (ngay_tinh - ngay_bt).days / 30.44
        if thang_tu_lan_cuoi <= chu_ky:
            thuong = tuoi_tho * 0.10

    rul_nam = tuoi_tho - tuoi_nam - phat_gio - phat_su_co + thuong
    rul_nam = max(0.0, rul_nam)

    return {
        "rul_nam": round(rul_nam, 2),
        "rul_ngay": round(rul_nam * 365.25, 1),
        "tuoi_nam": round(tuoi_nam, 2),
        "ty_le_con_lai": round(rul_nam / tuoi_tho, 3) if tuoi_tho else None,
        "can_thay_the": rul_nam <= 0,
        "ghi_chu": None,
    }


def gan_vao_do_thi(G: nx.DiGraph, ngay_tinh: date | None = None,
                   dinh_muc: dict | None = None) -> nx.DiGraph:
    """Tinh RUL cho moi node va ghi vao thuoc tinh rul_nam, rul_ngay."""
    dm = dinh_muc if dinh_muc is not None else nap_dinh_muc()
    for n, d in G.nodes(data=True):
        kq = tinh_rul_node(d, dm, ngay_tinh)
        if kq["rul_nam"] is not None:
            d["rul_nam"] = kq["rul_nam"]
            d["rul_ngay"] = kq["rul_ngay"]
            d["ty_le_con_lai"] = kq["ty_le_con_lai"]
    return G


def _f(v, mac_dinh):
    if v is None or v == "":
        return mac_dinh
    try:
        return float(v)
    except (TypeError, ValueError):
        return mac_dinh


def _ngay(v) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    for dinh_dang in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(v).strip(), dinh_dang).date()
        except ValueError:
            continue
    return None
