# -*- coding: utf-8 -*-
"""Lop truy xuat do thi - phan Claude goi qua MCP.

Day la "retrieval" cua Graph RAG: thay vi tim theo do tuong dong vector,
ta duyet theo cau truc do thi. Voi he phan phoi dien (hinh cay, quan he
cap nguon ro rang) cach nay chinh xac hon han tim theo vector.

Moi ham tra ve dict co khoa 'cypher' chua cau truy van tuong duong, de
nguoi dung kiem chung va de chuyen sang Neo4j o giai doan B.
"""
from __future__ import annotations

import csv
from pathlib import Path

import networkx as nx

from . import cypher as cy
from .model import LOAI_BO_QUA_BAO_TRI, NHAN_NODE, do_thi_cap_nguon

THU_MUC_DATA = Path(__file__).resolve().parent.parent / "data"


class DoThiCoDien:
    """Boc do thi va cung cap cac phep truy xuat nghiep vu."""

    def __init__(self, G: nx.DiGraph):
        self.G = G
        self.S = do_thi_cap_nguon(G)

    # --- tim kiem ----------------------------------------------------------

    def tim(self, tu_khoa: str, so_luong: int = 20) -> dict:
        """Tim node theo ten hoac ma thiet bi, khong phan biet chu hoa."""
        tk = tu_khoa.strip().lower()
        kq = []
        for n, d in self.G.nodes(data=True):
            ten = str(d.get("ten", n)).lower()
            ma = str(d.get("ma_thiet_bi", "")).lower()
            if tk in ten or (ma and tk in ma):
                kq.append(self._tom_tat(n))
        kq.sort(key=lambda x: (len(str(x["ten"])), str(x["ten"])))
        return {
            "tu_khoa": tu_khoa,
            "so_tim_thay": len(kq),
            "ket_qua": kq[:so_luong],
            "cypher": cy.tim_theo_ten(tu_khoa, so_luong),
        }

    # --- truy vet ----------------------------------------------------------

    def truy_vet_thuong_nguon(self, node_id: str) -> dict:
        """Truy nguoc duong cap nguon: thiet bi nay lay dien tu dau.

        Tra ve tat ca duong tu goc den node, vi mot tu co the co nhieu nguon
        (dien luoi va may phat).
        """
        if node_id not in self.S:
            return self._khong_thay(node_id)

        goc = [n for n in self.S if self.S.in_degree(n) == 0]
        duong_di = []
        for g in goc:
            for duong in nx.all_simple_paths(self.S, g, node_id):
                duong_di.append([self._tom_tat(x) for x in duong])

        return {
            "thiet_bi": self._tom_tat(node_id),
            "so_duong_cap_nguon": len(duong_di),
            "co_du_phong": len(duong_di) > 1,
            "cac_duong": duong_di,
            "diem_hong_don": self.diem_hong_don(node_id)["diem_hong_don"],
            "cypher": cy.truy_vet_thuong_nguon(node_id),
        }

    def truy_vet_ha_nguon(self, node_id: str,
                          chi_thiet_bi: bool = True) -> dict:
        """Liet ke thiet bi phia sau: thiet bi nay cap dien cho nhung gi."""
        if node_id not in self.S:
            return self._khong_thay(node_id)

        hau_due = nx.descendants(self.S, node_id)
        if chi_thiet_bi:
            hau_due = {
                m for m in hau_due
                if self.S.nodes[m].get("loai") not in LOAI_BO_QUA_BAO_TRI
            }
        theo_loai: dict[str, list] = {}
        for m in hau_due:
            theo_loai.setdefault(
                self.S.nodes[m].get("loai", "?"), []
            ).append(self._tom_tat(m))

        return {
            "thiet_bi": self._tom_tat(node_id),
            "so_thiet_bi_ha_nguon": len(hau_due),
            "theo_loai": {k: v for k, v in sorted(theo_loai.items())},
            "cypher": cy.truy_vet_ha_nguon(node_id, chi_thiet_bi),
        }

    def diem_hong_don(self, node_id: str) -> dict:
        """Tim diem hong don: node nao hong thi node dich mat dien.

        Thuat toan: voi tung node tren duong cap nguon, thu bo node do ra
        khoi do thi; neu node dich khong con duong nao tu goc thi node vua
        bo la diem hong don.
        """
        if node_id not in self.S:
            return self._khong_thay(node_id)

        # Moi node co duong toi node dich deu nam trong to tien cua no
        tren_duong = nx.ancestors(self.S, node_id)

        diem_don = [self._tom_tat(x) for x in tren_duong
                    if node_id in self._mat_dien_khi_bo(x)]

        diem_don.sort(key=lambda d: -(d.get("diem_rui_ro") or 0))
        return {
            "thiet_bi": self._tom_tat(node_id),
            "diem_hong_don": diem_don,
            "giai_thich": (
                f"Có {len(diem_don)} thiết bị mà nếu hỏng sẽ làm "
                f"'{self._ten(node_id)}' mất điện hoàn toàn."
                if diem_don else
                f"'{self._ten(node_id)}' có nguồn dự phòng, không có điểm hỏng đơn."
            ),
            "cypher": cy.diem_don(node_id),
        }

    # --- phan tich ---------------------------------------------------------

    def anh_huong_mat_dien(self, node_id: str) -> dict:
        """Thiet bi nay hong thi mat dien o dau, bao nhieu tai."""
        if node_id not in self.S:
            return self._khong_thay(node_id)

        # Chi tinh node mat het nguon. Node con duong khac (vi du MSB3 co hai
        # may bien ap) thi mot nhanh hong khong lam no mat dien.
        hau_due = self._mat_dien_khi_bo(node_id)
        con_dien = len(nx.descendants(self.S, node_id)) - len(hau_due)
        thiet_bi, phu_tai = [], []
        tong_kVA = 0.0
        tang, cong_trinh = set(), set()

        for m in hau_due:
            d = self.S.nodes[m]
            # CHI cong tai cua phu tai cuoi. Cong ca node trung gian se dem
            # trung, vi tu dien thuong mang san con so cong don ha nguon.
            if d.get("loai") == "phu_tai":
                tong_kVA += float(d.get("cong_suat_kVA") or 0)
            if d.get("tang"):
                tang.add(str(d["tang"]))
            if d.get("cong_trinh"):
                cong_trinh.add(str(d["cong_trinh"]))
            if d.get("loai") == "phu_tai":
                phu_tai.append(self._tom_tat(m))
            elif d.get("loai") not in LOAI_BO_QUA_BAO_TRI:
                thiet_bi.append(self._tom_tat(m))

        # Neu phu tai cuoi khong co so lieu cong suat (rat pho bien trong
        # model Revit), dung con so cong don ma Revit ghi cho chinh node nay.
        nguon_so_lieu = "tổng tải của các phụ tải cuối"
        if tong_kVA == 0:
            dp = self.S.nodes[node_id].get("cong_suat_cong_don_revit_kVA")
            if dp not in (None, ""):
                try:
                    tong_kVA = float(dp)
                    nguon_so_lieu = (
                        "số cộng dồn Revit ghi cho thiết bị này "
                        "(phụ tải cuối không có số liệu công suất)"
                    )
                except (TypeError, ValueError):
                    pass
            if tong_kVA == 0:
                nguon_so_lieu = "không có số liệu công suất trong model"

        thiet_bi.sort(key=lambda d: -(d.get("diem_rui_ro") or 0))
        return {
            "thiet_bi": self._tom_tat(node_id),
            "tom_tat": (
                f"Nếu '{self._ten(node_id)}' hỏng: mất điện {len(thiet_bi)} "
                f"thiết bị và {len(phu_tai)} phụ tải, "
                f"tổng {tong_kVA:.1f} kVA"
                + (f", thuộc {len(cong_trinh)} khối: "
                   f"{', '.join(sorted(cong_trinh))}" if cong_trinh else "")
            ),
            "so_thiet_bi_mat_dien": len(thiet_bi),
            "so_phu_tai_mat_dien": len(phu_tai),
            "tong_cong_suat_kVA": round(tong_kVA, 2),
            "nguon_so_lieu_cong_suat": nguon_so_lieu,
            "so_node_con_dien_nho_du_phong": con_dien,
            "cac_khoi": sorted(cong_trinh),
            "cac_tang": sorted(tang),
            "thiet_bi_mat_dien": thiet_bi[:50],
            "cypher": cy.anh_huong_mat_dien(node_id),
        }

    def xep_hang_rui_ro(self, so_luong: int = 10,
                        loai: str | None = None) -> dict:
        """Xep hang thiet bi theo diem rui ro giam dan."""
        ds = []
        for n, d in self.G.nodes(data=True):
            if loai:
                if d.get("loai") != loai:
                    continue
            elif d.get("loai") in LOAI_BO_QUA_BAO_TRI | {"nguon_luoi"}:
                continue
            ds.append(self._tom_tat(n))

        thieu_diem = sum(1 for x in ds if x.get("diem_rui_ro") is None)
        ds.sort(key=lambda x: -(x.get("diem_rui_ro") or 0))
        kq = {
            "so_thiet_bi_xet": len(ds),
            "xep_hang": ds[:so_luong],
            "cypher": cy.xep_hang_rui_ro(so_luong, loai),
        }
        if thieu_diem:
            kq["canh_bao"] = (
                f"{thieu_diem} thiết bị chưa có điểm rủi ro. "
                "Chạy risk.gan_vao_do_thi(G) trước khi xếp hạng."
            )
        return kq

    # --- bao tri -----------------------------------------------------------

    def cong_viec_bao_tri(self, node_id: str | None = None,
                          loai: str | None = None) -> dict:
        """Tra cong viec bao tri theo mau, cho mot thiet bi hoac mot loai."""
        mau = _nap_cong_viec()

        if node_id:
            if node_id not in self.G:
                return self._khong_thay(node_id)
            loai = self.G.nodes[node_id].get("loai")

        cv = [x for x in mau if not loai or x["loai_thiet_bi"] == loai]
        cv.sort(key=lambda x: (int(x.get("uu_tien") or 3),
                               int(x.get("chu_ky_thang") or 999)))

        tong_gio = sum(float(x.get("gio_cong") or 0) for x in cv)
        tong_tien = sum(float(x.get("chi_phi_vnd") or 0) for x in cv)
        chung_chi = sorted({
            x["chung_chi_yeu_cau"] for x in cv
            if x.get("chung_chi_yeu_cau")
        })

        return {
            "thiet_bi": self._tom_tat(node_id) if node_id else None,
            "loai": loai,
            "nhan_loai": NHAN_NODE.get(loai, loai),
            "so_cong_viec": len(cv),
            "cong_viec": cv,
            "tong_gio_cong_mot_chu_ky": round(tong_gio, 2),
            "tong_chi_phi_vnd_mot_chu_ky": tong_tien,
            "chung_chi_can_co": chung_chi,
            "cypher": cy.cong_viec_den_han(),
            "ghi_chu": (
                "Giờ công và chi phí là giá trị tạm trong "
                "data/cong_viec_baotri.csv, Hawee cần thay bằng định mức thật."
            ),
        }

    # --- tong quan ---------------------------------------------------------

    def tong_quan(self) -> dict:
        """Thong ke tong quan do thi."""
        theo_loai: dict[str, int] = {}
        for _, d in self.G.nodes(data=True):
            k = d.get("loai", "(không rõ)")
            theo_loai[k] = theo_loai.get(k, 0) + 1

        goc = [n for n in self.S if self.S.in_degree(n) == 0]
        goc.sort(key=lambda n: -len(nx.descendants(self.S, n)))

        return {
            "ten_do_thi": self.G.graph.get("ten_do_thi", "(không tên)"),
            "du_an": self.G.graph.get("ma_du_an"),
            "so_node": self.G.number_of_nodes(),
            "so_canh": self.G.number_of_edges(),
            "theo_loai": {
                k: {"so_luong": v, "nhan": NHAN_NODE.get(k, k)}
                for k, v in sorted(theo_loai.items(), key=lambda kv: -kv[1])
            },
            "so_nguon_goc": len(goc),
            "cac_nguon_goc": [
                {**self._tom_tat(n),
                 "so_thiet_bi_phia_sau": len(nx.descendants(self.S, n))}
                for n in goc[:10]
            ],
            "la_dag": nx.is_directed_acyclic_graph(self.S),
        }

    # --- noi bo ------------------------------------------------------------

    def _mat_dien_khi_bo(self, x: str) -> set:
        """Tap node ha nguon cua x se mat dien hoan toan khi x hong.

        Bo x ra, roi loang tu cac nguon goc con lai. Node ha nguon nao khong
        con loang toi duoc la mat dien.

        Tap goc phai tinh TREN DO THI GOC. Neu tinh lai sau khi bo x, cac node
        vua mat thuong nguon se bi coi la goc moi va luon con "nguon".
        """
        goc = [n for n in self.S if self.S.in_degree(n) == 0 and n != x]
        H = self.S.copy()
        H.remove_node(x)
        con_nguon = set(goc)
        for g in goc:
            con_nguon |= nx.descendants(H, g)
        return nx.descendants(self.S, x) - con_nguon

    def _tom_tat(self, n: str) -> dict:
        d = self.G.nodes.get(n, {})
        t = {
            "id": n,
            "ten": d.get("ten", n),
            "loai": d.get("loai"),
            "nhan_loai": NHAN_NODE.get(d.get("loai"), d.get("loai")),
        }
        for k in ("ma_thiet_bi", "cong_trinh", "tang", "truc",
                  "dien_ap_V", "dong_dien_dinh_muc_A", "cong_suat_kVA",
                  "diem_rui_ro", "rul_nam", "so_thiet_bi_ha_nguon",
                  "so_hieu_ban_ve", "ma_tuyen"):
            if d.get(k) not in (None, ""):
                t[k] = d[k]
        return t

    def _ten(self, n: str) -> str:
        return str(self.G.nodes.get(n, {}).get("ten", n))

    def _khong_thay(self, node_id: str) -> dict:
        goi_y = self.tim(node_id, 5)["ket_qua"] if len(node_id) >= 2 else []
        return {
            "loi": f"Không tìm thấy thiết bị có id '{node_id}'",
            "goi_y": goi_y,
            "huong_dan": "Dùng tool 'tim' để tra id theo tên thiết bị.",
        }


def _nap_cong_viec() -> list[dict]:
    p = THU_MUC_DATA / "cong_viec_baotri.csv"
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
