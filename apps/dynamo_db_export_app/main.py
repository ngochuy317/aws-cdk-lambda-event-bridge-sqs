from datetime import datetime, timedelta
import boto3

client = boto3.client('dynamodb')


def lambda_handler(event, context):
    existing_export = client.list_exports(
        TableArn=event['TABLE_ARN'],
        MaxResults=10
    )

    print(existing_export)

    if existing_export and ('ExportSummaries' in existing_export) and bool(existing_export['ExportSummaries']):
        # Incremental export
        completed_export = list(filter(lambda x: x['ExportStatus'] == 'COMPLETED', existing_export['ExportSummaries']))
        running_export = list(filter(lambda x: x['ExportStatus'] == 'IN_PROGRESS', existing_export['ExportSummaries']))

        if running_export:
            raise Exception(f"Export for {event['TABLE_ARN']} is already running with {existing_export['ExportSummaries'][0]['ExportArn']}")

        if completed_export:
            latest_export = max(completed_export, key=lambda x: x['ExportArn'])
            response = client.describe_export(
                ExportArn=latest_export['ExportArn']
            )

            now_ts = datetime.utcnow()
            last_response = response['ExportDescription'].get('ExportTime', response['ExportDescription']['EndTime'])
            days_diff = (datetime.utcnow() - last_response.replace(tzinfo=None)).days

            next_ts = last_response.replace(tzinfo=None)
            prev_ts = last_response.replace(tzinfo=None)

            for i in range(0, days_diff + 1):
                # DynamoDB allows only 24 hours export
                next_ts = min(next_ts + timedelta(hours=23), now_ts)
                export_response = run_db_export(event, prev_ts, next_ts)

                print(export_response)
                prev_ts = next_ts
        else:
            raise Exception(f"No successful export for {event['TABLE_ARN']}")
    else:
        # Full export
        export_response = run_db_export(event, datetime.utcnow() - timedelta(hours=23), datetime.utcnow())
        print(export_response)


def run_db_export(event, time_from, time_to):
    print(f"Running from {time_from} to {time_to} for table {event['TABLE_ARN']}")
    return client.export_table_to_point_in_time(
        TableArn=event['TABLE_ARN'],
        IncrementalExportSpecification={
          'ExportFromTime': time_from,
          'ExportToTime': time_to,
          'ExportViewType': 'NEW_IMAGE'
        },
        ExportType='INCREMENTAL_EXPORT',
        S3Bucket=event['S3_BUCKET'],
        S3Prefix=event['S3_PREFIX'],
        S3SseAlgorithm='AES256',
        ExportFormat='DYNAMODB_JSON'
    )
