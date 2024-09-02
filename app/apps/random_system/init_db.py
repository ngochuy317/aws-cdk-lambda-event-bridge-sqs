import os
import boto3
from botocore.exceptions import ClientError

def handler(event, context):
    # Retrieve environment variables
    cluster_arn = os.environ['DB_CLUSTER_ARN']
    secret_arn = os.environ['DB_SECRET_ARN']
    db_name = os.environ['DB_NAME']

    # Initialize the boto3 RDS DataService client
    rds_data = boto3.client('rds-data')

    try:
        # Create table using the RDS Data API
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        execute_statement(rds_data, cluster_arn, secret_arn, db_name, create_table_sql)

        # Insert test data using the RDS Data API
        insert_data_sql = """
        INSERT INTO users (name, email) VALUES
        ('Alice', 'alice@example.com'),
        ('Bob', 'bob@example.com'),
        ('Charlie', 'charlie@example.com')
        ON CONFLICT (email) DO NOTHING;
        """
        execute_statement(rds_data, cluster_arn, secret_arn, db_name, insert_data_sql)

        print("Database initialized with test data successfully.")

    except Exception as e:
        print(f"Error initializing the PostgreSQL database: {e}")


def execute_statement(rds_data, cluster_arn, secret_arn, db_name, sql):
    """Execute a SQL statement using the RDS Data API."""
    try:
        response = rds_data.execute_statement(
            secretArn=secret_arn,
            database=db_name,
            resourceArn=cluster_arn,
            sql=sql
        )
        print(f"SQL executed successfully: {response}")
    except ClientError as e:
        print(f"Error executing SQL statement: {e}")
        raise e