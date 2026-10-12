# -*- coding: utf-8 -*-
"""Dinh nghia kieu node, kieu canh va kiem tra tinh dung dan cua do thi.

Ma dinh danh dung ASCII; nhan hien thi tieng Viet nam trong NHAN_NODE.
Xem schema/hawee_mep_v1.md
"""
from __future__ import annotations

import networkx as nx

# --- Loai node -------------------------------------------------------------

NHAN_NODE: dict[str, str] = {
    "nguon_luoi": "Nguồn lưới / Trạm biến áp EVN",
    "may_bien_ap": "Máy biến áp",
    "may_phat": "Máy phát điện dự phòng",
    "ats": "Bộ chuyển nguồn tự động (ATS)",
    "tu_tong": "Tủ điện tổng (MSB)",
    "tu_phan_phoi": "Tủ phân phối (MDB/DB)",
    "busway": "Tuyến thanh dẫn (busway)",
    "noi_mem": "Nối mềm (flexible link)",
    "thang_mang_cap": "Thang / máng cáp",
    "tuyen_cap": "Tuyến cáp",
    "mach": "Mạch (circuit)",
    "phu_tai": "Phụ tải cuối",
}

LOAI_NODE = frozenset(NHAN_NODE)

# Node duoc coi la nguon (hop le khi khong co thuong nguon)
LOAI_NGUON = frozenset({"nguon_luoi", "may_phat"})

# Node khong phai thiet bi can bao tri (bo qua khi xep hang rui ro)
LOAI_BO_QUA_BAO_TRI = frozenset({"nguon_luoi", "mach", "phu_tai"})

# --- Loai canh -------------------------------------------------------------

NHAN_CANH: dict[str, str] = {
    "supplies": "Cấp nguồn cho",
    "routed_in": "Đi trong",
    "controls": "Điều khiển",
    "backup_for": "Dự phòng cho",
}

LOAI_CANH = frozenset(NHAN_CANH)

# Chi loai canh nay dung de truy vet nguon va tinh rui ro
CANH_CAP_NGUON = "supplies"


def nhan(loai: str) -> str:
    """Tra nhan tieng Viet cua mot ma loai node hoac canh."""
    return NHAN_NODE.get(loai) or NHAN_CANH.get(loai) or loai


def do_thi_cap_nguon(G: nx.DiGraph) -> nx.DiGraph:
    """Tra ve do thi con chi gom canh 'supplies'.

    Moi phep truy vet nguon va tinh rui ro PHAI chay tren do thi nay.
    Tinh tren ca do thi goc se sai, vi canh 'routed_in' va 'controls'
    khong truyen cong suat.
    """
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        if d.get("loai", CANH_CAP_NGUON) == CANH_CAP_NGUON:
            H.add_edge(u, v, **d)
    return H


# --- Kiem tra tinh dung dan ------------------------------------------------

def kiem_tra_do_thi(G: nx.DiGraph) -> dict:
    """Kiem tra do thi theo rang buoc trong schema v1.

    Tra ve dict:
        hop_le: bool            - khong co loi nghiem trong
        loi: list[dict]         - vi pham rang buoc
        canh_bao: list[dict]    - dau hieu dang ngo, khong chan
        thong_ke: dict
    """
    loi: list[dict] = []
    canh_bao: list[dict] = []

    # 1. Loai node hop le
    for n, d in G.nodes(data=True):
        lo = d.get("loai")
        if lo is None:
            loi.append({"ma": "thieu_loai", "node": n,
                        "thong_diep": "Node không có thuộc tính 'loai'"})
        elif lo not in LOAI_NODE:
            loi.append({"ma": "loai_khong_hop_le", "node": n,
                        "thong_diep": f"Loại '{lo}' không có trong schema"})

    # 2. Loai canh hop le
    for u, v, d in G.edges(data=True):
        lo = d.get("loai", CANH_CAP_NGUON)
        if lo not in LOAI_CANH:
            loi.append({"ma": "canh_khong_hop_le", "node": f"{u}->{v}",
                        "thong_diep": f"Loại cạnh '{lo}' không có trong schema"})

    S = do_thi_cap_nguon(G)

    # 3. Khong co chu trinh tren canh cap nguon (tru chu trinh qua ATS)
    if not nx.is_directed_acyclic_graph(S):
        for chu_trinh in nx.simple_cycles(S):
            if not any(G.nodes[n].get("loai") == "ats" for n in chu_trinh):
                loi.append({
                    "ma": "chu_trinh",
                    "node": " -> ".join(str(x) for x in chu_trinh[:6]),
                    "thong_diep": "Chu trình cấp nguồn không đi qua ATS",
                })

    # 4. Node khong co nguon cap
    for n, d in S.nodes(data=True):
        if S.in_degree(n) == 0 and d.get("loai") not in LOAI_NGUON:
            canh_bao.append({
                "ma": "khong_co_nguon", "node": n,
                "thong_diep": f"'{d.get('ten', n)}' không có nguồn cấp. "
                              "Có thể model Revit chưa nối mạch.",
            })

    # 5. Busway treo lo lung
    for n, d in S.nodes(data=True):
        if d.get("loai") == "busway":
            if S.in_degree(n) == 0 or S.out_degree(n) == 0:
                loi.append({
                    "ma": "busway_ho", "node": n,
                    "thong_diep": f"Busway '{d.get('ten', n)}' thiếu thượng "
                                  "nguồn hoặc hạ nguồn",
                })

    # 6. Dong dinh muc ha nguon lon hon thuong nguon
    for u, v in S.edges():
        a = _so(S.nodes[u].get("dong_dien_dinh_muc_A"))
        b = _so(S.nodes[v].get("dong_dien_dinh_muc_A"))
        if a is not None and b is not None and b > a:
            canh_bao.append({
                "ma": "dong_nghich", "node": f"{u}->{v}",
                "thong_diep": (
                    f"'{S.nodes[v].get('ten', v)}' ({b:g}A) có dòng định mức "
                    f"lớn hơn thượng nguồn '{S.nodes[u].get('ten', u)}' ({a:g}A)"
                ),
            })

    thong_ke = {
        "so_node": G.number_of_nodes(),
        "so_canh": G.number_of_edges(),
        "so_canh_cap_nguon": S.number_of_edges(),
        "theo_loai": _dem_loai(G),
        "so_goc": sum(1 for n in S if S.in_degree(n) == 0),
    }
    return {"hop_le": not loi, "loi": loi, "canh_bao": canh_bao,
            "thong_ke": thong_ke}


def _so(v) -> float | None:
    """Doi gia tri ve float, tra None neu khong doi duoc.

    Can thiet vi GraphML luu moi thu duoi dang chuoi.
    """
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dem_loai(G: nx.DiGraph) -> dict[str, int]:
    d: dict[str, int] = {}
    for _, a in G.nodes(data=True):
        k = a.get("loai", "(không rõ)")
        d[k] = d.get(k, 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))
