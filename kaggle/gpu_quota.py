"""The Kaggle account's weekly GPU hours: used, allowed, left, and when they refresh (UTC) (#772).

Read it before and after every GPU run (AGENTS.md, "Failures, retries and reruns"), so the cost of a run is known
and the week isn't spent in a day. Uses the Kaggle token the other scripts use (KAGGLE_API_TOKEN); prints no secret.

usage: python kaggle/gpu_quota.py
"""


def summarize(response) -> dict:
    """Hours used, allowed and left, and the refresh time, from Kaggle's accelerator quota statistics."""
    q = response.gpu_quota
    used = round(q.time_used.total_seconds() / 3600, 2)
    allowed = round(q.total_time_allowed.total_seconds() / 3600, 2)
    return {"gpu_hours_used": used, "gpu_hours_allowed": allowed, "gpu_hours_left": round(allowed - used, 2),
            "refresh_ts": response.quota_refresh_time.isoformat()}


def line(summary: dict) -> str:
    """The one line the script prints, as kaggle/README.md shows it."""
    return (f"gpu_hours used {summary['gpu_hours_used']:.2f} allowed {summary['gpu_hours_allowed']:.2f} "
            f"left {summary['gpu_hours_left']:.2f} refresh {summary['refresh_ts']} UTC")


def fetch():
    """Ask Kaggle for this account's accelerator quota statistics."""
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.kernels.types.kernels_api_service import ApiGetAcceleratorQuotaStatisticsRequest
    api = KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as client:
        return client.kernels.kernels_api_client.get_accelerator_quota_statistics(
            ApiGetAcceleratorQuotaStatisticsRequest())


if __name__ == "__main__":
    print(line(summarize(fetch())))
