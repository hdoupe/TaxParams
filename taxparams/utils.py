from collections import defaultdict
import os
import inspect

import taxcalc
import paramtools

TCPATH = inspect.getfile(taxcalc.Policy)
TCDIR = os.path.dirname(TCPATH)
DEFAULTS = os.path.join(TCDIR, "policy_current_law.json")

MIN_YEAR = 2013
MAX_YEAR = 2029

POLICY_SCHEMA = {
    "labels": {
        "year": {
            "type": "int",
            "validators": {
                "choice": {"choices": [yr for yr in range(MIN_YEAR, MAX_YEAR + 1)]}
            },
        },
        "MARS": {
            "type": "str",
            "validators": {
                "choice": {
                    "choices": ["single", "mjoint", "mseparate", "headhh", "widow"]
                }
            },
        },
        "idedtype": {
            "type": "str",
            "validators": {
                "choice": {
                    "choices": ["med", "sltx", "retx", "cas", "misc", "int", "char"]
                }
            },
        },
        "EIC": {
            "type": "str",
            "validators": {"choice": {"choices": ["0kids", "1kid", "2kids", "3+kids"]}},
        },
        "data_source": {
            "type": "str",
            "validators": {"choice": {"choices": ["PUF", "CPS", "other"]}},
        },
    },
    "additional_members": {
        "section_1": {"type": "str"},
        "section_2": {"type": "str"},
        "start_year": {"type": "int"},
        "checkbox": {"type": "bool"},
    },
}


def convert_defaults(pcl=DEFAULTS, ignore_data_source=True):
    pcl = paramtools.read_json(pcl)

    def handle_data_source(param_data):
        puf = param_data["compatible_data"]["puf"]
        cps = param_data["compatible_data"]["cps"]
        if (puf and cps) or ignore_data_source:
            return {}
        elif puf:
            return {"data_source": "PUF"}
        elif cps:
            return {"data_source": "CPS"}
        else:
            # both are false?
            return {"data_source": "other"}

    type_map = {"real": "float", "boolean": "bool", "integer": "int", "string": "str"}

    new_pcl = defaultdict(dict)
    new_pcl["schema"] = POLICY_SCHEMA
    # LAST_YEAR = 2026
    # pol = taxcalc.Policy()
    # pol.set_year(2026)
    for param, item in pcl.items():
        values = []
        pol_val = item["value"]
        min_year = min(item["value_yrs"])
        data_source = handle_data_source(item)
        if isinstance(pol_val[0], list):
            for year in range(len(pol_val)):
                # if min_year + year > LAST_YEAR:
                #     break
                for dim1 in range(len(pol_val[0])):
                    values.append(
                        {
                            "year": min_year + year,
                            item["vi_name"]: item["vi_vals"][dim1],
                            "value": pol_val[year][dim1],
                            **data_source,
                        }
                    )
        else:
            for year in range(len(pol_val)):
                # if min_year + year > LAST_YEAR:
                #     break
                values.append(
                    {"year": min_year + year, "value": pol_val[year], **data_source}
                )

        new_pcl[param]["value"] = values
        new_pcl[param]["title"] = pcl[param]["long_name"]
        new_pcl[param]["type"] = type_map[pcl[param]["value_type"]]

        new_pcl[param]["validators"] = {"range": pcl[param]["valid_values"]}

        # checkbox if indexable
        if item["indexable"]:
            if item["indexed"]:
                new_pcl[param]["checkbox"] = True
            else:
                new_pcl[param]["checkbox"] = False

        to_keep = list(POLICY_SCHEMA["additional_members"].keys()) + [
            "description",
            "notes",
        ]
        for k in to_keep:
            if k in pcl[param]:
                new_pcl[param][k] = pcl[param][k]

        if pcl[param].get("indexable", False):
            new_pcl[param]["indexed"] = pcl[param]["indexed"]

    return new_pcl
