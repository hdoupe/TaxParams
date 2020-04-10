import paramtools as pt
from paramtools.select import select_lt
import taxcalc
import numpy as np
import marshmallow as ma
import copy


from taxparams import utils


class CompatibleDataSchema(ma.Schema):
    """
    Schema for Compatible data object
    {
        "compatible_data": {"data1": bool, "data2": bool, ...}
    }
    """

    puf = ma.fields.Boolean()
    cps = ma.fields.Boolean()


pt.register_custom_type(
    "compatible_data",
    ma.fields.Nested(CompatibleDataSchema())
)


class TaxParams(pt.Parameters):
    defaults = utils.convert_defaults()
    array_first = True
    label_to_extend = "year"
    uses_extend_func = True

    WAGE_INDEXED_PARAMS = ("SS_Earnings_c", "SS_Earnings_thd")

    def __init__(self, *args, **kwargs):
        self._wage_growth_rates = None
        self._inflation_rates = None
        self._gfactors = None
        self._wage_indexed = TaxParams.WAGE_INDEXED_PARAMS
        super().__init__(*args, **kwargs)
        self._init_values = {
            param: data["value"]
            for param, data in self.read_params(self.defaults).items()
            if param != "schema"
        }

    def adjust(self, params_or_path, **kwargs):
        """
        Custom adjust method that handles special indexing logic. The logic
        is:

        1. If "CPI_offset" is adjusted, revert all values of indexed parameters
            to the 'known' values:
            a. The current values of parameters that are being adjusted are
                deleted after the first year in which CPI_offset is adjusted.
            b. The current values of parameters that are not being adjusted
                (i.e. are not in params) are deleted after the last known year.
            After the 'unknown' values have been deleted, the last known value
            is extrapolated through the budget window. If there are indexed
            parameters in the adjustment, they will be included in the final
            adjustment call (unless their indexed status is changed).
        2. If the "indexed" status is updated for any parameter:
            a. If a parameter has values that are being adjusted before
                the indexed status is adjusted, update those parameters first.
            b. Extend the values of that parameter to the year in which
                the status is changed.
            c. Change the the indexed status for the parameter.
            d. Update parameter values in adjustment that are adjusted after
                the year in which the indexed status changes.
            e. Using the new "-indexed" status, extend the values of that
                parameter through the remaining years or until the -indexed
                status changes again.
        3. Update all parameters that are not indexing related, i.e. they are
            not "CPI_offset" or do not end with "-indexed".
        4. Return parsed adjustment with all adjustments, including "-indexed"
            parameters.

        Notable side-effects:
            - All values of indexed parameters, including default values, are
                wiped out after the first year in which the "CPI_offset" is
                changed. This is only necessary because Tax-Calculator
                hard-codes inflated values. If Tax-Calculator only hard-coded
                values that were changed for non-inflation related reasons,
                then this would not be necessary for default values.
            - All values of a parameter whose indexed status is adjusted are
              wiped out after the year in which the value is adjusted for the
              same hard-coding reason.
        """
        min_year = min(self._stateless_label_grid["year"])

        # Temporarily turn off extra ops during the intermediary adjustments
        # so that expensive and unnecessary operations are not run.
        label_to_extend = self.label_to_extend
        array_first = self.array_first
        self.array_first = False

        params = self.read_params(params_or_path)

        # Check if CPI_offset is adjusted. If so, reset values of all indexed
        # parameters after year where CPI_offset is changed. If CPI_offset is
        # changed multiple times, then reset values after the first year in
        # which the CPI_offset is changed.
        needs_reset = []
        if params.get("CPI_offset") is not None:
            # Update CPI_offset with new value.
            cpi_adj = super().adjust(
                {
                    "CPI_offset": params["CPI_offset"]
                },
                **kwargs
            )
            # turn off extend now that CPI_offset has been updated.
            self.label_to_extend = None
            # Get first year in which CPI_offset is changed.
            cpi_min_year = min(
                cpi_adj["CPI_offset"], key=lambda vo: vo["year"]
            )
            # Apply new CPI_offset values to inflation rates
            rate_adjustment_vals = self.select_gt(
                "CPI_offset", True, year=cpi_min_year["year"] - 1
            )
            for cpi_vo in rate_adjustment_vals:
                self._inflation_rates[cpi_vo["year"] - self.start_year] += \
                    cpi_vo["value"]
            # 1. delete all unknown values.
            # 1.a for revision these are years specified after cpi_min_year
            to_delete = {}
            for param in params:
                if param == "CPI_offset" or param in self._wage_indexed:
                    continue
                if param.endswith("-indexed"):
                    param = param.split("-indexed")[0]
                if self._data[param].get("indexed", False):
                    gt = self.select_gt(param, True, year=cpi_min_year["year"])
                    to_delete[param] = [
                        dict(vo, **{"value": None}) for vo in gt
                    ]
                    needs_reset.append(param)
            super().adjust(to_delete, **kwargs)

            # 1.b for all others these are years after last_known_year
            to_delete = {}
            last_known_year = max(cpi_min_year["year"], self._last_known_year)
            for param in self._data:
                if (
                    param in params or
                    param == "CPI_offset" or
                    param in self.WAGE_INDEXED_PARAMS
                ):
                    continue
                if self._data[param].get("indexed", False):
                    gt = self.select_gt(param, True, year=last_known_year)
                    to_delete[param] = [
                        dict(vo, **{"value": None}) for vo in gt
                    ]
                    needs_reset.append(param)

            super().adjust(to_delete, **kwargs)

            self.extend(label_to_extend="year")

        # 2. Handle -indexed parameters.
        self.label_to_extend = None
        index_affected = set([])
        for param, values in params.items():
            if param.endswith("-indexed"):
                base_param = param.split("-indexed")[0]
                if not self._data[base_param].get("indexable", None):
                    msg = f"Parameter {base_param} is not indexable."
                    raise pt.ValidationError(
                        {"errors": {base_param: msg}},
                        labels=None
                    )
                index_affected |= {param, base_param}
                indexed_changes = {}
                if isinstance(values, bool):
                    indexed_changes[min_year] = values
                elif isinstance(values, list):
                    for vo in values:
                        indexed_changes[vo.get("year", min_year)] = vo["value"]
                else:
                    raise Exception(
                        "Index adjustment parameter must be a boolean or list."
                    )
                # 2.a Adjust values less than first year in which index status
                # was changed.
                if base_param in params:
                    min_index_change_year = min(indexed_changes.keys())
                    vos = select_lt(
                        params[base_param],
                        False,
                        {"year": min_index_change_year}
                    )
                    if vos:
                        min_adj_year = min(
                            vos,
                            key=lambda vo: vo["year"]
                        )["year"]
                        gt = self.select_gt(
                            base_param,
                            True,
                            year=min_adj_year
                        )
                        super().adjust(
                            {
                                base_param: [
                                    dict(vo, **{"value": None}) for vo in gt
                                ]
                            }
                        )
                        super().adjust({base_param: vos}, **kwargs)
                        self.extend(
                            params=[base_param],
                            label_to_extend="year",
                            label_to_extend_values=list(
                                range(min_year, min_index_change_year)
                            ),
                        )

                for year in sorted(indexed_changes):
                    indexed_val = indexed_changes[year]
                    # Get and delete all default values after year where
                    # indexed status changed.
                    gte = self.select_gt(base_param, True, year=year)
                    super().adjust(
                        {
                            base_param: [
                                dict(vo, **{"value": None}) for vo in gte
                            ]
                        }
                    )

                    # 2.b Extend values for this parameter to the year where
                    # the indexed status changes.
                    if year > min_year:
                        self.extend(
                            params=[base_param],
                            label_to_extend="year",
                            label_to_extend_values=list(
                                range(min_year, year + 1)
                            ),
                        )

                    # 2.c Set indexed status.
                    self._data[base_param]["indexed"] = indexed_val

                    # 2.d Adjust with values greater than or equal to current
                    # year in params
                    if base_param in params:
                        vos = pt.select_gt(
                            params[base_param], False, {"year": year - 1}
                        )
                        super().adjust({base_param: vos}, **kwargs)

                    # 2.e Extend values through remaining years.
                    self.extend(params=[base_param], label_to_extend="year")

                needs_reset.append(base_param)
        # Re-instate ops.
        self.label_to_extend = label_to_extend
        self.array_first = array_first

        # Filter out "-indexed" params.
        nonindexed_params = {
            param: val for param, val in params.items()
            if param not in index_affected
        }

        needs_reset = set(needs_reset) - set(nonindexed_params.keys())
        if needs_reset:
            self._set_state(params=needs_reset)

        # 3. Do adjustment for all non-indexing related parameters.
        adj = super().adjust(nonindexed_params, **kwargs)

        # 4. Add indexing params back for return to user.
        adj.update(
            {
                param: val for param, val in params.items()
                if param in index_affected
            }
        )
        return adj

    def get_index_rate(self, param, label_to_extend_val):
        """
        Initalize indexing data and return the indexing rate value
        depending on the parameter name and label_to_extend_val, the value of
        label_to_extend.
        Returns: rate to use for indexing.
        """
        if not self._inflation_rates or not self._wage_growth_rates:
            self.set_rates()
        if param in self.WAGE_INDEXED_PARAMS:
            return self.wage_growth_rates(year=label_to_extend_val)
        else:
            return self.inflation_rates(year=label_to_extend_val)

    def wage_growth_rates(self, year=None):
        if year is not None:
            return self._wage_growth_rates[year - self.start_year]
        return self._wage_growth_rates or []

    def inflation_rates(self, year=None):
        if year is not None:
            return self._inflation_rates[year - self.start_year]
        return self._inflation_rates or []

    def set_rates(self):
        """Initialize taxcalc indexing data."""
        cpi_vals = [vo["value"] for vo in self._data["CPI_offset"]["value"]]
        # extend cpi_offset values through budget window if they
        # have not been extended already.
        cpi_vals = cpi_vals + cpi_vals[-1:] * (2030 - 2013 + 1 - len(cpi_vals))
        cpi_offset = {(2013 + ix): val for ix, val in enumerate(cpi_vals)}

        if not self._gfactors:
            self._gfactors = taxcalc.GrowFactors()

        self._inflation_rates = [
            np.round(rate + cpi_offset[2013 + ix], 4)
            for ix, rate in enumerate(
                self._gfactors.price_inflation_rates(2013, 2030)
            )
        ]

        self._wage_growth_rates = self._gfactors.wage_growth_rates(2013, 2030)

    @property
    def current_year(self):
        return self.label_grid["year"][0]

    @property
    def start_year(self):
        return self._stateless_label_grid["year"][0]

    @property
    def end_year(self):
        return self._stateless_label_grid["year"][-1]

    @property
    def num_years(self):
        return self.end_year - self.start_year + 1

    @property
    def _last_known_year(self):
        return taxcalc.Policy.LAST_KNOWN_YEAR
