import numpy as np
import pytest

import taxcalc

from taxparams import TaxParams


def cmp_with_taxcalc_values(taxparams, pol=None):
    if pol is None:
        pol = taxcalc.Policy()
    # test all keys are the same.
    assert set(map(lambda x: x[1:], pol._vals.keys())) == set(taxparams._data.keys())
    # test all values are the same.
    pol.set_year(2029)
    # breakpoint()
    for param in taxparams._data:
        np.testing.assert_allclose(getattr(pol, f"_{param}"), getattr(taxparams, param))
    taxparams.set_state()
    for param in taxparams._data:
        np.testing.assert_allclose(getattr(pol, f"_{param}"), getattr(taxparams, param))


@pytest.fixture(scope="function")
def taxparams():
    return TaxParams()


def test_init(taxparams):
    assert taxparams


def test_values(taxparams):
    cmp_with_taxcalc_values(taxparams)


def test_simple_adj(taxparams):
    pol = taxcalc.Policy()
    pol.implement_reform(
        {
            "EITC_c": {
                2020: [10000, 10001, 10002, 10003],
                2023: [20000, 20001, 20002, 20003],
            }
        }
    )

    taxparams.adjust(
        {
            "EITC_c": [
                {"year": 2020, "EIC": "0kids", "value": 10000},
                {"year": 2020, "EIC": "1kid", "value": 10001},
                {"year": 2020, "EIC": "2kids", "value": 10002},
                {"year": 2020, "EIC": "3+kids", "value": 10003},
                {"year": 2023, "EIC": "0kids", "value": 20000},
                {"year": 2023, "EIC": "1kid", "value": 20001},
                {"year": 2023, "EIC": "2kids", "value": 20002},
                {"year": 2023, "EIC": "3+kids", "value": 20003},
            ]
        }
    )
    cmp_with_taxcalc_values(taxparams, pol)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_indexed_status(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform({"EITC_c-indexed": {year: False}})

    taxparams.adjust({"EITC_c-indexed": [{"year": year, "value": False}]})
    cmp_with_taxcalc_values(taxparams, pol)


def test_adj_indexed_status_beginning(taxparams):
    pol = taxcalc.Policy()
    pol.implement_reform({"EITC_c-indexed": {2013: False}})

    taxparams.adjust({"EITC_c-indexed": False})
    cmp_with_taxcalc_values(taxparams, pol)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_indexed_status_and_param_value(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform(
        {
            "EITC_c": {year: [10000, 10001, 10002, 10003]},
            "EITC_c-indexed": {year: False},
        }
    )

    taxparams.adjust(
        {
            "EITC_c": [
                {"year": year, "EIC": "0kids", "value": 10000},
                {"year": year, "EIC": "1kid", "value": 10001},
                {"year": year, "EIC": "2kids", "value": 10002},
                {"year": year, "EIC": "3+kids", "value": 10003},
            ],
            "EITC_c-indexed": [{"year": year, "value": False}],
        }
    )
    cmp_with_taxcalc_values(taxparams, pol)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_activates_index(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform({"CTC_c": {year: 1005}, "CTC_c-indexed": {year: True}})

    taxparams.adjust(
        {
            "CTC_c": [{"year": year, "value": 1005}],
            "CTC_c-indexed": [{"year": year, "value": True}],
        }
    )
    cmp_with_taxcalc_values(taxparams, pol)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_CPI_offset(year):
    def convert(arr):
        return {2013 + i: arr[i] for i in range(len(arr))}

    taxparams = TaxParams()
    taxparams_cpi = TaxParams()
    taxparams_cpi.adjust({"CPI_offset": [{"year": year, "value": -0.001}]})

    def_rates = taxparams.inflation_rates
    default_inflation = np.array([def_rates[yr] for yr in sorted(def_rates)])

    new_rates = taxparams_cpi.inflation_rates
    new_inflation = np.array([new_rates[yr] for yr in sorted(new_rates)])

    exp_inflation = new_inflation - taxparams_cpi.CPI_offset
    np.testing.assert_allclose(default_inflation, exp_inflation)

    pol = taxcalc.Policy()
    pol.set_year(year)
    pol.implement_reform({"CPI_offset": {year: -0.001}})

    cmp_with_taxcalc_values(taxparams_cpi, pol)


def test_multiple_cpi_swaps():

    pol = taxcalc.Policy()
    pol.implement_reform(
        {
            "II_em": {2016: 6000, 2018: 7500, 2020: 9000},
            "II_em-indexed": {2016: False, 2018: True},
        }
    )

    taxparams = TaxParams()
    taxparams.adjust(
        {
            "II_em": [
                {"year": 2016, "value": 6000},
                {"year": 2018, "value": 7500},
                {"year": 2020, "value": 9000},
            ],
            "II_em-indexed": [
                {"year": 2016, "value": False},
                {"year": 2018, "value": True},
            ],
        }
    )

    cmp_with_taxcalc_values(taxparams, pol)


def test_multiple_cpi_swaps2():
    pol = taxcalc.Policy()
    pol.implement_reform(
        {
            "II_em": {2016: 6000, 2018: 7500, 2020: 9000},
            "II_em-indexed": {2016: False, 2018: True},
            "SS_Earnings_c": {2016: 300000, 2018: 500000, 2020: 700000},
            "SS_Earnings_c-indexed": {2017: False, 2019: True},
            "AMT_em-indexed": {2017: False, 2020: True},
        }
    )

    taxparams = TaxParams()
    taxparams.adjust(
        {
            "SS_Earnings_c": [
                {"year": 2016, "value": 300000},
                {"year": 2018, "value": 500000},
                {"year": 2020, "value": 700000},
            ],
            "SS_Earnings_c-indexed": [
                {"year": 2017, "value": False},
                {"year": 2019, "value": True},
            ],
            "AMT_em-indexed": [
                {"year": 2017, "value": False},
                {"year": 2020, "value": True},
            ],
            "II_em": [
                {"year": 2016, "value": 6000},
                {"year": 2018, "value": 7500},
                {"year": 2020, "value": 9000},
            ],
            "II_em-indexed": [
                {"year": 2016, "value": False},
                {"year": 2018, "value": True},
            ],
        }
    )

    cmp_with_taxcalc_values(taxparams, pol)


def test_adj_CPI_offset_and_index_status():
    taxparams = TaxParams()
    taxparams.adjust(
        {
            "CPI_offset": [{"year": 2020, "value": -0.005}],
            "CTC_c-indexed": [{"year": 2020, "value": True}],
        }
    )

    pol = taxcalc.Policy()
    pol.implement_reform({"CTC_c-indexed": {2020: True}, "CPI_offset": {2020: -0.005}})

    cmp_with_taxcalc_values(taxparams, pol)
