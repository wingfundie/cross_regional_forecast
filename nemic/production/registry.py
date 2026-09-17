"""Immutable package manifests and independently versioned routing policies."""
from pathlib import Path
import shutil

from .contracts import TARGETS, connector, digest, read_json, safe_path, write_json


def validate_package(folder):
    folder = Path(folder)
    manifest = read_json(folder / "manifest.json")
    required = {"id", "version", "connectors", "target", "lead_min", "lead_max",
                "resolution_minutes", "adapter", "recipe", "features", "status",
                "artifacts", "training_cutoff", "evaluation", "dependencies"}
    if required - manifest.keys():
        raise ValueError(f"Incomplete manifest: {sorted(required - manifest.keys())}")
    if manifest["target"] not in TARGETS or manifest["resolution_minutes"] != 30:
        raise ValueError("Unsupported target/resolution")
    if not 1 <= manifest["lead_min"] <= manifest["lead_max"] <= 1440:
        raise ValueError("Invalid lead range (half-hours, maximum 30 days)")
    if manifest["status"] not in {"research", "shadow", "approved", "retired"}:
        raise ValueError("Invalid eligibility status")
    if "model.joblib" not in manifest["artifacts"]:
        raise ValueError("Model artifact must have an integrity hash")
    if not manifest["connectors"] or not manifest["features"]:
        raise ValueError("Empty connector or feature contract")
    if len(set(manifest["features"])) != len(manifest["features"]):
        raise ValueError("Duplicate feature columns")
    for name in manifest["connectors"]:
        connector(name)
    for filename, expected in manifest["artifacts"].items():
        if digest(safe_path(folder, filename)) != expected:
            raise ValueError(f"Hash mismatch: {filename}")
    return manifest


class Registry:
    def __init__(self, root):
        self.root = Path(root)
        self.index = read_json(self.root / "index.json") if (self.root / "index.json").exists() else {"schema_version": 1, "models": {}}

    def register(self, package):
        manifest = validate_package(package)
        key = f"{manifest['id']}@{manifest['version']}"
        if key in self.index["models"]:
            raise ValueError(f"Immutable model already registered: {key}")
        # Paths never depend on user-supplied model identifiers.
        import hashlib
        relative = "packages/" + hashlib.sha256(key.encode()).hexdigest()[:24]
        destination = safe_path(self.root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package, destination)
        self.index["models"][key] = relative
        write_json(self.root / "index.json", self.index)
        return key

    def load(self, key):
        path = safe_path(self.root, self.index["models"][key])
        return validate_package(path), path

    def export(self, key, destination):
        _, path = self.load(key)
        shutil.copytree(path, destination)

    def catalogue(self):
        return [{"key": key, **self.load(key)[0]} for key in self.index["models"]]

    def validate_routes(self, policy):
        if not policy.get("version"):
            raise ValueError("Routing policy requires a version")
        occupied = set()
        for route in policy["routes"]:
            name = connector(route["connector"])
            if route["target"] not in TARGETS or not 1 <= route["lead_min"] <= route["lead_max"] <= 1440:
                raise ValueError("Invalid routing target or horizon")
            if not route["models"]:
                raise ValueError("Route needs primary model")
            for lead in range(route["lead_min"], route["lead_max"] + 1):
                cell = (name, route["target"], lead)
                if cell in occupied:
                    raise ValueError(f"Ambiguous route: {cell}")
                occupied.add(cell)
            for key in route["models"]:
                m, _ = self.load(key)
                if name not in [connector(c) for c in m["connectors"]] or m["target"] != route["target"]:
                    raise ValueError(f"Cross-connector/target route: {key}")
                if not m["lead_min"] <= route["lead_min"] <= route["lead_max"] <= m["lead_max"]:
                    raise ValueError(f"Unsupported route horizon: {key}")
        return policy

    def activate(self, policy):
        """Explicit policy promotion/rollback. Existing versions are immutable."""
        import hashlib
        self.validate_routes(policy)
        for route in policy["routes"]:
            for key in route["models"]:
                m, _ = self.load(key)
                if m["status"] != "approved" or not m.get("approval_evidence"):
                    raise ValueError(f"Production policy requires approval evidence: {key}")
        name = hashlib.sha256(str(policy["version"]).encode()).hexdigest() + ".json"
        path = self.root / "policies" / name
        if path.exists() and read_json(path) != policy:
            raise ValueError("Routing versions are immutable")
        write_json(path, policy)
        write_json(self.root / "active_policy.json", {"path": "policies/" + name, "version": policy["version"]})
        return path

    def candidates(self, policy, name, target, lead):
        matches = [r for r in policy["routes"] if connector(r["connector"]) == connector(name)
                   and r["target"] == target and r["lead_min"] <= lead <= r["lead_max"]]
        if len(matches) > 1:
            raise ValueError("Ambiguous route")
        return matches[0]["models"] if matches else []
