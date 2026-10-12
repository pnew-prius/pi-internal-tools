"""In-memory stand-in for GeoServer + GWC REST, covering exactly the calls add_cog / the app make.
It mirrors the behaviors learned on the real server: group bounds are NOT recomputed, tile layers are auto-created for
new layers (strays), and coverage creation fails for unknown/unreadable files."""
import json
import re


class FakeGS:
    def __init__(self, cogs, workspaces=("COPE-S26",), prod_workspaces=()):
        self.cogs = cogs                     # file stem -> (epsg code str, {minx,miny,maxx,maxy})
        self.workspaces = set(workspaces)
        self.prod_workspaces = set(prod_workspaces)
        self.stores, self.coverages, self.groups, self.gwc, self.seeds, self.log = {}, {}, {}, {}, [], []
        self.stores[("COPE-S26", "codes26-01")] = {"name": "codes26-01", "connectionParameters": {"entry": []}, "metadata": {"entry": {}}}
        self.auto_stray = True

    def call(self, env, method, path, body=None, ctype=None, accept=None, timeout=0, allow_prod=False):
        self.log.append((env, method, path))
        path = path.split("?")[0]
        if env == "prod":
            if method == "GET" and path == "/rest/workspaces.json":
                return 200, {"workspaces": {"workspace": [{"name": w} for w in sorted(self.prod_workspaces)]}}
            return 404, "n/a"
        m = re.fullmatch
        if path == "/rest/workspaces.json" and method == "GET":
            return 200, {"workspaces": {"workspace": [{"name": w} for w in sorted(self.workspaces)]} if self.workspaces else ""}
        if path == "/rest/workspaces" and method == "POST":
            self.workspaces.add(body["workspace"]["name"]); return 201, ""
        g = m(r"/rest/workspaces/([^/]+)\.json", path)
        if g and method == "GET":
            return (200, {"workspace": {"name": g.group(1)}}) if g.group(1) in self.workspaces else (404, "no")
        g = m(r"/rest/workspaces/([^/]+)/coveragestores/([^/]+)\.json", path)
        if g and method == "GET":
            s = self.stores.get((g.group(1), g.group(2)))
            return (200, {"coverageStore": s}) if s else (404, "no")
        g = m(r"/rest/workspaces/([^/]+)/coveragestores", path)
        if g and method == "POST":
            s = body["coverageStore"]; self.stores[(g.group(1), s["name"])] = s; return 201, s["name"]
        g = m(r"/rest/workspaces/([^/]+)/coveragestores/([^/]+)", path)
        if g and method == "DELETE":
            self.stores.pop((g.group(1), g.group(2)), None); self.coverages.pop((g.group(1), g.group(2)), None); return 200, ""
        g = m(r"/rest/workspaces/([^/]+)/coveragestores/([^/]+)/coverages", path)
        if g and method == "POST":
            ws, tile = g.group(1), g.group(2)
            stem = self.stores[(ws, tile)]["url"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if stem not in self.cogs:
                return 500, "Error getting coverages from coverage reader."
            epsg, bb = self.cogs[stem]
            self.coverages[(ws, tile)] = {"name": tile, "srs": f"EPSG:{epsg}", "nativeBoundingBox": dict(bb)}
            if self.auto_stray:
                self.gwc[f"{ws}:{tile}"] = "auto"
            return 201, tile
        g = m(r"/rest/workspaces/([^/]+)/coveragestores/([^/]+)/coverages/([^/]+)\.json", path)
        if g and method == "GET":
            c = self.coverages.get((g.group(1), g.group(3)))
            return (200, {"coverage": c}) if c else (404, "no")
        g = m(r"/rest/workspaces/([^/]+)/layergroups\.json", path)
        if g and method == "GET":
            names = [k[1] for k in self.groups if k[0] == g.group(1)]
            return 200, {"layerGroups": {"layerGroup": [{"name": n} for n in names]} if names else ""}
        g = m(r"/rest/workspaces/([^/]+)/layergroups/([^/]+)\.json", path)
        if g and method == "GET":
            grp = self.groups.get((g.group(1), g.group(2)))
            return (200, {"layerGroup": json.loads(json.dumps(grp))}) if grp else (404, "no")
        g = m(r"/rest/workspaces/([^/]+)/layergroups", path)
        if g and method == "POST":
            grp = body["layerGroup"]; self.groups[(g.group(1), grp["name"])] = grp
            self.gwc[f"{g.group(1)}:{grp['name']}"] = "auto-group"; return 201, grp["name"]
        g = m(r"/rest/workspaces/([^/]+)/layergroups/([^/]+)", path)
        if g and method == "PUT":
            self.groups[(g.group(1), g.group(2))] = body["layerGroup"]; return 200, ""
        g = m(r"/gwc/rest/layers/(.+)\.xml", path)
        if g and method == "PUT":
            self.gwc[g.group(1)] = body; return 200, "layer saved"
        if path == "/gwc/rest/layers.json" and method == "GET":
            return 200, sorted(self.gwc)
        g = m(r"/gwc/rest/layers/(.+)\.json", path)
        if g and method == "DELETE":
            self.gwc.pop(g.group(1), None); return 200, "deleted"
        if g and method == "GET":
            return (200, {"GeoServerLayer": {"name": g.group(1)}}) if g.group(1) in self.gwc else (500, "Unknown layer")
        g = m(r"/gwc/rest/seed/(.+)\.json", path)
        if g and method == "POST":
            self.seeds.append((body["seedRequest"]["type"], body["seedRequest"]["zoomStart"], body["seedRequest"]["zoomStop"],
                               [float(v) for v in body["seedRequest"]["bounds"]["coords"]["double"]])); return 200, ""
        if g and method == "GET":
            return 200, {"long-array-array": []}
        return 404, f"fake: unhandled {method} {path}"


# two COGs in UTM 13N (EPSG:32613), side by side and overlapping slightly, plus one in zone 14
COGS = {
    "t-01-RGB": ("32613", {"minx": 600000.0, "miny": 3600000.0, "maxx": 605000.0, "maxy": 3604000.0}),
    "t-02-RGB": ("32613", {"minx": 604900.0, "miny": 3600000.0, "maxx": 610000.0, "maxy": 3604000.0}),
    "t-03-RGB": ("32614", {"minx": 300000.0, "miny": 3600000.0, "maxx": 305000.0, "maxy": 3604000.0}),
}
