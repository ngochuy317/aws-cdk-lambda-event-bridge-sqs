import boto3


class S3Service:
    def __init__(self, logger):
        self.client = boto3.client("s3", region_name='us-east-1')
        self.logger = logger

    @staticmethod
    def get_bucket_and_key_from_string(s3_path):
        bucket = s3_path.replace('s3://', '').split('/')[0]
        key = s3_path.replace(f's3://{bucket}/', '')

        return [bucket, key]

    def download_file_from_s3(self, s3_path, local_path):
        bucket, key = self.get_bucket_and_key_from_string(s3_path)
        self.logger.info(f"Download {s3_path} to {local_path}")

        with open(local_path, 'wb') as file_io:
            self.client.download_fileobj(bucket, key, file_io)

    def upload_file_to_s3(self, s3_path, local_path):
        bucket, key = self.get_bucket_and_key_from_string(s3_path)
        self.logger.info(f"Upload {s3_path} to {local_path}")

        with open(local_path, 'rb') as file_io:
            self.client.upload_fileobj(file_io, bucket, key)

    def is_path_exists(self, s3_path):
        bucket, key = self.get_bucket_and_key_from_string(s3_path)
        response = self.client.list_objects_v2(Bucket=bucket, Prefix=key)

        if 'Contents' in response:
            objects = response['Contents']
            if objects:
                return True

        return False

    def delete_object(self, s3_path):
        s3_bucket, s3_object = self.get_bucket_and_key_from_string(s3_path)
        self.logger.info(f"Dropping {s3_path} object")
        self.client.delete_object(Bucket=s3_bucket, Key=s3_object)
