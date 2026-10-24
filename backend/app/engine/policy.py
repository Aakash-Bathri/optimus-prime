from dataclasses import asdict, dataclass

ENGINE_VERSION = "deterministic-v1"


@dataclass(frozen=True)
class Policy:
    version: str = "conservative-demo-v1"
    cpu_limit_pct: float = 80
    memory_limit_pct: float = 80
    disk_limit_pct: float = 80
    minimum_coverage: float = 0.95
    minimum_history_days: int = 7
    maximum_sample_age_seconds: int = 3600
    stress_multiplier: float = 1.2
    saturation_pct: float = 95
    idle_cpu_peak_pct: float = 5
    idle_memory_peak_pct: float = 20
    idle_iops_peak: float = 10
    idle_network_peak_mbps: float = 1

    def as_dict(self) -> dict:
        return asdict(self)


POLICY = Policy()
