import os
from datetime import datetime, timedelta
import boto3
from boto3.dynamodb import conditions
import functools
import uuid

from common.constants import get_logger


class DynamoLockException(Exception):
    def __init__(self, message):
        super().__init__(message)


class DynamoDBLockService:
    def __init__(self, lock_table, logger, timeout_in_seconds):
        dynamodb = boto3.resource("dynamodb")

        self.table = dynamodb.Table(lock_table)
        self.ex = dynamodb.meta.client.exceptions

        self.timeout_in_seconds = timeout_in_seconds
        self.logger = logger

    def acquire_lock(self, stage: str, unique_request_id: str, transaction_id: str) -> bool:
        now = datetime.utcnow().isoformat(timespec="seconds")
        new_timeout = (datetime.utcnow() + timedelta(seconds=self.timeout_in_seconds)).isoformat(
            timespec="seconds"
        )

        try:
            self.logger.debug("Acquiring lock for %s event with %s transaction id for %s sec.",
                              unique_request_id, transaction_id, self.timeout_in_seconds)
            self.table.update_item(
                Key={'unique_request_id': unique_request_id, 'stage': stage},
                UpdateExpression="SET #tx_id = :tx_id, #timeout = :timeout",
                ExpressionAttributeNames={
                    "#tx_id": "transaction_id",
                    "#timeout": "timeout",
                },
                ExpressionAttributeValues={
                    ":tx_id": transaction_id,
                    ":timeout": new_timeout,
                },
                ConditionExpression=conditions.Or(
                    conditions.Attr("stage").not_exists(),  # New Item, i.e. no lock
                    conditions.Attr("timeout").lt(now),  # Old lock is timed out
                ),
            )

            self.logger.info(
                "Successfully acquired lock for %s event with %s transaction id until %s.",
                unique_request_id, transaction_id, new_timeout
            )
            return True

        except self.ex.ConditionalCheckFailedException as e:
            self.logger.warn(
                "Failed to acquired lock for %s event with %s transaction id due to %s.",
                unique_request_id, transaction_id, e
            )
            # It's already locked
            return False

    def release_lock(self, stage: str, unique_request_id: str, transaction_id: str) -> bool:
        try:
            self.logger.debug(
                "Realising lock for %s stage %s event with %s transaction id.", stage, unique_request_id, transaction_id
            )
            self.table.delete_item(
                Key={'unique_request_id': unique_request_id, 'stage': stage},
                ConditionExpression=conditions.Attr("transaction_id").eq(transaction_id),
            )

            self.logger.info(
                "Successfully released lock for %s stage %s event with %s transaction.", stage, unique_request_id, transaction_id
            )
            return True

        except (self.ex.ConditionalCheckFailedException, self.ex.ResourceNotFoundException) as e:
            self.logger.warn(
                "Failed to release lock for %s stage %s event with %s transaction id due to %s.",
                stage, unique_request_id, transaction_id, e
            )
            return False


class DynamoDBLockServiceConstructor:
    @staticmethod
    def create(logger=None, timeout_in_seconds=40):
        local_logger = logger if logger else get_logger()

        return DynamoDBLockService(
            lock_table=os.environ['DYNAMO_LOCK_TABLE'],
            logger=local_logger,
            timeout_in_seconds=timeout_in_seconds
        )


def dynamo_lock(_func=None, *, unique_request_id_func, stage, lock_service=None):
    def decorator_dynamo_lock(func):
        @functools.wraps(func)
        def wrap(event, context):
            dynamo_db_lock = lock_service if lock_service else DynamoDBLockServiceConstructor.create()

            # Handle batch failures
            transaction_id = uuid.uuid4().hex
            unique_request_id = unique_request_id_func(event)

            if not dynamo_db_lock.acquire_lock(stage, unique_request_id, transaction_id):
                raise DynamoLockException(f"Item {stage} stage {unique_request_id} is locked!")

            try:
                func(event, context)
            finally:
                dynamo_db_lock.release_lock(stage, unique_request_id, transaction_id)

        return wrap

    if _func is None:
        return decorator_dynamo_lock
    else:
        return decorator_dynamo_lock(_func)
