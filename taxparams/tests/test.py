import numpy as np
import pytest

import taxcalc

from taxparams import TaxParams


def cmp_with_taxcalc_values(taxparams):
    pol = taxcalc.Policy()
    # test all keys are the same.
    assert set(map(lambda x: x[1:], pol._vals.keys())) == set(taxparams._data.keys())
    # test all values are the same.
    pol.set_year(2029)
    for param in taxparams._data:
        np.testing.assert_allclose(
            getattr(pol, f"_{param}"), getattr(taxparams, param)
        )


@pytest.fixture(scope="function")
def taxparams():
    return TaxParams()


def test_init(taxparams):
    assert taxparams


def test_values(taxparams):
    cmp_with_taxcalc_values(taxparams)


def test_simple_adj(taxparams):
    pol = taxcalc.Policy()
    pol.implement_reform({
        "EITC_c": {
            2020: [10000, 10001, 10002, 10003],
            2023: [20000, 20001, 20002, 20003]
        },
    })

    taxparams.adjust({
        "EITC_c": [
            {'year': 2020, 'EIC': '0kids', 'value': 10000},
            {'year': 2020, 'EIC': '1kid', 'value': 10001},
            {'year': 2020, 'EIC': '2kids', 'value': 10002},
            {'year': 2020, 'EIC': '3+kids', 'value': 10003},
            {'year': 2023, 'EIC': '0kids', 'value': 20000},
            {'year': 2023, 'EIC': '1kid', 'value': 20001},
            {'year': 2023, 'EIC': '2kids', 'value': 20002},
            {'year': 2023, 'EIC': '3+kids', 'value': 20003},

        ],        
    })
    np.testing.assert_allclose(pol._EITC_c, taxparams.EITC_c)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_indexed_status(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform({
        "EITC_c-indexed": {year: False}
    })

    taxparams.adjust({
        "EITC_c-indexed": [{"year": year, "value": False}]
    })
    np.testing.assert_allclose(pol._EITC_c, taxparams.EITC_c)


def test_adj_indexed_status_beginning(taxparams):
    pol = taxcalc.Policy()
    pol.implement_reform({
        "EITC_c-indexed": {2013: False}
    })

    taxparams.adjust({
        "EITC_c-indexed": False
    })
    np.testing.assert_allclose(pol._EITC_c, taxparams.EITC_c)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_indexed_status_and_param_value(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform({
        "EITC_c": {
            year: [10000, 10001, 10002, 10003],
        },
        "EITC_c-indexed": {year: False}
    })

    taxparams.adjust({
        "EITC_c": [
            {'year': year, 'EIC': '0kids', 'value': 10000},
            {'year': year, 'EIC': '1kid', 'value': 10001},
            {'year': year, 'EIC': '2kids', 'value': 10002},
            {'year': year, 'EIC': '3+kids', 'value': 10003},
        ],
        "EITC_c-indexed": [{"year": year, "value": False}]
    })
    np.testing.assert_allclose(pol._EITC_c, taxparams.EITC_c)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_activates_index(taxparams, year):
    pol = taxcalc.Policy()
    pol.implement_reform({
        "CTC_c": {
            year: 1005,
        },
        "CTC_c-indexed": {year: True}
    })

    taxparams.adjust({
        "CTC_c": [
            {'year': year, 'value': 1005},
        ],
        "CTC_c-indexed": [{"year": year, "value": True}]
    })
    np.testing.assert_allclose(pol._CTC_c, taxparams.CTC_c)


@pytest.mark.parametrize("year", [2014, 2016, 2018, 2022, 2025])
def test_adj_CPI_offset(year):
    taxparams = TaxParams()
    taxparams_cpi = TaxParams()
    taxparams_cpi.adjust({
        "CPI_offset": [{"year": year, "value": -0.001}]
    })

    default_inflation = np.array([v for v in taxparams._inflation_rates.values()])
    new_inflation = np.array([v for v in taxparams_cpi._inflation_rates.values()])

    exp_inflation = default_inflation - taxparams.CPI_offset + taxparams_cpi.CPI_offset
    np.testing.assert_allclose(
        exp_inflation,
        new_inflation
    )

    cmp_with_taxcalc_values(taxparams)
