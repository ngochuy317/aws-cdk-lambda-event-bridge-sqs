import boto3


class GlueService:
    def __init__(self):
        self.glue = boto3.client('glue')
    
    def run_async(self, object_name, config):
        response = self.glue.start_job_run(
            JobName=config['target_glue_arn'],
            Arguments={
                '--FILE_NAME': object_name
            }
        )
    
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            return response['JobRunId']

    def is_running(self, resource_arn):
        glue_runs = self.glue.get_job_runs(
            JobName=resource_arn,
            MaxResults=10
        )
        running_jobs = list(filter(lambda glue_run: glue_run['JobRunState'] in ['RUNNING', 'STARTING', 'WAITING'], glue_runs))
    
        return len(running_jobs) > 0
