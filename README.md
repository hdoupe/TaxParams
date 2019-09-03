# TaxParams

TaxParams shows how [ParamTools][1] can be used for a complex, real world parameter indexing problem. TaxParams is mostly compatible with the open-source [Tax-Calculator][2] project's parameter processing and validation library. Further, since most of the low-level parameter handling logic is taken care of by ParamTools, this project provides a high-level view of the logic used to index tax policy parameters to inflation. This logic is encapsulated in the `adjust` method of the `TaxParams` class.

## What is parameter indexing

A parameter is indexed when its value grows over time at some rate or set of rates. For example, tax parameters like the standard deduction are often indexed to price inflation. So, the value of the standard deduction actually increases every year by 1 or 2% depending on that year's inflation rate. Lucky for us, [ParamTools already implements parameter indexing][3].

## How does Tax-Calculator do indexing

Before we dive into the details, let's take a 10,000 foot view of how Tax-Calculator does parameter indexing. First, not all parameters are indexed. It doesn't make sense to index some parameters. For example, how do you index a tax rate? Second, not all of the parameters that can be indexed are indexed. Whether the value for a tax law provision is indexed or not is a policy decision. A parameter's indexing status can be turned on and off by setting the value of its name plus "-indexing" to `true` or `false`. For example, the following code snippet turns on indexing for the Child Tax Credit (`CTC`):

```python
taxparams.adjust(
    {
        "CTC_c-indexed": [{"year": 2020, "value": True}],
    }
)
```

Third, Tax-Calculator has a [`CPI_offset`][4] parameter that is added to the traditional CPI measure to estimate a chained CPI. Finally, if the indexing status of a parameter changes or if the indexing rates change (i.e. by changing `CPI_offset`), the values of all affected parameters need to be updated, but only after the year in which the change takes effect.

## Implementation

ParamTools allows you to write custom `adjust` methods on top of its `adjust` method by using the following syntax (todo: link to custom adjust docs once published):

```python
import paramtools


class Params(paramtools.Parameters):
    def adjust(self, params_or_path, **kwargs):
        params = self.read_params(params_or_path)

        # ... custom logic here

        return super().adjust(params, **kwargs)
```

TaxParams implements all of the logic described in the previous section within the `TaxParams.adjust` method. Here's a breakdown of the algorithm that is used to do adjustments with indexing:

1. If `CPI_offset` is modified, update the inflation rates and the values
    of all parameters that are set in the year after the `CPI_offset`
    parameter is changed.
2. If the "indexed" status is updated for any parameter:

    a. extend the values of that parameter to the year in which
        the status is changed.

    b. change the the indexed status for the parameter.

    c. extend the remaining values of that parameter until the final year,
        using the new "indexed" status.
3. Update all parameters that are not indexing related, i.e. they are
    not `CPI_offset` or do not end with "-indexed".
4. Return parsed adjustment with all adjustments, including "-indexed"
    parameters.

For the exact implementation, check out the `TaxParams.adjust` method.


## Disclaimer

The development of this package is 1% me understanding how indexing rates are related to tax policy and 99% percent me reverse-engineering Tax-Calculator. There may be (and most certainly are) errors in this package or in my description of parameter indexing.


[1]: https://github.com/PSLmodels/ParamTools
[2]: https://github.com/PSLmodels/Tax-Calculator/
[3]: https://paramtools.org/api/indexing/
[4]: https://github.com/PSLmodels/Tax-Calculator/blob/2.5.0/taxcalc/policy_current_law.json#L2-L29