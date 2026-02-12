import boto3, os, logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("region: %s", os.environ.get("AWS_DEFAULT_REGION"))
    logger.info("%s", boto3.client("sts").get_caller_identity())
