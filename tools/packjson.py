"""Shared helpers: read and write map packs as readable JSON (one place per line)."""
import json


def dump_pack(pack, path):
    """Write a pack with normal indentation, but each place on a single line."""
    def enc(o, ind=0):
        sp = "  " * ind
        if isinstance(o, dict):
            if not o:
                return "{}"
            if ind >= 3 or all(not isinstance(v, (dict, list)) for v in o.values()) and len(json.dumps(o)) < 100:
                return json.dumps(o, ensure_ascii=False)
            inner = ",\n".join(f'{sp}  {json.dumps(k)}: {items(v, ind + 1) if k == "items" else enc(v, ind + 1)}' for k, v in o.items())
            return "{\n" + inner + "\n" + sp + "}"
        if isinstance(o, list):
            if all(not isinstance(v, (dict, list)) for v in o) or ind >= 3:
                return json.dumps(o, ensure_ascii=False)
            inner = ",\n".join(f"{sp}  {json.dumps(v, ensure_ascii=False)}" for v in o)
            return "[\n" + inner + "\n" + sp + "]"
        return json.dumps(o, ensure_ascii=False)
    def items(lst, ind):
        sp = "  " * ind
        if not lst:
            return "[]"
        return "[\n" + ",\n".join(sp + "  " + json.dumps(v, ensure_ascii=False, separators=(", ", ": ")) for v in lst) + "\n" + sp + "]"

    with open(path, "w", encoding="utf-8") as f:
        f.write(enc(pack) + "\n")


def load_pack(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
