import boto3, os
print("region:", os.environ.get("AWS_DEFAULT_REGION"))
print(boto3.client("sts").get_caller_identity())
