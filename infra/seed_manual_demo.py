"""Create the manually managed demo EC2 record in local LocalStack only."""

import json
import os
from pathlib import Path

import boto3
from botocore.config import Config


def main():
    client = boto3.client(
        "ec2", endpoint_url=os.environ.get("CLOUDPILOT_LOCALSTACK_ENDPOINT", "http://127.0.0.1:4566"), region_name="us-east-1",
        aws_access_key_id="test", aws_secret_access_key="test",
        config=Config(connect_timeout=5, read_timeout=30,
                      retries={"total_max_attempts": 2, "mode": "standard"}),
    )
    matches = []
    for page in client.get_paginator("describe_instances").paginate(Filters=[
        {"Name": "tag:CloudPilotId", "Values": ["demo-manual-01"]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
    ]):
        matches.extend(instance for reservation in page["Reservations"]
                       for instance in reservation["Instances"])
    if len(matches) > 1:
        raise RuntimeError("Multiple manual demo instances found; inspect before seeding")
    if matches:
        instance_id = matches[0]["InstanceId"]
    else:
        response = client.run_instances(
            ImageId="ami-0c55b159cbfafe1f0", InstanceType="m5.2xlarge",
            MinCount=1, MaxCount=1,
            TagSpecifications=[{"ResourceType": "instance", "Tags": [
                {"Key": key, "Value": value} for key, value in {
                    "Name": "cloudpilot-manual-dev", "CloudPilotDemo": "true",
                    "CloudPilotId": "demo-manual-01", "Management": "manual",
                    "Environment": "development", "Team": "platform", "Owner": "demo-engineer",
                }.items()
            ]}],
        )
        instance_id = response["Instances"][0]["InstanceId"]
    if not matches or matches[0]["State"]["Name"] == "pending":
        client.get_waiter("instance_running").wait(
            InstanceIds=[instance_id], WaiterConfig={"Delay": 2, "MaxAttempts": 30},
        )
    result = {"resource_id": "demo-manual-01", "management": "manual",
              "provider_id": instance_id, "endpoint": "http://127.0.0.1:4566"}
    target = Path(__file__).resolve().parents[1] / "data/local/manual-demo.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
