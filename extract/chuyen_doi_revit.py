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

import re
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
    # Busway Siemens LI: tham so tuyen nam tren tung doan thanh dan
    "Busbar run number": "ma_tuyen",
    "Busbar run description": "mo_ta_tuyen",
    # Sinh ra o buoc gop_busway_va_tu, khong co trong Revit
    "so_phan_tu_gop": "so_phan_tu_gop",
    "revit_ids_gop": "revit_ids_gop",
    "suy_dien": "suy_dien",
}

# Ten tham so dong dinh muc cua busway Siemens LI
THAM_SO_INC = "Max. permissible operational current Inc (horizontal edgewise) (A)"

# Nối mềm cach dau tu duoi nguong nay (m) thi coi la o phia tu do
NGUONG_NOI_MEM_M = 5.0


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


def _chuan_hoa_ten(s) -> str:
    """'MDB-F12', 'MDB.F12', 'mdb f12' -> 'mdbf12' de so khop ten tu."""
    return re.sub(r"[^0-9a-z]", "", str(s or "").lower())


def _so_hoac_none(v) -> float | None:
    try:
        return float(str(v).split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def _toa_do(d: dict) -> tuple | None:
    try:
        return float(d["x"]), float(d["y"]), float(d["z"])
    except (KeyError, TypeError, ValueError):
        return None


def gop_busway_va_tu(G_vao: nx.DiGraph) -> nx.DiGraph:
    """Dung quan he cap nguon tu tham so busway, khi model khong co circuit.

    Model busway thuc te (nhu Hon Thom) khong co Electrical Circuit nao. Quan
    he cap nguon nam o tham so cua tung doan thanh dan Siemens LI:

        Busbar run number      = P12
        Busbar run description = From MSB3 To MDB-F12

    Ham nay tra ve do thi Revit da duoc sap xep lai:
      - Moi tuyen (theo run number) gop thanh MOT node busway, thay cho hang
        chuc doan thang, co, te. Chieu dai = tong Engineered length.
      - Tu cung Panel Name gop thanh mot node: tu nhieu ngan (MSB3 ve bang 8
        family instance) van la mot tu ve mat van hanh.
      - Canh nguon -> tuyen -> dich lay tu "From X To Y". Dau nao khong co
        trong model (vi du may bien ap TR-01-F nam o model khac) thi tao node
        gia, danh dau suy_dien=1.
      - Noi mem (flexible link) gan vao tuyen gan nhat theo toa do.

    Model khong co tham so busway thi tra ve nguyen G_vao.
    """
    tuyen: dict[str, list] = {}
    for n, d in G_vao.nodes(data=True):
        so = str(d.get("Busbar run number") or "").strip()
        if so:
            tuyen.setdefault(so, []).append(n)
    if not tuyen:
        return G_vao

    H = nx.DiGraph()
    H.graph.update(G_vao.graph)
    da_gop: set = set()

    # 1. Gop tu cung ten
    nhom_tu: dict[str, list] = {}
    for n, d in G_vao.nodes(data=True):
        if d.get("category") == "Electrical Equipment":
            ten = d.get("Panel Name") or d.get("name")
            if ten:
                nhom_tu.setdefault(_chuan_hoa_ten(ten), []).append(n)
    tu_theo_ten: dict[str, str] = {}
    for khoa, ds in nhom_tu.items():
        ds = sorted(ds, key=str)
        dai_dien = ds[0]
        attrs = dict(G_vao.nodes[dai_dien])
        if len(ds) > 1:
            attrs["so_phan_tu_gop"] = len(ds)
            attrs["revit_ids_gop"] = ",".join(map(str, ds))
        H.add_node(dai_dien, **attrs)
        tu_theo_ten[khoa] = dai_dien
        da_gop.update(ds)

    def _dau_tuyen(ten: str) -> str:
        khoa = _chuan_hoa_ten(ten)
        if khoa in tu_theo_ten:
            return tu_theo_ten[khoa]
        nid = "suy_dien:" + ten
        if nid not in H:
            attrs = {"name": ten, "category": "Electrical Equipment",
                     "suy_dien": 1}
            if re.match(r"^(tr|mba)[\s\-_.]?\d", ten, re.I):
                attrs["part_type"] = "Transformer"
            H.add_node(nid, **attrs)
        return nid

    # 2. Gop tuyen busway
    toa_do_tuyen: dict[str, list] = {}
    for so, ds in sorted(tuyen.items()):
        mau = G_vao.nodes[ds[0]]
        dai_mm = sum(_so_hoac_none(G_vao.nodes[m].get("Engineered length"))
                     or 0.0 for m in ds)
        inc = [_so_hoac_none(G_vao.nodes[m].get(THAM_SO_INC)) for m in ds]
        inc = [x for x in inc if x]
        nid = "busway:" + so
        attrs = {
            "name": "Busway " + so,
            "category": "Busbar run",
            "Busbar run number": so,
            "so_phan_tu_gop": len(ds),
            "revit_ids_gop": ",".join(map(str, ds)),
        }
        mo_ta = mau.get("Busbar run description")
        if mo_ta:
            attrs["Busbar run description"] = mo_ta
        if dai_mm:
            attrs["Length"] = round(dai_mm / 1000.0, 2)
        if inc:
            attrs["Rating"] = min(inc)
        H.add_node(nid, **attrs)
        da_gop.update(ds)
        toa_do_tuyen[nid] = [t for t in (_toa_do(G_vao.nodes[m]) for m in ds)
                             if t]

        m = re.match(r"^\s*from\s+(.+?)\s+to\s+(.+?)\s*$", str(mo_ta or ""),
                     re.I)
        if m:
            H.add_edge(_dau_tuyen(m.group(1)), nid, loai="supplies")
            H.add_edge(nid, _dau_tuyen(m.group(2)), loai="supplies")

    # 3. Noi mem: gan vao tuyen gan nhat, gop cac pha cung tuyen
    noi_mem: dict[str, list] = {}
    for n, d in G_vao.nodes(data=True):
        ten = (str(d.get("name") or "") + " " +
               str(d.get("family") or "")).lower()
        if n in da_gop or not any(
                k in ten for k in ("flexible link", "flex link", "noi mem",
                                   "nối mềm")):
            continue
        p = _toa_do(d)
        if p is None or not toa_do_tuyen:
            continue
        gan_nhat = min(
            toa_do_tuyen,
            key=lambda t: min((_kc(p, q) for q in toa_do_tuyen[t]),
                              default=float("inf")),
        )
        noi_mem.setdefault(gan_nhat, []).append(n)
        da_gop.add(n)

    for t, ds in noi_mem.items():
        nid = "noi_mem:" + t.split(":", 1)[1]
        H.add_node(nid, name="Nối mềm " + t.split(":", 1)[1],
                   category="Flexible link", so_phan_tu_gop=len(ds),
                   revit_ids_gop=",".join(map(str, ds)))
        # Chen vao phia dau tuyen co tu nam gan noi mem
        tam = _trung_binh([_toa_do(G_vao.nodes[m]) for m in ds])
        nguon = next(iter(H.predecessors(t)), None)
        dich = next(iter(H.successors(t)), None)
        if dich is not None and tam and _gan_tu(H, dich, tam):
            H.remove_edge(t, dich)
            H.add_edge(t, nid, loai="supplies")
            H.add_edge(nid, dich, loai="supplies")
        elif nguon is not None:
            H.remove_edge(nguon, t)
            H.add_edge(nguon, nid, loai="supplies")
            H.add_edge(nid, t, loai="supplies")

    # 4. Giu phan con lai (mach, phu tai...) va canh cua chung
    for n, d in G_vao.nodes(data=True):
        if n not in da_gop:
            H.add_node(n, **d)
    for u, v, d in G_vao.edges(data=True):
        if u in H and v in H and not H.has_edge(u, v):
            H.add_edge(u, v, **d)
    return H


def _kc(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _trung_binh(ds):
    ds = [x for x in ds if x]
    if not ds:
        return None
    return tuple(sum(c) / len(ds) for c in zip(*ds))


def _gan_tu(H: nx.DiGraph, tu: str, p) -> bool:
    q = _toa_do(H.nodes[tu])
    return q is not None and _kc(p, q) <= NGUONG_NOI_MEM_M


def chuyen_doi(G_vao: nx.DiGraph, ten_do_thi: str = "",
               ma_du_an: str = "") -> nx.DiGraph:
    """Chuyen do thi Revit sang schema Hawee."""
    G_vao = gop_busway_va_tu(G_vao)
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
