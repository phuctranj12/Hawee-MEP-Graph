# -*- coding: utf-8 -*-
"""Chuyen do thi xuat tu Revit sang schema Hawee v1.

Dau vao: file GraphML xuat tu Revit, moi node co it nhat:
    category         ten category Revit doc duoc
    part_type        Panelboard / Switchboard (neu co)
    name             ten thiet bi
    supply_from_id   id thiet bi cap nguon

Dau ra: do thi dung schema Hawee (.hmepg).

Nguyen tac loc: Revit xuat ra hang tram thuoc tinh, phan lon vo dung cho
van hanh. Module nay chi lay theo DANH SACH TRANG duoi day.

Chay truc tiep:
    python extract/chuyen_doi_revit.py vao.graphml ra.hmepg
"""
from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hawee_mep import io_graphml, risk  # noqa: E402

# --- anh xa category Revit -> loai node Hawee ------------------------------

THEO_PART_TYPE = {
    "Switchboard": "tu_tong",
    "Panelboard": "tu_phan_phoi",
    "Transformer": "may_bien_ap",
}

THEO_CATEGORY = {
    "Electrical Equipment": "tu_phan_phoi",
    "Electrical Circuit": "mach",
    "Electrical Fixtures": "phu_tai",
    "Lighting Fixtures": "phu_tai",
    "Lighting Devices": "phu_tai",
    "Data Devices": "phu_tai",
    "Cable Tray Fittings": "thang_mang_cap",
    "Cable Trays": "thang_mang_cap",
    "Conduits": "tuyen_cap",
    "Conduit Fittings": "tuyen_cap",
}

# Tu khoa trong ten thiet bi -> loai, uu tien cao nhat vi phan anh thuc te
# cong trinh Hawee (busway thuong duoc mo hinh hoa bang category khac)
THEO_TEN = [
    (("busway", "busduct", "thanh dan", "thanh dẫn"), "busway"),
    (("flexible link", "flex link", "noi mem", "nối mềm"), "noi_mem"),
    (("ats",), "ats"),
    (("generator", "may phat", "máy phát"), "may_phat"),
    (("msb", "switchboard"), "tu_tong"),
    (("mdb", "panelboard"), "tu_phan_phoi"),
]

# Thuoc tinh Revit co don vi VA, phai chia 1000 de ra kVA.
# Revit xuat "Total Connected" theo VA (vi du 165095 VA = 165 kVA); neu gan
# truc tiep vao cong_suat_kVA thi moi con so cong suat se sai 1000 lan.
CHIA_1000 = {"cong_suat_VA": "cong_suat_kVA"}

# Thuoc tinh Revit -> thuoc tinh Hawee
ANH_XA_THUOC_TINH = {
    "name": "ten",
    "Panel Name": "ten",
    "Mark": "ma_thiet_bi",
    "Level": "tang",
    "Sheet Number": "so_hieu_ban_ve",
    "Voltage": "dien_ap_V",
    "Rating": "dong_dien_dinh_muc_A",
    "Mains": "dong_dien_dinh_muc_A",
    "Number of Phases": "so_pha",
    "Apparent Load": "cong_suat_VA",
    "Total Connected": "cong_suat_VA",
    "Short Circuit Rating": "dong_ngan_mach_kA",
    "Manufacturer": "nha_san_xuat",
    "Model": "model",
    "Length": "chieu_dai_m",
    "Comments": "ghi_chu",
}


def doan_loai(thuoc_tinh: dict) -> str:
    """Doan loai node Hawee tu thuoc tinh Revit.

    Thu tu uu tien: ten thiet bi -> part_type -> category.
    Ten duoc uu tien vi busway trong model thuc te thuong nam duoi category
    'Cable Tray Fittings' (nhu model Hon Thom), chi ten moi noi dung ban chat.
    """
    ten = str(thuoc_tinh.get("name") or thuoc_tinh.get("ten") or "").lower()
    for tu_khoa, loai in THEO_TEN:
        if any(k in ten for k in tu_khoa):
            return loai

    pt = thuoc_tinh.get("part_type")
    if pt in THEO_PART_TYPE:
        return THEO_PART_TYPE[pt]

    cat = thuoc_tinh.get("category")
    if cat in THEO_CATEGORY:
        return THEO_CATEGORY[cat]

    return "phu_tai"


def doan_cong_trinh(thuoc_tinh: dict) -> str | None:
    """Doan ma khoi nha tu ten tang, vi du 'F11.TANG HAM' -> 'F11'."""
    for khoa in ("tang", "Level", "name"):
        v = str(thuoc_tinh.get(khoa) or "")
        if "." in v:
            dau = v.split(".")[0].strip()
            if 1 <= len(dau) <= 6 and any(c.isdigit() for c in dau):
                return dau
    return None


def chuyen_doi(G_vao: nx.DiGraph, ten_do_thi: str = "",
               ma_du_an: str = "") -> nx.DiGraph:
    """Chuyen do thi Revit sang schema Hawee."""
    G = nx.DiGraph()
    G.graph["ten_do_thi"] = ten_do_thi or G_vao.graph.get("ten_do_thi", "")
    if ma_du_an:
        G.graph["ma_du_an"] = ma_du_an
    G.graph["schema"] = "hawee_mep_v1"

    for n, d in G_vao.nodes(data=True):
        moi: dict = {"loai": doan_loai(d)}
        for k_revit, k_hawee in ANH_XA_THUOC_TINH.items():
            v = d.get(k_revit)
            if v not in (None, "") and k_hawee not in moi:
                moi[k_hawee] = v
        moi.setdefault("ten", str(n))

        # Doi don vi VA -> kVA
        for k_va, k_kva in CHIA_1000.items():
            if k_va in moi:
                try:
                    moi[k_kva] = round(float(moi.pop(k_va)) / 1000.0, 3)
                except (TypeError, ValueError):
                    moi.pop(k_va, None)

        # Revit ghi "Total Connected" cua MOT TU la tong CONG DON ca ha nguon.
        # Neu de nguyen o node tu roi cong don lai khi lan truyen thi moi muc
        # trung gian bi dem lai mot lan nua (tu tong tung ra 39.558 kVA cho
        # mot he thuc te chi ~4.000 kVA).
        # Cach xu ly: chi phu tai cuoi giu cong_suat_kVA. Tu va mach giu con
        # so cong don cua Revit o truong rieng, chi de tham khieu va doi chieu.
        if moi["loai"] != "phu_tai" and "cong_suat_kVA" in moi:
            moi["cong_suat_cong_don_revit_kVA"] = moi.pop("cong_suat_kVA")

        # Revit tra ve "Level" la ElementId (chuoi toan so), khong phai ten
        # tang. Giu lai de truy nguoc nhung khong de o truong 'tang', vi
        # hien "tang: 1363065" cho nguoi van hanh la vo nghia.
        if str(moi.get("tang", "")).strip().isdigit():
            moi["revit_level_id"] = str(moi.pop("tang")).strip()

        # Revit tra 0 cho thong so chua khai bao; 0 khac han voi "khong biet"
        # va se lam sai moi phep so sanh dong dinh muc.
        for k in ("dien_ap_V", "dong_dien_dinh_muc_A", "dong_ngan_mach_kA",
                  "so_pha", "chieu_dai_m"):
            try:
                if k in moi and float(moi[k]) == 0:
                    moi.pop(k)
            except (TypeError, ValueError):
                pass

        ct = doan_cong_trinh({**d, **moi})
        if ct:
            moi["cong_trinh"] = ct

        # Revit dat ten node mach bang so mach tran ("2", "14"), doc rat kho
        # khi hien trong duong truy vet. Them tien to cho de doc.
        if moi["loai"] == "mach" and str(moi.get("ten", "")).strip().isdigit():
            moi["so_mach"] = str(moi["ten"]).strip()
            moi["ten"] = f"Mạch {moi['so_mach']}"

        # Giu lai nguon goc de truy nguoc ve Revit
        moi["revit_id"] = str(n)
        if d.get("category"):
            moi["revit_category"] = d["category"]
        G.add_node(str(n), **moi)

    # Canh cap nguon: uu tien supply_from_id, KHONG dung supply_from_name
    # vi truong do khong dang tin (nhieu node tra ve so mach thay vi ten tu)
    so_canh_tu_id = 0
    for n, d in G_vao.nodes(data=True):
        nguon = d.get("supply_from_id")
        if nguon and str(nguon) in G and str(nguon) != str(n):
            G.add_edge(str(nguon), str(n), loai="supplies")
            so_canh_tu_id += 1

    # Bo sung canh san co trong do thi vao, neu chua co
    for u, v, d in G_vao.edges(data=True):
        if str(u) in G and str(v) in G and not G.has_edge(str(u), str(v)):
            G.add_edge(str(u), str(v), loai=d.get("loai", "supplies"))

    G.graph["so_canh_tu_supply_from_id"] = so_canh_tu_id
    return G


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        print("Dung: python extract/chuyen_doi_revit.py <vao.graphml> <ra.hmepg>")
        return 1

    vao, ra = sys.argv[1], sys.argv[2]
    print(f"Doc {vao} ...")
    G_vao = io_graphml.doc(vao)
    print(f"  {G_vao.number_of_nodes()} node, {G_vao.number_of_edges()} canh")

    G = chuyen_doi(G_vao, ten_do_thi=Path(vao).stem)
    print(f"Chuyen doi xong: {G.number_of_nodes()} node, "
          f"{G.number_of_edges()} canh")

    risk.gan_vao_do_thi(G)
    io_graphml.ghi(G, ra)
    print(f"Da ghi {ra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
