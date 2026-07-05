from dataclasses import dataclass


@dataclass(frozen=True)
class KercelStageConfig:
    stage: str
    instance_type: str
    min_capacity: int
    max_capacity: int
    desired_capacity: int
    redis_node_type: str


def get_stage_config(stage: str) -> KercelStageConfig:
    is_prod = stage == "prod"
    return KercelStageConfig(
        stage=stage,
        instance_type="t3.small" if is_prod else "t3.micro",
        min_capacity=2 if is_prod else 1,
        max_capacity=10 if is_prod else 3,
        desired_capacity=2 if is_prod else 1,
        redis_node_type="cache.t3.small" if is_prod else "cache.t3.micro",
    )
