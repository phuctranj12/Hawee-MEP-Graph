# -*- coding: utf-8 -*-
"""Sinh cau Cypher tuong duong cho moi phep truy xuat.

Moi tool trong MCP server tra ve ket qua KEM cau Cypher tuong duong. Hai muc dich:

1. Nguoi dung kiem chung duoc ket qua bang cach chay lai truy van tren Neo4j.
2. Khi chuyen sang giai doan B (Neo4j lam backend), cac cau nay chay duoc
   ngay, khong phai viet lai.

Quy uoc anh xa sang Neo4j:
    - Moi node co label :ThietBi va them label theo loai (vi du :Busway)
    - Thuoc tinh node giu nguyen ten trong schema
    - Canh cap nguon:  (a)-[:CAP_NGUON]->(b)
    - Canh di trong:   (a)-[:DI_TRONG]->(b)
"""
from __future__ import annotations

NHAN_NEO4J = {
    "nguon_luoi": "NguonLuoi",
    "may_bien_ap": "MayBienAp",
    "may_phat": "MayPhat",
    "ats": "ATS",
    "tu_tong": "TuTong",
    "tu_phan_phoi": "TuPhanPhoi",
    "busway": "Busway",
    "noi_mem": "NoiMem",
    "thang_mang_cap": "ThangMangCap",
    "tuyen_cap": "TuyenCap",
    "mach": "Mach",
    "phu_tai": "PhuTai",
}

LOAI_CANH_NEO4J = {
    "supplies": "CAP_NGUON",
    "routed_in": "DI_TRONG",
    "controls": "DIEU_KHIEN",
    "backup_for": "DU_PHONG_CHO",
}


def _esc(s: str) -> str:
    """Escape dau nhay don trong chuoi Cypher."""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def truy_vet_thuong_nguon(node_id: str) -> str:
    return (
        f"MATCH duong = (goc:ThietBi)-[:CAP_NGUON*]->(n:ThietBi {{id: '{_esc(node_id)}'}})\n"
        f"WHERE NOT ()-[:CAP_NGUON]->(goc)\n"
        f"RETURN [x IN nodes(duong) | {{id: x.id, ten: x.ten, loai: x.loai}}] AS duong_cap_nguon\n"
        f"ORDER BY length(duong) DESC"
    )


def truy_vet_ha_nguon(node_id: str, chi_thiet_bi: bool = True) -> str:
    loc = (
        "\nWHERE NOT m.loai IN ['mach', 'phu_tai']" if chi_thiet_bi else ""
    )
    return (
        f"MATCH (n:ThietBi {{id: '{_esc(node_id)}'}})-[:CAP_NGUON*]->(m:ThietBi){loc}\n"
        f"RETURN m.id AS id, m.ten AS ten, m.loai AS loai,\n"
        f"       m.cong_trinh AS cong_trinh, m.tang AS tang"
    )


def anh_huong_mat_dien(node_id: str) -> str:
    return (
        f"MATCH (n:ThietBi {{id: '{_esc(node_id)}'}})\n"
        f"OPTIONAL MATCH (n)-[:CAP_NGUON*]->(m:ThietBi)\n"
        f"WITH n, collect(DISTINCT m) AS anh_huong\n"
        f"RETURN n.ten AS thiet_bi,\n"
        f"       size([x IN anh_huong WHERE NOT x.loai IN ['mach','phu_tai']]) AS so_thiet_bi,\n"
        f"       size([x IN anh_huong WHERE x.loai = 'phu_tai']) AS so_phu_tai,\n"
        # CHI cong tai cua phu tai cuoi. Cong ca node trung gian se dem trung,
        # vi tu dien thuong mang san con so cong don ha nguon (xem query.py).
        f"       reduce(s = 0.0, x IN [y IN anh_huong WHERE y.loai = 'phu_tai'] "
        f"| s + coalesce(x.cong_suat_kVA, 0)) AS tong_cong_suat_phu_tai_kVA,\n"
        f"       n.cong_suat_cong_don_revit_kVA AS cong_suat_cong_don_revit_kVA,\n"
        f"       [x IN anh_huong WHERE x.loai IN ['tu_tong','tu_phan_phoi'] | x.ten] AS cac_tu"
    )


def xep_hang_rui_ro(so_luong: int = 10, loai: str | None = None) -> str:
    loc = f"\nWHERE n.loai = '{_esc(loai)}'" if loai else (
        "\nWHERE NOT n.loai IN ['mach', 'phu_tai', 'nguon_luoi']"
    )
    return (
        f"MATCH (n:ThietBi){loc}\n"
        f"RETURN n.id AS id, n.ten AS ten, n.loai AS loai,\n"
        f"       n.diem_rui_ro AS diem_rui_ro,\n"
        f"       n.so_thiet_bi_ha_nguon AS so_ha_nguon,\n"
        f"       n.cong_suat_lan_truyen AS cong_suat_kVA,\n"
        f"       n.so_hieu_ban_ve AS ban_ve\n"
        f"ORDER BY n.diem_rui_ro DESC\n"
        f"LIMIT {int(so_luong)}"
    )


def diem_don(node_id: str) -> str:
    """Tim diem hong don (single point of failure) tren duong cap nguon."""
    return (
        f"MATCH (n:ThietBi {{id: '{_esc(node_id)}'}})\n"
        f"MATCH duong = (goc:ThietBi)-[:CAP_NGUON*]->(n)\n"
        f"WHERE NOT ()-[:CAP_NGUON]->(goc)\n"
        f"WITH n, nodes(duong) AS tren_duong\n"
        f"UNWIND tren_duong AS x\n"
        f"MATCH (x)\n"
        f"WHERE size([(y)-[:CAP_NGUON]->(x) | y]) <= 1\n"
        f"RETURN DISTINCT x.id AS id, x.ten AS ten, x.loai AS loai"
    )


def tim_theo_ten(tu_khoa: str, so_luong: int = 20) -> str:
    return (
        f"MATCH (n:ThietBi)\n"
        f"WHERE toLower(n.ten) CONTAINS toLower('{_esc(tu_khoa)}')\n"
        f"   OR toLower(coalesce(n.ma_thiet_bi, '')) CONTAINS toLower('{_esc(tu_khoa)}')\n"
        f"RETURN n.id AS id, n.ten AS ten, n.loai AS loai,\n"
        f"       n.cong_trinh AS cong_trinh, n.tang AS tang\n"
        f"LIMIT {int(so_luong)}"
    )


def cong_viec_den_han(so_thang: int = 3) -> str:
    return (
        f"MATCH (n:ThietBi)-[:CAN_BAO_TRI]->(cv:CongViec)\n"
        f"WHERE cv.thang_con_lai <= {int(so_thang)}\n"
        f"RETURN n.ten AS thiet_bi, n.loai AS loai, n.diem_rui_ro AS rui_ro,\n"
        f"       cv.ma_cv AS ma_cv, cv.mo_ta AS cong_viec,\n"
        f"       cv.gio_cong AS gio_cong, cv.chi_phi_vnd AS chi_phi,\n"
        f"       cv.chung_chi_yeu_cau AS chung_chi\n"
        f"ORDER BY n.diem_rui_ro DESC, cv.uu_tien ASC"
    )


def nap_do_thi() -> str:
    """Cau Cypher mau de nap do thi vao Neo4j (dung o giai doan B)."""
    return (
        "// Rang buoc duy nhat\n"
        "CREATE CONSTRAINT thiet_bi_id IF NOT EXISTS\n"
        "FOR (n:ThietBi) REQUIRE n.id IS UNIQUE;\n\n"
        "// Nap node tu CSV da xuat\n"
        "LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS d\n"
        "MERGE (n:ThietBi {id: d.id})\n"
        "SET n += d;\n\n"
        "// Nap canh cap nguon\n"
        "LOAD CSV WITH HEADERS FROM 'file:///edges.csv' AS d\n"
        "MATCH (a:ThietBi {id: d.source}), (b:ThietBi {id: d.target})\n"
        "WHERE d.loai = 'supplies'\n"
        "MERGE (a)-[r:CAP_NGUON]->(b)\n"
        "SET r.so_mach = d.so_mach, r.thiet_bi_bao_ve = d.thiet_bi_bao_ve;"
    )
