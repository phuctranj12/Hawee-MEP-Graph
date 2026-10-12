# -*- coding: utf-8 -*-
"""Chay thu cac phep truy xuat tren dong lenh, khong can MCP.

    python demo.py examples/mau_tu_revit.hmepg
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hawee_mep import io_graphml, model, risk  # noqa: E402
from hawee_mep.query import DoThiCoDien  # noqa: E402


def muc(tieu_de: str) -> None:
    print("\n" + "=" * 68)
    print(tieu_de)
    print("=" * 68)


def main() -> int:
    duong_dan = sys.argv[1] if len(sys.argv) > 1 else "examples/mau_tu_revit.hmepg"
    G = io_graphml.doc(duong_dan)
    risk.gan_vao_do_thi(G)
    q = DoThiCoDien(G)

    muc("1. Đồ thị này có gì?")
    tq = q.tong_quan()
    print(f'   {tq["so_node"]} thiết bị, {tq["so_canh"]} quan hệ, '
          f'{tq["so_nguon_goc"]} nguồn gốc')
    for k, v in tq["theo_loai"].items():
        print(f'   {v["so_luong"]:5d}  {v["nhan"]}')

    muc("2. Chất lượng model Revit")
    kt = model.kiem_tra_do_thi(G)
    print(f'   {"Hợp lệ" if kt["hop_le"] else str(len(kt["loi"])) + " lỗi"}, '
          f'{len(kt["canh_bao"])} cảnh báo')
    for c in kt["canh_bao"][:4]:
        print(f'   [{c["ma"]}] {c["thong_diep"]}')

    muc("3. Thiết bị nào rủi ro cao nhất, cần bảo trì trước?")
    for i, x in enumerate(q.xep_hang_rui_ro(6)["xep_hang"], 1):
        print(f'   {i}. {x["ten"][:22]:22} {x["nhan_loai"][:22]:22} '
              f'rủi ro {x.get("diem_rui_ro"):.3f}  '
              f'({x.get("so_thiet_bi_ha_nguon", 0)} thiết bị phía sau)')

    ten_thu = sys.argv[2] if len(sys.argv) > 2 else None
    if not ten_thu:
        ds = q.xep_hang_rui_ro(40, "tu_phan_phoi")["xep_hang"]
        ten_thu = ds[len(ds) // 2]["ten"] if ds else None
    if not ten_thu:
        return 0

    tim = q.tim(ten_thu)
    if not tim["ket_qua"]:
        print(f"\nKhông tìm thấy '{ten_thu}'")
        return 1
    nid = tim["ket_qua"][0]["id"]

    muc(f"4. Tủ '{ten_thu}' lấy điện từ đâu?")
    u = q.truy_vet_thuong_nguon(nid)
    print(f'   Số đường cấp nguồn: {u["so_duong_cap_nguon"]} '
          f'({"CÓ dự phòng" if u["co_du_phong"] else "KHÔNG có dự phòng"})')
    for d in u["cac_duong"][:2]:
        print("   " + "  ->  ".join(x["ten"][:16] for x in d))

    muc(f"5. Thiết bị nào hỏng thì '{ten_thu}' mất điện hoàn toàn?")
    dd = q.diem_hong_don(nid)
    print(f'   {dd["giai_thich"]}')
    for x in dd["diem_hong_don"]:
        print(f'   - {x["ten"][:22]:22} {x["nhan_loai"][:24]:24} '
              f'rủi ro {x.get("diem_rui_ro", 0):.3f}')

    muc(f"6. Nếu '{ten_thu}' hỏng thì ảnh hưởng gì?")
    a = q.anh_huong_mat_dien(nid)
    print(f'   {a["tom_tat"]}')
    print(f'   Nguồn số liệu công suất: {a["nguon_so_lieu_cong_suat"]}')

    muc(f"7. Phải bảo trì '{ten_thu}' thế nào?")
    cv = q.cong_viec_bao_tri(nid)
    print(f'   Loại: {cv["nhan_loai"]} | {cv["so_cong_viec"]} công việc | '
          f'{cv["tong_gio_cong_mot_chu_ky"]} giờ công | '
          f'{cv["tong_chi_phi_vnd_mot_chu_ky"]:,.0f} VND')
    for c in cv["cong_viec"]:
        print(f'   [{c["ma_cv"]}] mỗi {c["chu_ky_thang"]:>2} tháng - '
              f'{c["mo_ta"][:48]}')
    if cv["chung_chi_can_co"]:
        print(f'   Chứng chỉ cần có: {", ".join(cv["chung_chi_can_co"])}')

    muc("8. Câu Cypher tương đương (dùng cho giai đoạn B)")
    print(a["cypher"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
