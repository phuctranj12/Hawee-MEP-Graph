# -*- coding: utf-8 -*-
"""Xuat do thi MEP sang thu muc Markdown cho Obsidian de xem Graph View dep, gon.

Cach dung:
    python xuat_obsidian.py [duong_dan_hmepg] [thu_muc_obsidian] [--all]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import networkx as nx

from hawee_mep import io_graphml, model


def _tao_ten_file_hop_le(ten: str, node_id: str, danh_sach_ten: set[str]) -> str:
    """Loai bo ky tu cam va dam bao ten file duy nhat, ngan gon."""
    ten_sach = re.sub(r'[\\/*?:"<>|]', "_", str(ten).strip())
    if not ten_sach:
        ten_sach = f"ThietBi_{node_id}"

    # Neu trung ten thiet bi, moi them suffix id de phan biet
    ten_cuoi = ten_sach
    if ten_cuoi in danh_sach_ten:
        ten_cuoi = f"{ten_sach} ({node_id})"
    danh_sach_ten.add(ten_cuoi)
    return ten_cuoi


def xuat_sang_obsidian(
    duong_dan_hmepg: str,
    thu_muc_dich: str = "obsidian_vault",
    bao_gom_phu_tai: bool = False,
    thu_gon_mach: bool = True,
) -> int:
    path_dich = Path(thu_muc_dich)
    
    # Xoa cac file md cu de lam sach vault
    if path_dich.exists():
        for f in path_dich.glob("*.md"):
            try:
                f.unlink()
            except OSError:
                pass
    path_dich.mkdir(parents=True, exist_ok=True)

    print(f"[*] Dang doc do thi tu: {duong_dan_hmepg}...")
    G = io_graphml.doc(duong_dan_hmepg)

    # Thu gon node mach: Nguon -> Mach -> Dich => Nguon -> Dich
    if thu_gon_mach:
        G_view = G.copy()
        mach_nodes = [n for n, d in G_view.nodes(data=True) if d.get("loai") == "mach"]
        for m in mach_nodes:
            in_nodes = list(G_view.predecessors(m))
            out_nodes = list(G_view.successors(m))
            m_ten = G_view.nodes[m].get("ten", "Mạch")
            for u in in_nodes:
                for v in out_nodes:
                    G_view.add_edge(u, v, so_mach=m_ten, loai="supplies")
            G_view.remove_node(m)
    else:
        G_view = G

    # Tao ten file ngan gon cho tung node
    node_to_name: dict[str, str] = {}
    danh_sach_ten: set[str] = set()
    for n, d in G_view.nodes(data=True):
        ten = d.get("ten", str(n))
        ten_file = _tao_ten_file_hop_le(ten, str(n), danh_sach_ten)
        node_to_name[n] = ten_file

    so_luong_xuat = 0

    for n, d in G_view.nodes(data=True):
        loai = d.get("loai", "")
        if not bao_gom_phu_tai and loai in ["phu_tai", "mach"]:
            continue

        so_luong_xuat += 1
        ten_hien_thi = d.get("ten", str(n))
        nhan_loai = model.NHAN_NODE.get(loai, loai)
        file_name = node_to_name[n]
        file_path = path_dich / f"{file_name}.md"

        # YAML Frontmatter
        lines = ["---"]
        lines.append(f"id: \"{n}\"")
        lines.append(f"ten: \"{ten_hien_thi}\"")
        lines.append(f"loai: \"{loai}\"")
        lines.append(f"nhan: \"{nhan_loai}\"")
        if "cong_suat_kVA" in d and d["cong_suat_kVA"] is not None:
            lines.append(f"cong_suat_kVA: {d['cong_suat_kVA']}")
        if "tang" in d and d["tang"]:
            lines.append(f"tang: \"{d['tang']}\"")
        if "cong_trinh" in d and d["cong_trinh"]:
            lines.append(f"cong_trinh: \"{d['cong_trinh']}\"")
        lines.append("tags:")
        lines.append(f"  - mep/{loai}")
        lines.append("---\n")

        # Noi dung chi tiet
        lines.append(f"# {ten_hien_thi}\n")
        lines.append(f"- **Phân loại**: {nhan_loai} (`#mep/{loai}`)")
        if d.get("tang"):
            lines.append(f"- **Vị trí**: {d.get('tang')} ({d.get('cong_trinh', '')})")
        if d.get("so_hieu_ban_ve"):
            lines.append(f"- **Bản vẽ Revit**: `{d.get('so_hieu_ban_ve')}`")
        if d.get("cong_suat_kVA"):
            lines.append(f"- **Công suất**: {d.get('cong_suat_kVA')} kVA")
        if d.get("dong_dien_dinh_muc_A"):
            lines.append(f"- **Dòng định mức**: {d.get('dong_dien_dinh_muc_A')} A")

        # Quan he Thuong nguon (Lay dien tu)
        thuong_nguon = [u for u, _ in G_view.in_edges(n)]
        lines.append("\n## ⚡ Nguồn cấp vào (Thượng nguồn)")
        ds_tn = []
        for u in thuong_nguon:
            u_loai = G_view.nodes[u].get("loai", "")
            if not bao_gom_phu_tai and u_loai in ["phu_tai", "mach"]:
                continue
            e_data = G_view.get_edge_data(u, n, default={})
            mach_info = f" *(qua {e_data.get('so_mach')})*" if e_data.get("so_mach") else ""
            ds_tn.append(f"- [[{node_to_name[u]}]] {mach_info}")

        if ds_tn:
            lines.extend(ds_tn)
        else:
            lines.append("*Là nguồn gốc (hoặc chưa nối mạch trong Revit)*")

        # Quan he Ha nguon (Cap dien cho)
        ha_nguon = [v for _, v in G_view.out_edges(n)]
        lines.append("\n## 🔌 Cấp điện cho (Hạ nguồn)")
        ds_hn = []
        for v in ha_nguon:
            v_loai = G_view.nodes[v].get("loai", "")
            if not bao_gom_phu_tai and v_loai in ["phu_tai", "mach"]:
                continue
            e_data = G_view.get_edge_data(n, v, default={})
            mach_info = f" *(qua {e_data.get('so_mach')})*" if e_data.get("so_mach") else ""
            ds_hn.append(f"- [[{node_to_name[v]}]] {mach_info}")

        if ds_hn:
            lines.extend(ds_hn)
        else:
            lines.append("*Không cấp nguồn cho thiết bị nào khác*")

        file_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[+] Da xuat thanh cong {so_luong_xuat} file markdown vao: {path_dich.resolve()}")
    print("[+] Ten file gio day ngan gon: SWITCHBOARD, MAIN1, P102, P205...")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Xuat do thi MEP sang Obsidian Markdown")
    parser.add_argument("hmepg", nargs="?", default="examples/mau_tu_revit.hmepg", help="Duong dan file .hmepg")
    parser.add_argument("vault", nargs="?", default="obsidian_vault", help="Thu muc xuat Markdown Vault")
    parser.add_argument("--all", action="store_true", help="Bao gom ca phu tai cuoi")
    parser.add_argument("--keep-circuits", action="store_true", help="Giu nguyen node mach, khong thu gon")

    args = parser.parse_args()
    sys.exit(xuat_sang_obsidian(
        args.hmepg,
        args.vault,
        bao_gom_phu_tai=args.all,
        thu_gon_mach=not args.keep_circuits
    ))
