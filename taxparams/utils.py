from collections import defaultdict
import os
import inspect
import json

import taxcalc
import paramtools

TCPATH = inspect.getfile(taxcalc.Policy)
TCDIR = os.path.dirname(TCPATH)
with open(os.path.join(TCDIR, "policy_current_law.json")) as f:
    DEFAULTS = json.loads(f.read())


POLICY_SCHEMA = {
    "labels": {
        "year": {
            "type": "int",
            "validators": {
                "range": {"min": 2013, "max": 2030}
            }
        },
        "MARS": {
            "type": "str",
            "validators": {"choice": {"choices": ["single", "mjoint",
                                                  "mseparate", "headhh",
                                                  "widow"]}}
        },
        "idedtype": {
            "type": "str",
            "validators": {"choice": {"choices": ["med", "sltx", "retx", "cas",
                                                  "misc", "int", "char"]}}
        },
        "EIC": {
            "type": "str",
            "validators": {"choice": {"choices": ["0kids", "1kid",
                                                  "2kids", "3+kids"]}}
        },
    },
    "additional_members": {
        "section_1": {"type": "str"},
        "section_2": {"type": "str"},
        "start_year": {"type": "int"},
        "indexable": {"type": "bool"},
        "indexed": {"type": "bool"},
        "compatible_data": {"type": "compatible_data"}
    }
}

def convert_defaults():
    pcl = DEFAULTS
    type_map = {
        "real": "float",
        "boolean": "bool",
        "integer": "int",
        "string": "str",
    }

    new_pcl = defaultdict(dict)
    new_pcl["schema"] = POLICY_SCHEMA
    for param, item in pcl.items():
        values = []
        pol_val = item["value"]
        min_year = min(item["value_yrs"])
        if isinstance(pol_val[0], list):
            for year in range(len(pol_val)):
                for dim1 in range(len(pol_val[0])):
                    values.append({
                        "year": min_year + year,
                        item["vi_name"]: item["vi_vals"][dim1],
                        "value": pol_val[year][dim1],
                    })
        else:
            for year in range(len(pol_val)):
                values.append({
                    "year": min_year + year,
                    "value": pol_val[year],
                })

        new_pcl[param]['value'] = values
        new_pcl[param]['title'] = pcl[param]["long_name"]
        new_pcl[param]['type'] = type_map[pcl[param]["value_type"]]

        if pcl[param].get("invalid_action") == "warn":
            pcl[param]["valid_values"]["level"] = "warn"
        new_pcl[param]["validators"] = {"range": pcl[param]["valid_values"]}

        to_keep = list(POLICY_SCHEMA["additional_members"].keys()) + [
            "description", "notes", "compatible_data"
        ]
        for k in to_keep:
            if k in pcl[param]:
                new_pcl[param][k] = pcl[param][k]

    return new_pcl
