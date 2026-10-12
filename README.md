# Hawee-MEP-Graph

Đồ thị tri thức cho hệ cơ điện, để Claude truy vấn được bằng tiếng Việt.

Biến model Revit thành đồ thị có hướng, rồi cho phép truy vấn theo **cấu trúc**
thay vì theo từ khoá: *"tủ MDB.F11 lấy điện từ đâu"*, *"busway P12 hỏng thì mất
điện ở đâu"*, *"thiết bị nào rủi ro cao nhất cần bảo trì trước"*.

## Khác gì so với RAG thông thường

RAG thường chia tài liệu thành đoạn, nhúng thành vector, rồi tìm đoạn gần nghĩa
nhất. Cách đó không trả lời được câu hỏi về *quan hệ*: không có đoạn văn nào
chứa sẵn câu trả lời cho "tủ này mất điện thì ảnh hưởng những đâu".

Hệ phân phối điện là đồ thị có hướng, quan hệ cấp nguồn rõ ràng. Nên ở đây việc
truy xuất là **duyệt đồ thị**, cho kết quả chính xác chứ không phải gần đúng.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Yêu cầu Python 3.10 trở lên.

## Dùng nhanh

**1. Chuyển model Revit thành đồ thị**

```bash
python extract/chuyen_doi_revit.py duong_dan\xuat_tu_revit.graphml examples\cong_trinh.hmepg
```

**2. Thử truy vấn ngay trên dòng lệnh**

```bash
python demo.py examples/mau_tu_revit.hmepg
```

**3. Nối vào Claude**

Thêm vào cấu hình MCP:

```json
{
  "mcpServers": {
    "hawee-mep": {
      "command": "python",
      "args": ["D:\\Git\\Hawee-MEP-Graph\\mcp_server\\server.py"],
      "env": {
        "HAWEE_GRAPH": "D:\\Git\\Hawee-MEP-Graph\\examples\\mau_tu_revit.hmepg"
      }
    }
  }
}
```

## 10 tool Claude gọi được

| Tool | Trả lời câu hỏi |
|---|---|
| `tong_quan` | Đồ thị này có gì, công trình nào, bao nhiêu thiết bị |
| `tim_thiet_bi` | Tra id từ tên, ví dụ "MDB.F11" |
| `truy_vet_thuong_nguon` | Thiết bị này lấy điện từ đâu, có dự phòng không |
| `truy_vet_ha_nguon` | Thiết bị này cấp điện cho những gì |
| `anh_huong_mat_dien` | Hỏng thì mất điện ở đâu, bao nhiêu kVA |
| `diem_hong_don` | Thiết bị nào hỏng là mất điện hoàn toàn |
| `xep_hang_rui_ro` | Thiết bị nào cần bảo trì trước |
| `cong_viec_bao_tri` | Phải làm gì, chu kỳ bao lâu, cần chứng chỉ gì |
| `kiem_tra_chat_luong_model` | Model Revit có chỗ nào chưa nối mạch |
| `huong_dan_nap_neo4j` | Script Cypher để sang giai đoạn B |

Mọi tool đều trả về kèm **câu Cypher tương đương**, để kiểm chứng lại được và
để chuyển sang Neo4j mà không phải viết lại.

## Cấu trúc

```
schema/hawee_mep_v1.md      Đặc tả đồ thị. Đọc file này trước
hawee_mep/
  model.py                  Loại node, loại cạnh, kiểm tra tính đúng đắn
  io_graphml.py             Đọc/ghi .hmepg
  risk.py                   Công suất lan truyền và điểm rủi ro
  rul.py                    Tuổi thọ còn lại
  query.py                  Lớp truy xuất (phần "retrieval")
  cypher.py                 Sinh Cypher tương đương
  store_neo4j.py            Nạp vào Neo4j (giai đoạn B)
extract/chuyen_doi_revit.py Chuyển graph Revit sang schema Hawee
data/                       Bảng định mức. ⚠️ Số liệu còn là giá trị tạm
mcp_server/server.py        MCP server
tests/                      22 test
```

## Hai giai đoạn

| | Giai đoạn A (hiện tại) | Giai đoạn B |
|---|---|---|
| Backend | NetworkX, đọc file | Neo4j |
| Cài đặt | Chỉ cần Python | Thêm Neo4j Desktop/Docker |
| Quy mô | Đến khoảng vài chục nghìn node | Hàng triệu node |
| Claude sinh Cypher tự do | Không | Có |
| Tên tool | **Giữ nguyên ở cả hai giai đoạn** | |

Vì tên và tham số tool không đổi, chuyển giai đoạn chỉ là đổi lớp backend.

## Điểm khác biệt về kiến trúc: busway là node

Trong hầu hết schema MEP, dây dẫn chỉ là cạnh nối hai tủ. Nhưng với Hawee,
tuyến busway là sản phẩm chính: có tuổi thọ riêng, chi phí riêng, lịch bảo trì
riêng, và hỏng busway là mất điện cả tuyến. Cạnh không mang được những thứ đó.

```
tu_tong  --supplies-->  busway  --supplies-->  tu_phan_phoi
```

Nhờ vậy, câu hỏi "MDB.F11 mất điện vì đâu" chỉ ra **đúng đoạn busway**, không
chỉ ra tủ thượng nguồn.

## Điều kiện để dùng được

Đồ thị chỉ sinh được cạnh khi thiết bị trong Revit được **nối mạch logic**
(có circuit, có quan hệ cấp nguồn), không phải chỉ vẽ cạnh nhau. Chạy
`kiem_tra_chat_luong_model` để biết model còn thiếu chỗ nào.

## Việc còn phải làm

- [ ] Thay số liệu tạm trong `data/` bằng định mức thật của Hawee
- [ ] Trích xuất trực tiếp từ Revit qua Revit MCP, bỏ bước Dynamo
- [ ] Lớp truy xuất chạy trên Neo4j (giai đoạn B)
- [ ] Nối với hệ NS: gán người có chứng chỉ phù hợp cho từng công việc
- [ ] Mô phỏng bảo trì theo ngân sách giờ công và chi phí
- [ ] Mở rộng sang HVAC và cấp thoát nước

## Giấy phép

MIT, xem `LICENSE`. Phần ghi công và cơ sở pháp lý xem `NOTICE`.
