# Bảng định mức

⚠️ **Các con số trong hai file CSV ở đây là GIÁ TRỊ TẠM, do Claude đặt để hệ
thống chạy được. Hawee phải thay bằng số thật trước khi dùng cho quyết định
thật.**

## loai_thiet_bi.csv

Một dòng cho mỗi loại node trong schema.

| Cột | Ý nghĩa |
|---|---|
| `loai` | Mã loại, phải khớp `hawee_mep/model.py` |
| `ten_hien_thi` | Nhãn tiếng Việt |
| `tuoi_tho_nam` | Tuổi thọ thiết kế |
| `suy_giam_nam` | Tỉ lệ suy giảm thêm mỗi năm khi vận hành quá tải hoặc có sự cố |
| `do_quan_trong` | 1 đến 5, nhân vào điểm rủi ro |
| `chi_phi_thay_the_vnd` | Busway, thang máng, tuyến cáp tính theo **mét**; còn lại tính theo **cái** |
| `he_so_sua_chua` | Chi phí sửa / chi phí thay, 0 đến 1 |
| `chu_ky_bao_tri_thang` | Chu kỳ bảo trì mặc định |

## cong_viec_baotri.csv

Mẫu công việc bảo trì. Mỗi node trong đồ thị sẽ được sinh ra các công việc
tương ứng với `loai` của nó.

| Cột | Ý nghĩa |
|---|---|
| `ma_cv` | Mã công việc |
| `loai_thiet_bi` | Áp dụng cho loại node nào |
| `loai_cong_viec` | `kiem_tra`, `do_kiem`, `ve_sinh`, `siet_lai`, `thay_the` |
| `chu_ky_thang` | Chu kỳ lặp |
| `mo_ta` | Nội dung công việc |
| `uu_tien` | 1 (cao nhất) đến 3 |
| `gio_cong` | Giờ công cho một lần thực hiện |
| `chi_phi_vnd` | Chi phí vật tư, dụng cụ cho một lần |
| `chung_chi_yeu_cau` | Chứng chỉ người thực hiện phải có. Dùng để đối chiếu với hệ NS |

Cột `chung_chi_yeu_cau` là bổ sung riêng của Hawee, không có trong bản gốc.
Nó cho phép ghép lịch bảo trì với dữ liệu nhân sự và chứng chỉ trong hệ NS.
