# Live envelope: the Go operator's configuration (envelope = ICO candidate)

Generated 2026-10-21T11:04Z on voximul from code 41cfbcd + working-tree changes to run/conformal_eval.py and run/stats_eval.py (variant ico_candidate).
Command: run/conformal_eval.py "variants=[ico_candidate]" skip_decisions=24 out_dir=outputs/panel_live/ico_candidate; then run/stats_eval.py.

```
## Conformal policies on healthy, uninjected containers (mean [95% CI over containers])
ico_candidate/0.01/0.0/modify      n=296 slack 0.1778 [0.1763, 0.1794]  violation 0.0025 [0.0015, 0.0037]  bound-miss 0.0093 [0.0072, 0.0120]  bound-slack 0.0985 [0.0851, 0.1142]  cold 0.718
ico_candidate/0.01/0.0/size        n=296 slack 0.1508 [0.1478, 0.1539]  violation 0.0047 [0.0036, 0.0061]  bound-miss 0.0093 [0.0072, 0.0120]  bound-slack 0.0985 [0.0851, 0.1142]  cold 0.718
ico_candidate/0.01/0.0/veto        n=296 slack 0.1670 [0.1579, 0.1734]  violation 0.0119 [0.0070, 0.0177]  bound-miss 0.0093 [0.0072, 0.0120]  bound-slack 0.0985 [0.0851, 0.1142]  cold 0.718
ico_candidate/0.01/0.005/modify    n=296 slack 0.1788 [0.1771, 0.1805]  violation 0.0025 [0.0014, 0.0038]  bound-miss 0.0184 [0.0138, 0.0234]  bound-slack 0.0930 [0.0800, 0.1077]  cold 0.718
ico_candidate/0.01/0.005/size      n=296 slack 0.1550 [0.1519, 0.1581]  violation 0.0041 [0.0029, 0.0054]  bound-miss 0.0184 [0.0138, 0.0234]  bound-slack 0.0930 [0.0800, 0.1077]  cold 0.718
ico_candidate/0.01/0.005/veto      n=296 slack 0.1755 [0.1738, 0.1774]  violation 0.0077 [0.0041, 0.0117]  bound-miss 0.0184 [0.0138, 0.0234]  bound-slack 0.0930 [0.0800, 0.1077]  cold 0.718
ico_candidate/0.05/0.0/modify      n=296 slack 0.1760 [0.1749, 0.1773]  violation 0.0024 [0.0015, 0.0034]  bound-miss 0.0318 [0.0282, 0.0355]  bound-slack 0.0490 [0.0424, 0.0561]  cold 0.179
ico_candidate/0.05/0.0/size        n=296 slack 0.0483 [-0.0299, 0.0794]  violation 0.0277 [0.0247, 0.0305]  bound-miss 0.0318 [0.0282, 0.0355]  bound-slack 0.0490 [0.0424, 0.0561]  cold 0.179
ico_candidate/0.05/0.0/veto        n=296 slack 0.1727 [0.1688, 0.1763]  violation 0.0111 [0.0045, 0.0189]  bound-miss 0.0318 [0.0282, 0.0355]  bound-slack 0.0490 [0.0424, 0.0561]  cold 0.179
ico_candidate/0.05/0.005/modify    n=296 slack 0.1759 [0.1748, 0.1770]  violation 0.0025 [0.0015, 0.0035]  bound-miss 0.0317 [0.0287, 0.0348]  bound-slack 0.0476 [0.0414, 0.0544]  cold 0.179
ico_candidate/0.05/0.005/size      n=296 slack 0.0473 [-0.0307, 0.0783]  violation 0.0275 [0.0251, 0.0299]  bound-miss 0.0317 [0.0287, 0.0348]  bound-slack 0.0476 [0.0414, 0.0544]  cold 0.179
ico_candidate/0.05/0.005/veto      n=296 slack 0.1726 [0.1687, 0.1761]  violation 0.0106 [0.0046, 0.0178]  bound-miss 0.0317 [0.0287, 0.0348]  bound-slack 0.0476 [0.0414, 0.0544]  cold 0.179
ico_candidate/0.1/0.0/modify       n=296 slack 0.1750 [0.1743, 0.1758]  violation 0.0028 [0.0017, 0.0041]  bound-miss 0.0626 [0.0571, 0.0679]  bound-slack 0.0334 [0.0288, 0.0387]  cold 0.085
ico_candidate/0.1/0.0/size         n=296 slack -0.0144 [-0.2107, 0.0551]  violation 0.0586 [0.0535, 0.0635]  bound-miss 0.0626 [0.0571, 0.0679]  bound-slack 0.0334 [0.0288, 0.0387]  cold 0.085
ico_candidate/0.1/0.0/veto         n=296 slack 0.1614 [0.1450, 0.1742]  violation 0.0107 [0.0034, 0.0204]  bound-miss 0.0626 [0.0571, 0.0679]  bound-slack 0.0334 [0.0288, 0.0387]  cold 0.085
ico_candidate/0.1/0.005/modify     n=296 slack 0.1750 [0.1742, 0.1757]  violation 0.0029 [0.0017, 0.0043]  bound-miss 0.0642 [0.0595, 0.0688]  bound-slack 0.0320 [0.0276, 0.0370]  cold 0.085
ico_candidate/0.1/0.005/size       n=296 slack -0.0155 [-0.2120, 0.0538]  violation 0.0601 [0.0557, 0.0643]  bound-miss 0.0642 [0.0595, 0.0688]  bound-slack 0.0320 [0.0276, 0.0370]  cold 0.085
ico_candidate/0.1/0.005/veto       n=296 slack 0.1644 [0.1497, 0.1743]  violation 0.0092 [0.0032, 0.0171]  bound-miss 0.0642 [0.0595, 0.0688]  bound-slack 0.0320 [0.0276, 0.0370]  cold 0.085
## Live envelope (ICO candidate) vs Chronos-2 univariate, bound slack (eps 0.05, size, healthy): 0.0476 vs 0.0296, diff +0.0180, n = 296, Wilcoxon p = 1.1e-34 (outside the Holm family above)
```
