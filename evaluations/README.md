# Evaluations

The evaluation specs that drive TEEHR Hub, one file per evaluation:
`<project>/<evaluation name>.yaml`. The spec format is documented in teehr-core's
[spec guide](https://github.com/RTIInternational/teehr-core/blob/main/docs/spec/README.md).

They're loaded by hand for now (platform admin):

```
teehr evaluations plan evaluations/platform/nwm30_medium_range_by_location.yaml -p platform
teehr evaluations save nwm30_medium_range_by_location evaluations/platform/nwm30_medium_range_by_location.yaml -p platform
teehr runs start nwm30_medium_range_by_location -p platform --wait
```

Saving an unchanged spec does nothing; a changed one saves the next version. Change a spec
here and save it again rather than editing it through the API, so this folder stays the record.

| Evaluation | Compares | Groups by |
| --- | --- | --- |
| `nwm30_medium_range_by_location` | NWM 3.0 medium range vs USGS streamflow | gage, member |
| `nwm30_medium_range_by_lead_time` | NWM 3.0 medium range vs USGS streamflow | gage, member, 6-hour lead time bin |

Both compute count, RSR (`root_mean_standard_deviation_ratio`), relative bias, NSE and KGE,
the legacy forecast metrics (`fcst_metrics_by_location`, `fcst_metrics_by_lead_time_bins`).
