// Xuat he dien tu model Revit dang mo ra file .graphml, qua Revit MCP.
//
// Ban C# cua revit_xuat_graphml.py, cung dinh dang dau ra. Dung khi Claude
// goi tool send_code_to_revit (tool nay chi chay C#):
//     code        = noi dung file nay
//     parameters  = ["<duong dan .graphml dau ra>"]
//     transaction = "none" (chi doc, khong sua model)
// Sau do chay: python extract/chuyen_doi_revit.py <.graphml> <.hmepg>
//
// Revit 2024+ (ElementId.Value, UnitTypeId).

string duongDan = parameters != null && parameters.Length > 0 && !string.IsNullOrEmpty((string)parameters[0])
    ? (string)parameters[0]
    : System.IO.Path.ChangeExtension(document.PathName, ".graphml");

var thamSo = new Dictionary<string, ForgeTypeId> {
    {"Panel Name", null}, {"Mark", null}, {"Sheet Number", null},
    {"Voltage", UnitTypeId.Volts}, {"Rating", UnitTypeId.Amperes}, {"Mains", UnitTypeId.Amperes},
    {"Number of Phases", null}, {"Apparent Load", UnitTypeId.VoltAmperes},
    {"Total Connected", UnitTypeId.VoltAmperes}, {"Short Circuit Rating", UnitTypeId.Amperes},
    {"Manufacturer", null}, {"Model", null}, {"Length", UnitTypeId.Meters}, {"Comments", null},
    {"Busbar run number", null}, {"Busbar run description", null}, {"Busbar run ID", null},
    {"Engineered length", null},
    {"Max. permissible operational current Inc (horizontal edgewise) (A)", null}, {"Phase", null},
};
var tuKhoaBusway = new[] { "busway", "busduct", "thanh dan", "thanh dẫn", "flexible link", "flex link", "noi mem", "nối mềm" };

Func<Parameter, ForgeTypeId, string> giaTri = (p, dv) => {
    if (p == null || !p.HasValue) return null;
    switch (p.StorageType) {
        case StorageType.Double:
            if (dv == null) return p.AsValueString();
            try { return Math.Round(UnitUtils.ConvertFromInternalUnits(p.AsDouble(), dv), 3).ToString(System.Globalization.CultureInfo.InvariantCulture); }
            catch { return p.AsValueString(); }
        case StorageType.Integer: return p.AsInteger().ToString();
        case StorageType.String: return p.AsString();
        default: return p.AsValueString();
    }
};
Func<Element, string> tenThietBi = e => {
    foreach (var t in new[] { "Panel Name", "Mark" }) {
        var p = e.LookupParameter(t);
        if (p != null && p.HasValue && !string.IsNullOrEmpty(p.AsString())) return p.AsString();
    }
    var fi = e as FamilyInstance;
    return fi != null ? fi.Symbol.Family.Name + ": " + e.Name : e.Name;
};
Func<Element, Dictionary<string, string>> thuocTinh = e => {
    var d = new Dictionary<string, string>();
    foreach (var kv in thamSo) { var v = giaTri(e.LookupParameter(kv.Key), kv.Value); if (!string.IsNullOrEmpty(v)) d[kv.Key] = v; }
    var lv = document.GetElement(e.LevelId) as Level;
    if (lv != null) d["Level"] = lv.Name;
    var bb = e.get_BoundingBox(null);
    if (bb != null) {
        var c = (bb.Min + bb.Max) / 2 * 0.3048;
        var ic = System.Globalization.CultureInfo.InvariantCulture;
        d["x"] = Math.Round(c.X, 3).ToString(ic); d["y"] = Math.Round(c.Y, 3).ToString(ic); d["z"] = Math.Round(c.Z, 3).ToString(ic);
    }
    return d;
};

var nodes = new Dictionary<string, Dictionary<string, string>>();
var edges = new List<Tuple<string, string>>();

var danhMuc = new[] { BuiltInCategory.OST_ElectricalEquipment, BuiltInCategory.OST_ElectricalFixtures,
    BuiltInCategory.OST_LightingFixtures, BuiltInCategory.OST_LightingDevices, BuiltInCategory.OST_DataDevices,
    BuiltInCategory.OST_CableTrayFitting };
foreach (var bic in danhMuc) {
    foreach (var e in new FilteredElementCollector(document).OfCategory(bic).WhereElementIsNotElementType()) {
        var ten = tenThietBi(e);
        if (bic == BuiltInCategory.OST_CableTrayFitting) {
            var p = e.LookupParameter("Busbar run number");
            bool coTuyen = p != null && p.HasValue && !string.IsNullOrEmpty(p.AsString());
            if (!coTuyen && !tuKhoaBusway.Any(k => ten.ToLower().Contains(k))) continue;
        }
        var d = thuocTinh(e);
        d["category"] = e.Category != null ? e.Category.Name : "";
        d["name"] = ten;
        var fi = e as FamilyInstance;
        if (fi != null) {
            // Ten co the lay tu Mark ("10"), nen giu ten family de nhan dien
            d["family"] = fi.Symbol.Family.Name + ": " + fi.Name;
            var pt = fi.Symbol.Family.get_Parameter(BuiltInParameter.FAMILY_CONTENT_PART_TYPE);
            if (pt != null && pt.HasValue) d["part_type"] = pt.AsValueString();
        }
        nodes[e.Id.Value.ToString()] = d;
    }
}

// Mach: tu (BaseEquipment) -> mach -> cac phan tu tren mach
foreach (Autodesk.Revit.DB.Electrical.ElectricalSystem es in new FilteredElementCollector(document)
        .OfClass(typeof(Autodesk.Revit.DB.Electrical.ElectricalSystem))) {
    var mid = es.Id.Value.ToString();
    var d = thuocTinh(es);
    d["category"] = "Electrical Circuit";
    d["name"] = string.IsNullOrEmpty(es.CircuitNumber) ? mid : es.CircuitNumber;
    var tu = es.BaseEquipment;
    if (tu != null) {
        d["supply_from_id"] = tu.Id.Value.ToString();
        d["supply_from_name"] = tenThietBi(tu);
        edges.Add(Tuple.Create(d["supply_from_id"], mid));
    }
    nodes[mid] = d;
    foreach (Element pt in es.Elements) {
        var pid = pt.Id.Value.ToString();
        if (d.ContainsKey("supply_from_id") && pid == d["supply_from_id"]) continue;
        if (!nodes.ContainsKey(pid))
            nodes[pid] = new Dictionary<string, string> { { "category", pt.Category != null ? pt.Category.Name : "" }, { "name", tenThietBi(pt) } };
        if (!nodes[pid].ContainsKey("supply_from_id")) nodes[pid]["supply_from_id"] = mid;
        edges.Add(Tuple.Create(mid, pid));
    }
}

// Ghi GraphML
Func<string, string> esc = s => System.Security.SecurityElement.Escape(s ?? "");
var khoa = nodes.Values.SelectMany(x => x.Keys).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToList();
var ma = khoa.Select((k, i) => new { k, i }).ToDictionary(x => x.k, x => "d" + x.i);
var sb = new System.Text.StringBuilder();
sb.AppendLine("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
sb.AppendLine("<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\">");
foreach (var k in khoa) sb.AppendLine("  <key id=\"" + ma[k] + "\" for=\"node\" attr.name=\"" + esc(k) + "\" attr.type=\"string\"/>");
sb.AppendLine("  <graph id=\"" + esc(document.Title) + "\" edgedefault=\"directed\">");
foreach (var n in nodes) {
    sb.AppendLine("    <node id=\"" + esc(n.Key) + "\">");
    foreach (var kv in n.Value) sb.AppendLine("      <data key=\"" + ma[kv.Key] + "\">" + esc(kv.Value) + "</data>");
    sb.AppendLine("    </node>");
}
foreach (var e in edges) sb.AppendLine("    <edge source=\"" + esc(e.Item1) + "\" target=\"" + esc(e.Item2) + "\"/>");
sb.AppendLine("  </graph>");
sb.AppendLine("</graphml>");
System.IO.File.WriteAllText(duongDan, sb.ToString(), new System.Text.UTF8Encoding(false));

return "Da xuat " + nodes.Count + " node, " + edges.Count + " canh -> " + duongDan;
