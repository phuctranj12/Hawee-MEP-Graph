# -*- coding: utf-8 -*-
"""MCP server cho do thi he co dien Hawee.

Day la phan de Claude truy xuat do thi. Giai doan A dung NetworkX doc file
.hmepg; giai doan B doi sang Neo4j nhung GIU NGUYEN ten va tham so cac tool,
nen phia Claude khong phai thay doi gi.

Chay:
    set HAWEE_GRAPH=D:\\Git\\Hawee-MEP-Graph\\examples\\mau_tu_revit.hmepg
    python mcp_server/server.py

Khai bao trong cau hinh MCP:
    {
      "mcpServers": {
        "hawee-mep": {
          "command": "python",
          "args": ["D:\\\\Git\\\\Hawee-MEP-Graph\\\\mcp_server\\\\server.py"],
          "env": {"HAWEE_GRAPH": "D:\\\\Git\\\\Hawee-MEP-Graph\\\\examples\\\\mau_tu_revit.hmepg"}
        }
      }
    }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC))

# SDK mcp 2.x doi ten FastMCP thanh MCPServer. Thu ban moi truoc, roi lui
# ve ban cu, de server chay duoc tren ca hai phien ban.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp >= 2
except ModuleNotFoundError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server  # mcp < 2

from hawee_mep import cypher, io_graphml, model, risk, rul  # noqa: E402
from hawee_mep.query import DoThiCoDien  # noqa: E402

mcp = _Server("hawee-mep")

_bo_nho: dict[str, object] = {}


def _duong_dan_graph() -> Path:
    p = os.environ.get("HAWEE_GRAPH")
    if p:
        return Path(p)
    mac_dinh = GOC / "examples" / "mau_tu_revit.hmepg"
    if mac_dinh.exists():
        return mac_dinh
    raise FileNotFoundError(
        "Chưa có đồ thị. Đặt biến môi trường HAWEE_GRAPH trỏ tới file .hmepg"
    )


def _do_thi() -> DoThiCoDien:
    """Nap do thi mot lan, nap lai neu file da doi."""
    p = _duong_dan_graph()
    dau_moc = (str(p), p.stat().st_mtime)
    if _bo_nho.get("dau_moc") != dau_moc:
        G = io_graphml.doc(p)
        # Tinh san diem rui ro neu do thi chua co
        if not any(
            d.get("diem_rui_ro") is not None for _, d in G.nodes(data=True)
        ):
            risk.gan_vao_do_thi(G)
        rul.gan_vao_do_thi(G)
        _bo_nho["do_thi"] = DoThiCoDien(G)
        _bo_nho["dau_moc"] = dau_moc
    return _bo_nho["do_thi"]  # type: ignore[return-value]


def _tra(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


# --- Tool -----------------------------------------------------------------

@mcp.tool()
def tong_quan() -> str:
    """Tổng quan đồ thị hệ cơ điện: số thiết bị theo loại, các nguồn gốc,
    độ sâu phân cấp. Gọi tool này trước khi hỏi chi tiết, để biết đồ thị
    đang chứa công trình nào và có những loại thiết bị gì."""
    return _tra(_do_thi().tong_quan())


@mcp.tool()
def tim_thiet_bi(tu_khoa: str, so_luong: int = 20) -> str:
    """Tìm thiết bị theo tên hoặc mã, không phân biệt chữ hoa.

    Dùng tool này TRƯỚC khi gọi các tool cần id, vì id là ElementId của
    Revit, người dùng không biết. Ví dụ tu_khoa='MDB.F11' hoặc 'busway P12'.
    """
    return _tra(_do_thi().tim(tu_khoa, so_luong))


@mcp.tool()
def truy_vet_thuong_nguon(id_thiet_bi: str) -> str:
    """Truy ngược đường cấp nguồn: thiết bị này lấy điện từ đâu.

    Trả về mọi đường từ nguồn gốc tới thiết bị (một tủ có thể có cả điện
    lưới và máy phát), cho biết có dự phòng hay không, và liệt kê các điểm
    hỏng đơn trên đường đi.
    """
    return _tra(_do_thi().truy_vet_thuong_nguon(id_thiet_bi))


@mcp.tool()
def truy_vet_ha_nguon(id_thiet_bi: str, chi_thiet_bi: bool = True) -> str:
    """Liệt kê thiết bị phía sau: thiết bị này cấp điện cho những gì.

    chi_thiet_bi=True (mặc định) bỏ qua mạch và phụ tải cuối, chỉ trả về
    tủ và tuyến. Đặt False khi cần đếm cả đèn, ổ cắm.
    """
    return _tra(_do_thi().truy_vet_ha_nguon(id_thiet_bi, chi_thiet_bi))


@mcp.tool()
def anh_huong_mat_dien(id_thiet_bi: str) -> str:
    """Thiết bị này hỏng thì mất điện ở đâu, bao nhiêu tải, thuộc khối và
    tầng nào. Dùng để đánh giá mức độ nghiêm trọng trước khi cắt điện bảo
    trì, hoặc khi đang có sự cố.

    Lưu ý đọc trường 'nguon_so_lieu_cong_suat' để biết con số kVA lấy từ
    đâu, vì nhiều model Revit chỉ ghi công suất ở tủ.
    """
    return _tra(_do_thi().anh_huong_mat_dien(id_thiet_bi))


@mcp.tool()
def diem_hong_don(id_thiet_bi: str) -> str:
    """Tìm điểm hỏng đơn (single point of failure): những thiết bị mà nếu
    hỏng sẽ làm thiết bị đích mất điện hoàn toàn. Nếu danh sách rỗng nghĩa
    là thiết bị đích có nguồn dự phòng."""
    return _tra(_do_thi().diem_hong_don(id_thiet_bi))


@mcp.tool()
def xep_hang_rui_ro(so_luong: int = 10, loai: str = "") -> str:
    """Xếp hạng thiết bị theo điểm rủi ro giảm dần.

    Điểm rủi ro kết hợp công suất tải qua thiết bị, số thiết bị phụ thuộc
    phía sau, và độ quan trọng do người vận hành đặt. Dùng để chọn thứ tự
    ưu tiên bảo trì khi ngân sách có hạn.

    loai: để trống xét mọi thiết bị, hoặc lọc theo một loại
    ('tu_tong', 'tu_phan_phoi', 'busway', 'may_bien_ap', ...).
    """
    return _tra(_do_thi().xep_hang_rui_ro(so_luong, loai or None))


@mcp.tool()
def cong_viec_bao_tri(id_thiet_bi: str = "", loai: str = "") -> str:
    """Tra công việc bảo trì theo mẫu cho một thiết bị hoặc một loại thiết bị.

    Trả về danh sách công việc kèm chu kỳ, giờ công, chi phí và chứng chỉ
    người thực hiện phải có. Truyền id_thiet_bi để tự suy ra loại, hoặc
    truyền loai trực tiếp.
    """
    return _tra(_do_thi().cong_viec_bao_tri(id_thiet_bi or None, loai or None))


@mcp.tool()
def kiem_tra_chat_luong_model() -> str:
    """Kiểm tra chất lượng đồ thị theo schema: chu trình cấp nguồn, thiết bị
    không có nguồn, busway hở đầu, dòng định mức nghịch.

    Cảnh báo 'khong_co_nguon' thường nghĩa là model Revit chưa nối mạch
    logic, không phải lỗi của đồ thị.
    """
    return _tra(model.kiem_tra_do_thi(_do_thi().G))


@mcp.tool()
def huong_dan_nap_neo4j() -> str:
    """Trả về script Cypher để nạp đồ thị vào Neo4j (dùng cho giai đoạn B)."""
    return cypher.nap_do_thi()


if __name__ == "__main__":
    mcp.run()
