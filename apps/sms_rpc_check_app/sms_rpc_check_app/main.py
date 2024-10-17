import pandas
from pandarallel import pandarallel
import uuid
import os
from datetime import datetime
from const import DEFAULT_FILE_SEPARATOR, ETL_FIELD_NAME, DEFAULT_TIMESTAMP_MASK, get_logger
from service.s3_service import S3Service
from service.dynamo_db_service import DynamoDBService
from service.mulesoft_service import MulesoftService
from service.ssm_service import SSMService


def read_path_from_db(dynamo_service, dynamo_item, etl_name):
    item = dynamo_service.read_item({'item': dynamo_item, 'etl_name': etl_name})

    if item:
        return f"s3://{item['dest_bucket']}/{item['dest_path']}", item

    return None, None


def update_dynamo_path(dynamo_service, dynamo_item, new_path):
    dynamo_item["dest_path"] = new_path.replace(f"s3://{dynamo_item['dest_bucket']}/", "")
    dynamo_service.update_item(dynamo_item)


def get_parallel_num(ds_size):
    num_chck = ds_size // 10000

    return {
        0: 4,
        1: 8,
        2: 6,
        3: 10,
        4: 12
    }.get(num_chck, 16)


if __name__ == '__main__':
    local_logger = get_logger()
    s3_service = S3Service(logger=local_logger)
    ssm_service = SSMService(logger=local_logger, env=os.environ['GLOBAL_ENVIRONMENT'])
    dynamo_db_service = DynamoDBService(region=os.environ['GLOBAL_REGION'], table_name=os.environ['ETL_LOG_TABLE'])
    mulesoft_service = MulesoftService(
        client_id=ssm_service.get_ssm_parameter_with_env(os.getenv('MULESOFT_CLIENT_ID')),
        client_secret=ssm_service.get_ssm_parameter_with_env(os.getenv('MULESOFT_CLIENT_SECRET')),
        username=ssm_service.get_ssm_parameter_with_env(os.getenv('MULESOFT_USERNAME')),
        password=ssm_service.get_ssm_parameter_with_env(os.getenv('MULESOFT_PASSWORD')),
        logger=local_logger
    )

    rpc_url = ssm_service.get_ssm_parameter_with_env(os.getenv('MULESOFT_SMS_RESPONSE_ENDPOINT_KEY'))
    input_s3_path, dynamo_path_item = read_path_from_db(dynamo_db_service, os.environ['DYNAMO_ITEM'], ETL_FIELD_NAME)
    if input_s3_path:
        # If path hasn't been already RPC enriched
        if not input_s3_path.startswith("RPC_"):
            local_logger.info(f"Loading {input_s3_path} file. CPU - {os.cpu_count()}")
            s3_service.download_file_from_s3(input_s3_path, "non_rpc_temp.csv")

            sep = os.environ["FILE_SEPARATOR"] if "FILE_SEPARATOR" in os.environ else DEFAULT_FILE_SEPARATOR
            read_header = 0
            write_header = True

            if ("FILE_HAS_HEADER" in os.environ) and (os.environ["FILE_HAS_HEADER"] == "False"):
                read_header = None
                write_header = False

            local_logger.info(f"Reading input {input_s3_path} file with header {read_header} and separator {sep}")
            df = pandas.read_csv('non_rpc_temp.csv', sep=sep, header=read_header, dtype=str, engine="python")
            pandarallel.initialize(nb_workers=get_parallel_num(len(df.index)), progress_bar=True)
            df['RPC_COUNT'] = df[["msisdn", "branch_no", "account_id"]].parallel_apply(lambda x: mulesoft_service.get_rpc_count(rpc_url, x), axis=1)
            df['RPC_COUNT_TIMESTAMP'] = datetime.now().strftime(DEFAULT_TIMESTAMP_MASK)

            if input_s3_path.endswith("/") or input_s3_path.endswith(".txt"):
                last_folder = input_s3_path.split('/')[-2]
                file_name = input_s3_path.split('/')[-1]
            else:
                last_folder = input_s3_path.split('/')[-1]
                file_name = f'{uuid.uuid4().hex}.txt'

            df.to_csv('temp_rpc.csv', sep=sep, index=False, header=write_header)
            output_s3_path = input_s3_path.replace(file_name, f'RPC_{file_name}')
            local_logger.info(f"Writing to audience location {output_s3_path}")
            s3_service.upload_file_to_s3(output_s3_path, "temp_rpc.csv")

            if output_s3_path.endswith("/") or output_s3_path.endswith(".txt"):
                last_folder = output_s3_path.split('/')[-2]
            else:
                last_folder = output_s3_path.split('/')[-1]

            output_s3_internal_path = output_s3_path.replace(last_folder, f'{last_folder}_internal')
            local_logger.info(f"Writing to internal audience location {output_s3_internal_path}")
            s3_service.upload_file_to_s3(output_s3_internal_path, "temp_rpc.csv")
            update_dynamo_path(dynamo_db_service, dynamo_path_item, output_s3_path)
            s3_service.delete_object(input_s3_path)
            local_logger.info(f"Successfully processed {dynamo_path_item}")
    else:
        raise Exception(f"Path for {os.environ['DYNAMO_ITEM']} doesn't exist!")
