# -*- coding: utf-8 -*-
"""Script CLI nap do thi MEP vao Neo4j (Neo4j Desktop hoac Aura / Docker).

Cach dung:
    python nap_neo4j.py --uri bolt://localhost:7687 --user neo4j --password <mat_khau>
    python nap_neo4j.py --uri bolt://localhost:7687 -u neo4j -p 12345678 --xoa-cu
"""
from __future__ import annotations

import argparse
import sys

from hawee_mep import io_graphml, store_neo4j


def main() -> int:
    parser = argparse.ArgumentParser(description="Nap do thi MEP vao Neo4j")
    parser.add_argument("hmepg", nargs="?", default="examples/mau_tu_revit.hmepg", help="Duong dan file .hmepg")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Bolt URI cua Neo4j (mac dinh: bolt://localhost:7687)")
    parser.add_argument("-u", "--user", default="neo4j", help="Ten dang nhap (mac dinh: neo4j)")
    parser.add_argument("-p", "--password", required=True, help="Mat khau Neo4j")
    parser.add_argument("--db", default="neo4j", help="Ten Database (mac dinh: neo4j)")
    parser.add_argument("--xoa-cu", action="store_true", help="Xoa toan bo node ThietBi cu truoc khi nap")

    args = parser.parse_args()

    print(f"[*] Dang doc file do thi: {args.hmepg}...")
    G = io_graphml.doc(args.hmepg)
    print(f"[*] Tong so node: {G.number_of_nodes()}, so quan he: {G.number_of_edges()}")

    print(f"[*] Dang ket noi toi Neo4j tai {args.uri} (database: {args.db})...")
    try:
        kq = store_neo4j.nap(
            G=G,
            uri=args.uri,
            nguoi_dung=args.user,
            mat_khau=args.password,
            co_so_du_lieu=args.db,
            xoa_cu=args.xoa_cu,
        )
        print("\n" + "=" * 50)
        print("  NẠP VÀO NEO4J THÀNH CÔNG!")
        print(f"  - Số node đã nạp: {kq['so_node']}")
        print(f"  - Số quan hệ đã nạp: {kq['so_canh']}")
        print("=" * 50)
        print("\n[*] Bạn có thể mở Neo4j Desktop / Browser và chạy truy vấn:")
        print("    MATCH (n:ThietBi) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100")
        return 0
    except Exception as e:
        print(f"\n[!] Loi khi nap vao Neo4j: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
