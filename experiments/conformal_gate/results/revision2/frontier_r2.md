<!-- Source: voximul:~/ico-experiments/conformal_gate/outputs/frontier_r2.txt; scripts/run_revision.sh at code 348bc2e+ (floored bounds, robust sharpness, validity detail); generated 2026-10-21T01:43Z -->
## Policy points (mean over containers)
| conformal_modify_chronos2 | 0.01 | slack 0.1776 | violation 0.0029 |
| conformal_modify_chronos2 | 0.02 | slack 0.1773 | violation 0.0022 |
| conformal_modify_chronos2 | 0.05 | slack 0.1764 | violation 0.0024 |
| conformal_modify_chronos2 | 0.1 | slack 0.1759 | violation 0.0024 |
| conformal_modify_chronos2 | 0.2 | slack 0.1757 | violation 0.0025 |
| conformal_modify_lgbm | 0.01 | slack 0.1778 | violation 0.0029 |
| conformal_modify_lgbm | 0.02 | slack 0.1778 | violation 0.0022 |
| conformal_modify_lgbm | 0.05 | slack 0.1765 | violation 0.0024 |
| conformal_modify_lgbm | 0.1 | slack 0.1759 | violation 0.0027 |
| conformal_modify_lgbm | 0.2 | slack 0.1756 | violation 0.0028 |
| conformal_modify_toto2_313m | 0.01 | slack 0.1806 | violation 0.0029 |
| conformal_modify_toto2_313m | 0.02 | slack 0.1799 | violation 0.0021 |
| conformal_modify_toto2_313m | 0.05 | slack 0.1768 | violation 0.0022 |
| conformal_modify_toto2_313m | 0.1 | slack 0.1760 | violation 0.0020 |
| conformal_modify_toto2_313m | 0.2 | slack 0.1757 | violation 0.0021 |
| conformal_size_chronos2 | 0.01 | slack 0.1451 | violation 0.0053 |
| conformal_size_chronos2 | 0.02 | slack 0.1003 | violation 0.0128 |
| conformal_size_chronos2 | 0.05 | slack 0.0628 | violation 0.0401 |
| conformal_size_chronos2 | 0.1 | slack 0.0424 | violation 0.0929 |
| conformal_size_chronos2 | 0.2 | slack 0.0288 | violation 0.1978 |
| conformal_size_lgbm | 0.01 | slack 0.1465 | violation 0.0047 |
| conformal_size_lgbm | 0.02 | slack 0.1031 | violation 0.0107 |
| conformal_size_lgbm | 0.05 | slack 0.0650 | violation 0.0335 |
| conformal_size_lgbm | 0.1 | slack 0.0444 | violation 0.0743 |
| conformal_size_lgbm | 0.2 | slack 0.0313 | violation 0.1500 |
| conformal_size_toto2_313m | 0.01 | slack 0.1473 | violation 0.0053 |
| conformal_size_toto2_313m | 0.02 | slack 0.1010 | violation 0.0123 |
| conformal_size_toto2_313m | 0.05 | slack 0.0557 | violation 0.0405 |
| conformal_size_toto2_313m | 0.1 | slack 0.0287 | violation 0.0939 |
| conformal_size_toto2_313m | 0.2 | slack 0.0149 | violation 0.1960 |
| fixed_headroom | 1 | slack 0.0857 | violation 0.0819 |
| fixed_headroom | 1.1 | slack 0.1688 | violation 0.0052 |
| fixed_headroom | 1.25 | slack 0.2686 | violation 0.0011 |
| fixed_headroom | 1.5 | slack 0.3905 | violation 0.0004 |
| fixed_headroom | 2 | slack 0.5429 | violation 0.0000 |
| ico_margin | 0 | slack 0.0100 | violation 0.2703 |
| ico_margin | 0.1 | slack 0.1000 | violation 0.0139 |
| ico_margin | 0.2 | slack 0.1750 | violation 0.0042 |
| ico_margin | 0.3 | slack 0.2385 | violation 0.0023 |
| ico_margin | 0.5 | slack 0.3400 | violation 0.0006 |
| ico_margin | 0.75 | slack 0.4343 | violation 0.0003 |
| ico_margin | 1 | slack 0.5050 | violation 0.0000 |
| ico_margin | 1.5 | slack 0.6040 | violation 0.0000 |
| vpa_percentile | 50 | slack 0.1374 | violation 0.0424 |
| vpa_percentile | 75 | slack 0.1683 | violation 0.0077 |
| vpa_percentile | 90 | slack 0.1870 | violation 0.0020 |
| vpa_percentile | 95 | slack 0.1960 | violation 0.0009 |
| vpa_percentile | 99 | slack 0.2089 | violation 0.0005 |
| vpa_percentile | 99.9 | slack 0.2159 | violation 0.0003 |
## Slack at matched violation (interpolated; mean [95% bootstrap CI over containers]); -- = out of range
| family | viol=0.002 | viol=0.005 | viol=0.01 | viol=0.02 | viol=0.05 |
|---|---|---|---|---|---|
| conformal_modify_chronos2 | -- | -- | -- | -- | -- |
| conformal_modify_lgbm | -- | -- | -- | -- | -- |
| conformal_modify_toto2_313m | -- | -- | -- | -- | -- |
| conformal_size_chronos2 | -- | -- | 0.1171 [0.1059, 0.1287] | 0.0905 [0.0846, 0.0967] | 0.0590 [0.0538, 0.0638] |
| conformal_size_lgbm | -- | 0.1444 [0.1309, 0.1484] | 0.1081 [0.0966, 0.1220] | 0.0876 [0.0797, 0.0946] | 0.0567 [0.0509, 0.0622] |
| conformal_size_toto2_313m | -- | -- | 0.1163 [0.1052, 0.1305] | 0.0887 [0.0803, 0.0956] | 0.0509 [0.0410, 0.0595] |
| fixed_headroom | 0.2477 [0.1904, 0.2980] | 0.1743 [0.1577, 0.2187] | 0.1637 [0.1518, 0.1767] | 0.1528 [0.1396, 0.1667] | 0.1203 [0.1001, 0.1366] |
| ico_margin | 0.2570 [0.1814, 0.3073] | 0.1689 [0.1387, 0.2172] | 0.1304 [0.0989, 0.1603] | 0.0979 [0.0954, 0.1099] | 0.0874 [0.0845, 0.0905] |
| vpa_percentile | 0.1870 [0.1763, 0.1994] | 0.1772 [0.1654, 0.1863] | 0.1662 [0.1575, 0.1745] | 0.1573 [0.1465, 0.1654] | -- |
