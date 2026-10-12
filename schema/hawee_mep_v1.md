# Schema Hawee-MEP-Graph v1

Đặc tả đồ thị hệ cơ điện của Hawee. Định dạng lưu: **GraphML** (XML chuẩn),
đuôi file `.hmepg`.

## Nguyên tắc thiết kế

**1. Mã định danh dùng ASCII, nhãn hiển thị dùng tiếng Việt.**
Kiểu node ghi là `busway`, không ghi `thanh_dẫn`. Lý do: tránh lỗi mã hóa khi
đi qua Neo4j, Cypher, JSON và Revit API. Nhãn tiếng Việt nằm trong
`hawee_mep/model.py` để hiển thị cho người dùng.

**2. Thanh dẫn (busway) là NODE, không phải cạnh.**
Đây là khác biệt lớn nhất so với các schema MEP thông thường. Trong hầu hết
cách làm, dây dẫn chỉ là cạnh nối giữa hai tủ. Nhưng với Hawee, tuyến busway
là *sản phẩm chính*: nó có tuổi thọ riêng, chi phí riêng, lịch bảo trì riêng,
và hỏng busway thì mất điện toàn tuyến.

Cạnh không mang được các thuộc tính đó một cách tự nhiên. Vì vậy:

```
tu_tong  --supplies-->  busway  --supplies-->  tu_phan_phoi
```

thay cho:

```
tu_tong  --(busway)-->  tu_phan_phoi
```

Hệ quả: truy vết "tủ MDB.F11 mất điện vì đâu" sẽ chỉ ra **đúng đoạn busway**,
không chỉ ra tủ thượng nguồn.

**3. Mọi node đều truy được về bản vẽ.**
Thuộc tính `so_hieu_ban_ve` nối node với sheet trong model Revit. Người bảo
trì cầm kết quả truy vấn là biết mở bản vẽ nào.

**4. Đơn vị Việt Nam.** Điện áp 220/380V, tần số 50Hz, chi phí VND, thời gian
theo tháng.

## Các loại node

| Mã (`loai`) | Nhãn hiển thị | Ghi chú |
|---|---|---|
| `nguon_luoi` | Nguồn lưới / Trạm biến áp EVN | Gốc của đồ thị, ngoài phạm vi Hawee |
| `may_bien_ap` | Máy biến áp | |
| `may_phat` | Máy phát điện dự phòng | Nguồn thứ hai, tạo đồ thị nhiều gốc |
| `tu_tong` | Tủ điện tổng (MSB) | Tương đương Switchboard |
| `tu_phan_phoi` | Tủ phân phối (MDB/DB) | Tương đương Panelboard |
| `busway` | Tuyến thanh dẫn (busway/busduct) | **Node, không phải cạnh** |
| `noi_mem` | Nối mềm (flexible link) | Đoạn bù giãn nở, rung |
| `thang_mang_cap` | Thang / máng cáp | Tuyến đỡ cáp |
| `tuyen_cap` | Tuyến cáp | Khi cáp cần theo dõi riêng |
| `mach` | Mạch (circuit) | Revit sinh ra; gom nhiều phụ tải |
| `phu_tai` | Phụ tải cuối | Đèn, ổ cắm, động cơ... |
| `ats` | Bộ chuyển nguồn tự động (ATS) | Điểm hợp của 2 nguồn |

## Thuộc tính node

### Định danh (bắt buộc)
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `id` | string | Khóa chính. Từ Revit thì dùng ElementId |
| `loai` | string | Một trong các mã ở bảng trên |
| `ten` | string | Tên hiển thị, ví dụ `MDB.F11` |

### Định danh mở rộng
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `ma_thiet_bi` | string | Mã quản lý tài sản của Hawee |
| `nha_san_xuat` | string | |
| `model` | string | |
| `so_hieu_ban_ve` | string | Sheet number trong Revit |

### Vị trí
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `cong_trinh` | string | Toà/khối, ví dụ `F11` |
| `tang` | string | Tên tầng, ví dụ `TẦNG HẦM` |
| `truc` | string | Trục kỹ thuật (riser) |
| `x`, `y`, `z` | float | Toạ độ, đơn vị mét |

### Thông số điện
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `dien_ap_V` | float | 220, 380 |
| `dong_dien_dinh_muc_A` | float | Dòng định mức. Busway: 800, 1000, 1250, 2000 |
| `so_pha` | int | 1 hoặc 3 |
| `tan_so_Hz` | float | 50 |
| `cong_suat_kVA` | float | |
| `dong_ngan_mach_kA` | float | Icu / AIC |
| `loai_phu_tai` | string | `chieu_sang`, `o_cam`, `dieu_hoa`, `thang_may`, `bom`, `khac` |

### Riêng cho busway và tuyến cáp
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `chieu_dai_m` | float | Chiều dài tuyến |
| `ma_tuyen` | string | Mã tuyến, ví dụ `P12`, `T1` |
| `so_hieu_san_pham` | string | Mã hàng, ví dụ `LI-AM12505B` |

### Vòng đời và bảo trì
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `ngay_lap_dat` | date | `YYYY-MM-DD` |
| `tuoi_tho_nam` | float | Tuổi thọ thiết kế |
| `gio_van_hanh` | float | Giờ vận hành tích luỹ |
| `ngay_bao_tri_cuoi` | date | |
| `chu_ky_bao_tri_thang` | int | |
| `so_lan_su_co` | int | |
| `do_quan_trong` | int | 1 (thấp) đến 5 (cao) |

### Kinh tế
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `chi_phi_thay_the_vnd` | float | |
| `he_so_sua_chua` | float | Chi phí sửa / chi phí thay, 0 đến 1 |

### Trường do hệ thống tính (không nhập tay)
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `cong_suat_lan_truyen` | float | Tổng tải hạ nguồn dồn về node này |
| `diem_rui_ro` | float | 0 đến 1, xem `risk.py` |
| `rul_ngay`, `rul_nam` | float | Tuổi thọ còn lại |
| `so_thiet_bi_ha_nguon` | int | |

### Liên kết hệ thống Hawee
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `ma_du_an` | string | Khớp với dự án trong hệ NS |
| `ma_hop_dong` | string | Để tra nghĩa vụ bảo hành |

## Các loại cạnh

| Mã (`loai`) | Nhãn | Ý nghĩa |
|---|---|---|
| `supplies` | Cấp nguồn cho | Dòng công suất. Chiều: thượng nguồn → hạ nguồn |
| `routed_in` | Đi trong | Busway/cáp chạy trong thang máng nào |
| `controls` | Điều khiển | Tín hiệu điều khiển |
| `backup_for` | Dự phòng cho | Máy phát / ATS |

**Chỉ cạnh `supplies` được dùng để truy vết nguồn và tính rủi ro.** Các loại
cạnh khác là thông tin phụ trợ; nếu tính rủi ro trên chúng sẽ sai.

### Thuộc tính cạnh
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `loai` | string | Bắt buộc |
| `so_mach` | string | Số mạch (Circuit Number) |
| `thiet_bi_bao_ve` | string | MCCB/ACB bảo vệ đoạn này |
| `dong_bao_ve_A` | float | Dòng cắt của thiết bị bảo vệ |
| `sut_ap_V` | float | Sụt áp trên đoạn |

## Ràng buộc tính đúng đắn

Hàm `model.kiem_tra_do_thi()` kiểm tra:

1. **Không có chu trình** trên cạnh `supplies`. Hệ phân phối điện là DAG.
   Ngoại lệ hợp lệ duy nhất là mạch vòng qua ATS — khi đó ATS phải khai báo
   `loai = "ats"` và hệ thống bỏ qua chu trình tại đó.
2. **Mỗi node (trừ gốc) phải có ít nhất một cạnh `supplies` vào.** Node
   không có nguồn là dấu hiệu model Revit chưa nối mạch.
3. **`loai` phải thuộc danh sách hợp lệ.**
4. **Busway phải có cả thượng nguồn và hạ nguồn.** Busway treo lơ lửng là
   lỗi mô hình hoá.
5. **Cảnh báo** nếu `dong_dien_dinh_muc_A` của node hạ nguồn lớn hơn thượng
   nguồn — khả năng sai thông số hoặc thiếu thiết bị trung gian.

## Ghi chú rút ra từ dữ liệu Revit thật

Khảo sát `output_graph.graphml` của luận văn MACAD (1.853 node, 1.845 cạnh,
trích từ một model Revit thật):

- Đồ thị là **DAG, sâu 10 cấp**, có **8 gốc** (1 tủ tổng + 7 tủ PV).
- Chỉ **54 node là thiết bị thật** (44 Panelboard + 10 Switchboard). Còn lại
  là phụ tải và mạch: 562 đèn, 530 thiết bị điện, 448 mạch, 144 thiết bị
  chiếu sáng.
- Revit sinh node loại **Electrical Circuit** làm trung gian giữa tủ và phụ
  tải. Schema này giữ nguyên bằng loại `mach`.
- Thuộc tính `supply_from_name` trong dữ liệu gốc **không đáng tin**: nhiều
  tủ trả về số mạch (`"3"`, `"4"`) thay vì tên tủ thượng nguồn. Khi trích
  xuất, phải lấy quan hệ cấp nguồn từ `supply_from_id`, không từ tên.
- Model Revit xuất ra 275 thuộc tính khác nhau, phần lớn vô dụng cho vận
  hành. Bộ trích xuất phải **lọc theo danh sách trắng**, không lấy hết.

## Phiên bản

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| v1 | 2026-10-12 | Bản đầu. Chỉ hệ điện. HVAC và cấp thoát nước để sau |
