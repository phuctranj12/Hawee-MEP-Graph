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


# --- hai nguon cap song song (nhu MSB3 Hon Thom) ----------------------------

def do_thi_hai_mba() -> nx.DiGraph:
    """TR1 -> T1 -> MSB <- T2 <- TR2,  MSB -> P11 -> MDB -> phu tai."""
    G = nx.DiGraph()
    for n, loai in [("TR1", "may_bien_ap"), ("TR2", "may_bien_ap"),
                    ("T1", "busway"), ("T2", "busway"), ("MSB", "tu_tong"),
                    ("P11", "busway"), ("MDB", "tu_phan_phoi")]:
        G.add_node(n, loai=loai, ten=n)
    G.add_node("PT", loai="phu_tai", ten="PT", cong_suat_kVA=40)
    for u, v in [("TR1", "T1"), ("T1", "MSB"), ("TR2", "T2"), ("T2", "MSB"),
                 ("MSB", "P11"), ("P11", "MDB"), ("MDB", "PT")]:
        G.add_edge(u, v, loai="supplies")
    return G


def test_hai_nguon_goc_khong_phai_diem_hong_don():
    q = DoThiCoDien(risk.gan_vao_do_thi(do_thi_hai_mba()))
    ids = {x["id"] for x in q.diem_hong_don("MDB")["diem_hong_don"]}
    assert ids == {"MSB", "P11"}


def test_anh_huong_mat_dien_tinh_den_du_phong():
    q = DoThiCoDien(risk.gan_vao_do_thi(do_thi_hai_mba()))
    kq = q.anh_huong_mat_dien("T1")
    assert kq["so_thiet_bi_mat_dien"] == 0
    assert kq["tong_cong_suat_kVA"] == 0
    assert kq["so_node_con_dien_nho_du_phong"] > 0
    assert q.anh_huong_mat_dien("MSB")["so_phu_tai_mat_dien"] == 1


# --- gop tuyen busway tu tham so Siemens LI ----------------------------------

def test_gop_busway_tu_tham_so_tuyen():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extract"))
    from chuyen_doi_revit import chuyen_doi

    R = nx.DiGraph()
    # Tu MSB3 ve bang hai family instance; MDB ten khac kieu viet trong mo ta
    R.add_node("1", category="Electrical Equipment", name="MSB3",
               x=0, y=0, z=0)
    R.add_node("2", category="Electrical Equipment", name="MSB3",
               x=1, y=0, z=0)
    R.add_node("3", category="Electrical Equipment", name="MDB.F12",
               Level="F12.TẦNG HẦM", x=50, y=0, z=0)
    for i, (so, mo_ta, x) in enumerate([
            ("T1", "From TR-01-F To MSB3", -5), ("T1", "From TR-01-F To MSB3", -8),
            ("P12", "From MSB3 To MDB-F12", 20), ("P12", "From MSB3 To MDB-F12", 40)]):
        R.add_node("f%d" % i, category="Cable Tray Fittings", name="LI -L-HB",
                   **{"Busbar run number": so, "Busbar run description": mo_ta,
                      "Engineered length": "3000",
                      model_inc(): "2000" if so == "T1" else "1250"},
                   x=x, y=0, z=0)
    # Noi mem: ten lay tu Mark, chi family moi cho biet la noi mem
    R.add_node("nm", category="Electrical Fixtures", name="10",
               family="TKT_Flexible link 3D: LI-A.2000A L1", x=-9, y=0, z=0)

    G = chuyen_doi(R)
    ten = {n: d["ten"] for n, d in G.nodes(data=True)}
    canh = {(ten[u], ten[v]) for u, v in G.edges()}
    assert canh == {
        ("TR-01-F", "Nối mềm T1"), ("Nối mềm T1", "Busway T1"),
        ("Busway T1", "MSB3"), ("MSB3", "Busway P12"),
        ("Busway P12", "MDB.F12"),
    }
    bw = G.nodes["busway:P12"]
    assert bw["loai"] == "busway"
    assert bw["dong_dien_dinh_muc_A"] == 1250
    assert bw["chieu_dai_m"] == 6.0
    assert G.nodes["suy_dien:TR-01-F"]["loai"] == "may_bien_ap"
    assert G.nodes["1"]["so_phan_tu_gop"] == 2
    assert model.kiem_tra_do_thi(G)["hop_le"]


def model_inc() -> str:
    from chuyen_doi_revit import THAM_SO_INC
    return THAM_SO_INC
