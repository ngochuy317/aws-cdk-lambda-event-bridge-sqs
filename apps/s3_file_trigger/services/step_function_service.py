import json
import boto3


class SfnService:
    def __init__(self):
        self.sfn = boto3.client('stepfunctions')

    # TODO: add templatization
    def run_async(self, object_name, config):
        sfn_exec_input = config["target_sfn_input"] | {
            'object_name': object_name,
            'dynamo_item': config["configuration_id"]
        }
        sfn_exec_input['InputConfig']['eventBody']['fileName'] = object_name.split('/')[-1]
        response = self.sfn.start_execution(
            stateMachineArn=config["target_arn"],
            input=json.dumps(sfn_exec_input, indent=4)
        )
        print(response)

        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            return response['executionArn']

    def is_running(self, sfn_arn):
        running_sfn = self.sfn.list_executions(
            stateMachineArn=sfn_arn,
            statusFilter='RUNNING',
            maxResults=10
        )

        return len(running_sfn["executions"]) > 0
