# -*- coding: utf-8 -*-
"""Trich xuat he dien tu model Revit dang mo ra file .graphml.

Thay the buoc Dynamo thu cong. Script nay chay BEN TRONG Revit, doc truc tiep
quan he cap nguon qua Revit API, roi (tuy chon) goi luon
extract/chuyen_doi_revit.py de ra file .hmepg.

Chay duoc o ba moi truong, khong can sua code:

    1. Dynamo: tao node Python Script, dan toan bo file nay vao.
         IN[0] = duong dan file .graphml dau ra (de trong: canh file .rvt)
         IN[1] = True de goi luon bo chuyen doi ra .hmepg
       Luu .dyn lai roi chay bang Dynamo Player: mot click, khong mo do thi.
    2. pyRevit: dat file vao mot pushbutton (script.py) -> mot nut tren ribbon.
    3. RevitPythonShell / Revit MCP (send_code_to_revit).

Viet tuong thich ca IronPython 2.7 va CPython 3 (khong dung f-string).

Cau truc do thi xuat ra giong file MACAD ma bo chuyen doi da duoc kiem chung:

    tu dien --supplies--> mach (Electrical Circuit) --supplies--> thiet bi

Moi node mang: category, part_type, name, supply_from_id va cac tham so
Revit nam trong ANH_XA_THUOC_TINH cua chuyen_doi_revit.py.

Busway ve bang Cable Tray Fittings thuong khong co circuit. Script xuat tung
doan kem tham so tuyen (Busbar run number / description) va toa do; viec gop
doan thanh tuyen va dung canh "From X To Y" nam o chuyen_doi_revit.py
(gop_busway_va_tu), de logic do chay va kiem thu duoc ngoai Revit.

Ban C# tuong duong cho Revit MCP (send_code_to_revit): revit_mcp_xuat.cs.
"""
from __future__ import print_function

import io
import os
import subprocess
from xml.sax.saxutils import escape, quoteattr

import clr

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (  # noqa: E402
    BuiltInCategory,
    BuiltInParameter,
    ElementId,
    FilteredElementCollector,
    StorageType,
    UnitUtils,
)
from Autodesk.Revit.DB.Electrical import ElectricalSystem  # noqa: E402

# --- lay document theo moi truong -----------------------------------------


def _lay_document():
    # pyRevit / RevitPythonShell
    try:
        return __revit__.ActiveUIDocument.Document  # noqa: F821
    except NameError:
        pass
    # Dynamo
    clr.AddReference("RevitServices")
    from RevitServices.Persistence import DocumentManager
    return DocumentManager.Instance.CurrentDBDocument


doc = _lay_document()

# --- cau hinh --------------------------------------------------------------

DANH_MUC = [
    BuiltInCategory.OST_ElectricalEquipment,
    BuiltInCategory.OST_ElectricalFixtures,
    BuiltInCategory.OST_LightingFixtures,
    BuiltInCategory.OST_LightingDevices,
    BuiltInCategory.OST_DataDevices,
    BuiltInCategory.OST_CableTrayFitting,
]

# Busway thuong ve bang Cable Tray Fittings. Category nay con chua bulong, co,
# te cua mang cap, lay het se ra hang tram node roi. Chi lay phan tu co tham
# so tuyen busway (Siemens LI: "Busbar run number") hoac ten giong busway.
THAM_SO_TUYEN = "Busbar run number"
CHI_LAY_THEO_TEN = {
    BuiltInCategory.OST_CableTrayFitting:
        ("busway", "busduct", "thanh dan", u"thanh dẫn",
         "flexible link", "flex link", "noi mem", u"nối mềm"),
}

# Tham so lay theo TEN hien thi, dung voi khoa trong ANH_XA_THUOC_TINH.
# Gia tri: don vi dich khi doi tu don vi noi bo cua Revit (None = lay chuoi).
THAM_SO = {
    "Panel Name": None,
    "Mark": None,
    "Sheet Number": None,
    "Voltage": "V",
    "Rating": "A",
    "Mains": "A",
    "Number of Phases": None,
    "Apparent Load": "VA",
    "Total Connected": "VA",
    "Short Circuit Rating": "A",
    "Manufacturer": None,
    "Model": None,
    "Length": "m",
    "Comments": None,
    # Busway Siemens LI: quan he cap nguon nam o day khi model khong co circuit
    "Busbar run number": None,
    "Busbar run description": None,
    "Busbar run ID": None,
    "Engineered length": None,
    "Max. permissible operational current Inc (horizontal edgewise) (A)": None,
    "Phase": None,
}

# Ten don vi cho ca API moi (UnitTypeId, Revit 2021+) va cu (DisplayUnitType)
_DON_VI = {
    "V": ("Volts", "DUT_VOLTS"),
    "A": ("Amperes", "DUT_AMPERES"),
    "VA": ("VoltAmperes", "DUT_VOLT_AMPERES"),
    "m": ("Meters", "DUT_METERS"),
}


def _doi_don_vi(gia_tri, don_vi):
    moi, cu = _DON_VI[don_vi]
    try:
        from Autodesk.Revit.DB import UnitTypeId
        return UnitUtils.ConvertFromInternalUnits(
            gia_tri, getattr(UnitTypeId, moi))
    except (ImportError, AttributeError):
        from Autodesk.Revit.DB import DisplayUnitType
        return UnitUtils.ConvertFromInternalUnits(
            gia_tri, getattr(DisplayUnitType, cu))


def _gia_tri(p, don_vi):
    if p is None or not p.HasValue:
        return None
    st = p.StorageType
    if st == StorageType.Double:
        # Khong biet don vi thi lay chuoi hien thi: AsDouble tra don vi noi
        # bo (foot) se sai voi tham so chieu dai cua nha san xuat
        if not don_vi:
            return p.AsValueString()
        try:
            return round(_doi_don_vi(p.AsDouble(), don_vi), 3)
        except Exception:
            return p.AsValueString()
    if st == StorageType.Integer:
        return p.AsInteger()
    if st == StorageType.String:
        return p.AsString()
    return p.AsValueString()


def _id(e):
    # ElementId.IntegerValue bi bo o Revit 2024+, thay bang Value
    i = e.Id if not isinstance(e, ElementId) else e
    try:
        return str(i.Value)
    except AttributeError:
        return str(i.IntegerValue)


def _part_type(e):
    try:
        fam = e.Symbol.Family
        p = fam.get_Parameter(BuiltInParameter.FAMILY_CONTENT_PART_TYPE)
        return p.AsValueString() if p else None
    except Exception:
        return None


def _ten_thiet_bi(e):
    for ten in ("Panel Name", "Mark"):
        p = e.LookupParameter(ten)
        if p is not None and p.HasValue and p.AsString():
            return p.AsString()
    try:
        return "{0}: {1}".format(e.Symbol.Family.Name, e.Name)
    except Exception:
        return e.Name


def _ten_tang(e):
    try:
        lv = doc.GetElement(e.LevelId)
        return lv.Name if lv is not None else None
    except Exception:
        return None


def _thuoc_tinh(e):
    d = {}
    for ten, don_vi in THAM_SO.items():
        v = _gia_tri(e.LookupParameter(ten), don_vi)
        if v not in (None, ""):
            d[ten] = v
    tang = _ten_tang(e)
    if tang:
        d["Level"] = tang
    # Toa do tam (m), de gan noi mem vao tuyen busway gan nhat
    try:
        bb = e.get_BoundingBox(None)
        if bb is not None:
            for truc in ("X", "Y", "Z"):
                tam = (getattr(bb.Min, truc) + getattr(bb.Max, truc)) / 2
                d[truc.lower()] = round(tam * 0.3048, 3)
    except Exception:
        pass
    return d


# --- thu thap --------------------------------------------------------------


def thu_thap():
    """Tra ve (nodes, edges). nodes: {id: dict}, edges: [(nguon, dich)]."""
    nodes = {}
    edges = []

    for bic in DANH_MUC:
        for e in (FilteredElementCollector(doc).OfCategory(bic)
                  .WhereElementIsNotElementType()):
            ten = _ten_thiet_bi(e)
            tu_khoa = CHI_LAY_THEO_TEN.get(bic)
            if tu_khoa:
                p = e.LookupParameter(THAM_SO_TUYEN)
                co_tuyen = p is not None and p.HasValue and p.AsString()
                if not co_tuyen and not any(k in ten.lower() for k in tu_khoa):
                    continue
            d = _thuoc_tinh(e)
            d["category"] = e.Category.Name if e.Category else ""
            d["name"] = ten
            # Ten co the lay tu Mark ("10"), nen giu ten family de nhan dien
            try:
                d["family"] = u"{0}: {1}".format(e.Symbol.Family.Name, e.Name)
            except Exception:
                pass
            pt = _part_type(e)
            if pt:
                d["part_type"] = pt
            nodes[_id(e)] = d

    # Mach: tu (BaseEquipment) -> mach -> cac phan tu tren mach
    for es in (FilteredElementCollector(doc).OfClass(ElectricalSystem)
               .WhereElementIsNotElementType()):
        mid = _id(es)
        d = _thuoc_tinh(es)
        d["category"] = "Electrical Circuit"
        # Chi de so mach tran ("2", "1,3,5"): neu ghep ten tu vao, vi du
        # "MDB.F11/2", bo chuyen doi se doan nham mach thanh tu phan phoi.
        d["name"] = es.CircuitNumber or mid
        try:
            tu = es.BaseEquipment
        except Exception:
            tu = None
        if tu is not None:
            d["supply_from_id"] = _id(tu)
            d["supply_from_name"] = _ten_thiet_bi(tu)
            edges.append((_id(tu), mid))
        nodes[mid] = d

        for ptu in es.Elements:
            pid = _id(ptu)
            if pid == d.get("supply_from_id"):
                continue
            if pid not in nodes:
                nodes[pid] = {
                    "category": ptu.Category.Name if ptu.Category else "",
                    "name": _ten_thiet_bi(ptu),
                }
            nodes[pid].setdefault("supply_from_id", mid)
            edges.append((mid, pid))

    return nodes, edges


# --- ghi GraphML -----------------------------------------------------------


def ghi_graphml(nodes, edges, duong_dan, ten_do_thi):
    khoa = sorted({k for d in nodes.values() for k in d})
    ma = dict((k, "d{0}".format(i)) for i, k in enumerate(khoa))

    dong = [
        u'<?xml version="1.0" encoding="UTF-8"?>',
        u'<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
    ]
    for k in khoa:
        dong.append(u'  <key id="{0}" for="node" attr.name={1} '
                    u'attr.type="string"/>'.format(ma[k], quoteattr(k)))
    dong.append(u'  <graph id={0} edgedefault="directed">'
                .format(quoteattr(ten_do_thi)))
    for nid, d in nodes.items():
        dong.append(u'    <node id={0}>'.format(quoteattr(nid)))
        for k, v in d.items():
            dong.append(u'      <data key="{0}">{1}</data>'
                        .format(ma[k], escape(u"{0}".format(v))))
        dong.append(u'    </node>')
    for u, v in edges:
        dong.append(u'    <edge source={0} target={1}/>'
                    .format(quoteattr(u), quoteattr(v)))
    dong += [u'  </graph>', u'</graphml>']

    with io.open(duong_dan, "w", encoding="utf-8") as f:
        f.write(u"\n".join(dong))


def goi_chuyen_doi(graphml, python="python"):
    """Goi extract/chuyen_doi_revit.py (can Python 3 + networkx ngoai Revit)."""
    try:
        thu_muc = os.path.dirname(os.path.abspath(__file__))
    except NameError:  # Dynamo khong co __file__
        thu_muc = os.environ.get("HAWEE_EXTRACT_DIR",
                                 r"D:\Git\Hawee-MEP-Graph\extract")
    hmepg = os.path.splitext(graphml)[0] + ".hmepg"
    lenh = [python, os.path.join(thu_muc, "chuyen_doi_revit.py"),
            graphml, hmepg]
    ma = subprocess.call(lenh)
    return hmepg if ma == 0 else None


# --- chay ------------------------------------------------------------------


def chay(duong_dan=None, chuyen_luon=False):
    ten = doc.Title.replace(".rvt", "")
    if not duong_dan:
        goc = os.path.dirname(doc.PathName) if doc.PathName else \
            os.path.expanduser("~")
        duong_dan = os.path.join(goc, ten + ".graphml")

    nodes, edges = thu_thap()
    ghi_graphml(nodes, edges, duong_dan, ten)
    kq = u"Da xuat {0} node, {1} canh -> {2}".format(
        len(nodes), len(edges), duong_dan)

    if chuyen_luon:
        hmepg = goi_chuyen_doi(duong_dan)
        kq += u"\n" + (u"Da chuyen doi -> {0}".format(hmepg) if hmepg else
                       u"Chuyen doi that bai, chay tay chuyen_doi_revit.py")
    return kq


if "IN" in globals():
    # Dynamo: IN[0] = duong dan, IN[1] = chuyen luon sang .hmepg
    OUT = chay(IN[0] if len(IN) > 0 else None,  # noqa: F821
               bool(IN[1]) if len(IN) > 1 else False)  # noqa: F821
else:
    print(chay(chuyen_luon=True))
