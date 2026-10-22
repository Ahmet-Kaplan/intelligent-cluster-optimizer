"""Export GKE container metrics for the gate-* namespaces (Cloud Monitoring REST, paginated).

Usage: export_metrics.py PROJECT CLUSTER START_RFC3339 METRIC OUT.json   (METRIC e.g. memory/used_bytes)
"""
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

project, cluster, start, metric, out = sys.argv[1:6]
token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
params = {
    "filter": (f'metric.type="kubernetes.io/container/{metric}" AND resource.labels.cluster_name="{cluster}"'
               ' AND resource.labels.namespace_name=starts_with("gate-")'),
    "interval.startTime": start,
    "interval.endTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
series, page = [], None
while True:
    q = dict(params, **({"pageToken": page} if page else {}))
    url = f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    series += body.get("timeSeries", [])
    page = body.get("nextPageToken")
    if not page:
        break
json.dump(series, open(out, "w"))
print(f"{metric}: {len(series)} series, {sum(len(s['points']) for s in series)} points -> {out}")
