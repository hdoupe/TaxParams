import paramtools
import taxcalc
import numpy as np
import copy


from taxparams import utils


class TaxParams(paramtools.Parameters):
    defaults = utils.convert_defaults()
    array_first = True
    label_to_extend = "year"
    uses_extend_func = True

    WAGE_INDEXED_PARAMS = (
        "SS_Earnings_c",
        "SS_Earnings_thd"
    )

    def __init__(self, *args, **kwargs):
        self._wage_rates = None
        self._inflation_rates = None
        super().__init__(*args, **kwargs)
        self._init_values = {
            param: data["value"] for param, data in self.read_params(self.defaults).items()
            if param != "schema"
        }

    def adjust(self, params_or_path, **kwargs):
        """
        Custom adjust method that handles special indexing logic. The logic
        is:

        1. If "CPI_offset" is modified, update the inflation rates and the values
            of all parameters that are set in the year after the "CPI_offset"
            parameter is changed.
        2. If the "indexed" status is updated for any parameter:
            a. extend the values of that parameter to the year in which
                the status is changed.
            b. change the the indexed status for the parameter.
            c. extend the values of that parameter until the highest year,
                using the new "indexed" status.
        3. Update all parameters that are not indexing related, i.e. they are
            not "CPI_offset" or do not end with "-indexed".
        4. Return parsed adjustment with all adjustments, including "-indexed"
            parameters.

        Notable side-effects:
            - All values of indexed parameters, including default values, are wiped out after
                the first year in which the "CPI_offset" is changed. This is only necessary because
                Tax-Calculator hard-codes inflated values. If Tax-Calculator only hard-coded values
                that were changed for non-inflation related reasons, then this would not be
                necessary for default values.
            - All values of a parameter whose indexed status is adjusted are wiped out after the
                year in which the value is adjusted for the same hard-coding reason.
        """
        min_year = min(self._stateless_label_grid["year"])

        # turn off extra ops during the intermediary adjustments so that
        # expensive and unnecessary operations are not changed.
        label_to_extend = self.label_to_extend
        array_first = self.array_first
        self.array_first = False

        params = self.read_params(params_or_path)

        # Check if CPI_offset is adjusted. If so, reset values of all indexed
        # parameters after year where CPI_offset is changed. If CPI_offset is
        # changed multiple times, then the reset year is the year in which the
        # CPI_offset is first changed.
        if params.get("CPI_offset") is not None:
            cpi_adj = super().adjust({"CPI_offset": params["CPI_offset"]})
            cpi_min_year = min(cpi_adj["CPI_offset"], key= lambda vo: vo["year"])
            self.set_rates()
            to_delete = {}
            for param in self._data:
                if self._data[param].get("indexed", False):
                    gte = self.select_gt(param, True, year=cpi_min_year["year"])
                    to_delete[param] = list([dict(vo, **{"value": None}) for vo in gte])

            super().adjust(to_delete)

        # no need to do extra work to extend parameters in the next block.
        self.label_to_extend = None
        needs_reset = set([])
        for param, values in params.items():
            if param.endswith("-indexed"):
                base_param = param.split("-indexed")[0]
                if isinstance(values, bool):
                    indexed_val = values
                    year = min_year
                elif isinstance(values, list) and len(values) == 1:
                    indexed_val = values[0]["value"]
                    year = values[0].get("year", min_year)
                else:
                    raise Exception("Index adjustment parameter must be a boolean or list with one item.")
                # reset all values to default.
                super().adjust({base_param: [{"value": None}]})
                super().adjust({base_param: self._init_values[base_param]})

                # get and delete all default values after year where indexed status changed.
                gte = self.select_gt(base_param, True, year=year)
                self._adjust({base_param: list([dict(vo, **{"value": None}) for vo in gte])})

                # extend values for this parameter to the year where the indexed
                # status changes.
                if year > min_year:
                    self.extend(
                        params=[base_param],
                        label_to_extend="year",
                        label_to_extend_values=list(range(min_year, year + 1))
                    )

                # set indexed status.
                self._data[base_param]["indexed"] = indexed_val

                # extend values remaining years.
                self.extend(
                    params=[base_param],
                    label_to_extend="year",
                )

                needs_reset = needs_reset | {base_param}

        # re-instate ops.
        self.label_to_extend = label_to_extend
        self.array_first = array_first

        # filter out "-indexed" params
        nonindexed_params = {
            param: val for param, val in params.items()
            if not param.endswith("-indexed")
        }

        needs_reset = needs_reset - set(nonindexed_params.keys())
        if needs_reset:
            self._set_state(params=needs_reset)


        # Do adjustment for all non-indexing related parameters.
        adj = super().adjust(nonindexed_params)

        # add indexing params back for return to user.
        adj.update({
            param: val for param, val in params.items()
            if param.endswith("-indexed")
        })
        return adj


    def get_index_rate(self, param, label_to_extend_val):
        """
        Initalize indexing data and return the indexing rate value
        depending on the parameter name and label_to_extend_val, the value of
        label_to_extend.

        Returns: rate to use for indexing.
        """
        if not self._inflation_rates or not self._wage_rates:
            self.set_rates()
        if param in self.WAGE_INDEXED_PARAMS:
            return self._wage_rates[label_to_extend_val]
        else:
            return self._inflation_rates[label_to_extend_val]

    def set_rates(self):
        """Initialize taxcalc indexing data."""
        cpi_vals = [
            vo["value"] for vo in self._data["CPI_offset"]["value"]
        ]
        # extend cpi_offset values through budget window if they
        # have not been extended already.
        cpi_vals = cpi_vals + cpi_vals[-1:] * (
            2029 - 2013 + 1 - len(cpi_vals)
        )
        cpi_offset = {
            (2013 + ix): val for ix, val in enumerate(cpi_vals)
        }
        rates = taxcalc.GrowFactors()
        self._inflation_rates = {
            (2013 + year): np.round(rate + cpi_offset[2013 + year], 4)
            for year, rate in enumerate(rates.price_inflation_rates(2013, 2029))
        }
        self._wage_rates = {
            (2013 + year): rate
            for year, rate in enumerate(rates.wage_growth_rates(2013, 2029))
        }

    def select_gte(self, param, exact_match, **labels):
        return paramtools.select(
            self._data[param]["value"],
            exact_match,
            lambda x, y: all(x >= item for item in y),
            all,
            labels,
        )
