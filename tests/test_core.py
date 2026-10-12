# -*- coding: utf-8 -*-
"""Kiem thu lop core: schema, rui ro, RUL, truy xuat.

Chay: pytest -q
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hawee_mep import model, risk, rul  # noqa: E402
from hawee_mep.query import DoThiCoDien  # noqa: E402


def do_thi_mau() -> nx.DiGraph:
    """He don gian:  luoi -> MBA -> MSB -> busway -> MDB -> 2 phu tai."""
    G = nx.DiGraph()
    G.add_node("L1", loai="nguon_luoi", ten="Lưới EVN")
    G.add_node("T1", loai="may_bien_ap", ten="MBA 1250kVA",
               dong_dien_dinh_muc_A=2000, ngay_lap_dat="2015-01-01",
               tuoi_tho_nam=30)
    G.add_node("MSB", loai="tu_tong", ten="MSB.F11",
               dong_dien_dinh_muc_A=2000)
    G.add_node("BW1", loai="busway", ten="Busway T1 2000A",
               ma_tuyen="T1", dong_dien_dinh_muc_A=2000, chieu_dai_m=45)
    G.add_node("MDB", loai="tu_phan_phoi", ten="MDB.F11",
               dong_dien_dinh_muc_A=800)
    G.add_node("PT1", loai="phu_tai", ten="Chiếu sáng hầm",
               cong_suat_kVA=30)
    G.add_node("PT2", loai="phu_tai", ten="Bơm nước", cong_suat_kVA=20)
    for u, v in [("L1", "T1"), ("T1", "MSB"), ("MSB", "BW1"),
                 ("BW1", "MDB"), ("MDB", "PT1"), ("MDB", "PT2")]:
        G.add_edge(u, v, loai="supplies")
    return G


# --- schema ---------------------------------------------------------------

def test_do_thi_mau_hop_le():
    kq = model.kiem_tra_do_thi(do_thi_mau())
    assert kq["hop_le"], kq["loi"]
    assert kq["thong_ke"]["so_goc"] == 1


def test_bat_duoc_busway_ho():
    G = do_thi_mau()
    G.remove_edge("BW1", "MDB")
    kq = model.kiem_tra_do_thi(G)
    assert not kq["hop_le"]
    assert any(l["ma"] == "busway_ho" for l in kq["loi"])


def test_bat_duoc_loai_sai():
    G = do_thi_mau()
    G.nodes["MDB"]["loai"] = "tu_dien_gi_do"
    kq = model.kiem_tra_do_thi(G)
    assert any(l["ma"] == "loai_khong_hop_le" for l in kq["loi"])


def test_bat_duoc_dong_nghich():
    G = do_thi_mau()
    G.nodes["MDB"]["dong_dien_dinh_muc_A"] = 4000  # lon hon busway 2000A
    kq = model.kiem_tra_do_thi(G)
    assert any(c["ma"] == "dong_nghich" for c in kq["canh_bao"])


def test_canh_khac_loai_khong_vao_do_thi_cap_nguon():
    G = do_thi_mau()
    G.add_node("TMC", loai="thang_mang_cap", ten="Thang cáp hầm")
    G.add_edge("BW1", "TMC", loai="routed_in")
    S = model.do_thi_cap_nguon(G)
    assert not S.has_edge("BW1", "TMC")
    assert S.has_edge("BW1", "MDB")


# --- rui ro ---------------------------------------------------------------

def test_cong_suat_lan_truyen_don_dung():
    cs = risk.tinh_cong_suat_lan_truyen(do_thi_mau())
    assert cs["MDB"] == pytest.approx(50.0)
    assert cs["BW1"] == pytest.approx(50.0)
    assert cs["L1"] == pytest.approx(50.0)
    assert cs["PT1"] == pytest.approx(30.0)


def test_rui_ro_giam_dan_ve_phia_ha_nguon():
    rr = risk.tinh_diem_rui_ro(do_thi_mau())
    assert rr["MSB"] > rr["MDB"] > rr["PT1"]
    assert max(rr.values()) == pytest.approx(1.0)


def test_khong_dem_phu_tai_vao_so_ha_nguon():
    hn = risk.dem_thiet_bi_ha_nguon(do_thi_mau())
    # MDB chi co 2 phu tai cuoi -> khong tinh
    assert hn["MDB"] == 0
    # MSB co busway + MDB
    assert hn["MSB"] == 2


def test_gan_vao_do_thi():
    G = risk.gan_vao_do_thi(do_thi_mau())
    assert G.nodes["MSB"]["diem_rui_ro"] > 0
    assert G.nodes["MSB"]["so_thiet_bi_ha_nguon"] == 2


# --- RUL ------------------------------------------------------------------

def test_rul_tinh_dung_tuoi():
    dm = rul.nap_dinh_muc()
    kq = rul.tinh_rul_node(
        {"loai": "may_bien_ap", "ngay_lap_dat": "2015-01-01",
         "tuoi_tho_nam": 30},
        dm, ngay_tinh=date(2026, 1, 1),
    )
    assert kq["tuoi_nam"] == pytest.approx(11.0, abs=0.1)
    assert kq["rul_nam"] == pytest.approx(19.0, abs=0.2)
    assert kq["can_thay_the"] is False


def test_rul_thieu_ngay_lap_dat_thi_bao_ro():
    dm = rul.nap_dinh_muc()
    kq = rul.tinh_rul_node({"loai": "tu_tong"}, dm)
    assert kq["rul_nam"] is None
    assert "ngay_lap_dat" in kq["ghi_chu"]


def test_rul_su_co_lam_giam_tuoi_tho():
    dm = rul.nap_dinh_muc()
    chung = {"loai": "tu_tong", "ngay_lap_dat": "2015-01-01",
             "tuoi_tho_nam": 25}
    lanh = rul.tinh_rul_node(chung, dm, date(2026, 1, 1))
    hong = rul.tinh_rul_node({**chung, "so_lan_su_co": 5}, dm, date(2026, 1, 1))
    assert hong["rul_nam"] < lanh["rul_nam"]


def test_rul_khong_am():
    dm = rul.nap_dinh_muc()
    kq = rul.tinh_rul_node(
        {"loai": "phu_tai", "ngay_lap_dat": "1980-01-01", "tuoi_tho_nam": 10},
        dm, date(2026, 1, 1),
    )
    assert kq["rul_nam"] == 0.0
    assert kq["can_thay_the"] is True


def test_nap_dinh_muc_doc_duoc_moi_loai():
    dm = rul.nap_dinh_muc()
    for loai in ("busway", "tu_tong", "may_bien_ap", "noi_mem"):
        assert loai in dm, f"thiếu định mức cho {loai}"
        assert dm[loai]["tuoi_tho_nam"] > 0


# --- truy xuat ------------------------------------------------------------

def test_tim_khong_phan_biet_chu_hoa():
    q = DoThiCoDien(do_thi_mau())
    assert q.tim("mdb.f11")["so_tim_thay"] == 1
    assert q.tim("BUSWAY")["so_tim_thay"] == 1


def test_truy_vet_thuong_nguon_dung_thu_tu():
    q = DoThiCoDien(risk.gan_vao_do_thi(do_thi_mau()))
    kq = q.truy_vet_thuong_nguon("MDB")
    assert kq["so_duong_cap_nguon"] == 1
    assert kq["co_du_phong"] is False
    ids = [x["id"] for x in kq["cac_duong"][0]]
    assert ids == ["L1", "T1", "MSB", "BW1", "MDB"]


def test_diem_hong_don_tim_dung_busway():
    q = DoThiCoDien(risk.gan_vao_do_thi(do_thi_mau()))
    ids = {x["id"] for x in q.diem_hong_don("MDB")["diem_hong_don"]}
    assert "BW1" in ids, "busway phải là điểm hỏng đơn của MDB"
    assert "MSB" in ids and "T1" in ids


def test_co_du_phong_thi_khong_con_diem_hong_don():
    G = risk.gan_vao_do_thi(do_thi_mau())
    # Them may phat cap truc tiep cho MDB
    G.add_node("MP", loai="may_phat", ten="Máy phát 500kVA")
    G.add_edge("MP", "MDB", loai="supplies")
    q = DoThiCoDien(G)
    kq = q.diem_hong_don("MDB")
    ids = {x["id"] for x in kq["diem_hong_don"]}
    assert "BW1" not in ids
    assert q.truy_vet_thuong_nguon("MDB")["co_du_phong"] is True


def test_anh_huong_mat_dien_dem_dung_tai():
    q = DoThiCoDien(risk.gan_vao_do_thi(do_thi_mau()))
    kq = q.anh_huong_mat_dien("BW1")
    assert kq["so_phu_tai_mat_dien"] == 2
    assert kq["tong_cong_suat_kVA"] == pytest.approx(50.0)
    assert "phụ tải cuối" in kq["nguon_so_lieu_cong_suat"]


def test_cong_viec_bao_tri_busway_co_siet_lai():
    q = DoThiCoDien(do_thi_mau())
    kq = q.cong_viec_bao_tri("BW1")
    assert kq["loai"] == "busway"
    assert kq["so_cong_viec"] > 0
    assert any(c["loai_cong_viec"] == "siet_lai" for c in kq["cong_viec"])
    assert kq["tong_gio_cong_mot_chu_ky"] > 0


def test_id_khong_ton_tai_tra_goi_y():
    q = DoThiCoDien(do_thi_mau())
    kq = q.truy_vet_thuong_nguon("KHONG_CO")
    assert "loi" in kq
    assert "huong_dan" in kq


def test_tong_quan_dem_dung():
    q = DoThiCoDien(do_thi_mau())
    tq = q.tong_quan()
    assert tq["so_node"] == 7
    assert tq["so_nguon_goc"] == 1
    assert tq["la_dag"] is True
    assert tq["theo_loai"]["phu_tai"]["so_luong"] == 2
