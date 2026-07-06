from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime


def hello():
    print("Hello from Airflow!")

def goodbye():
    print("Goodbye from Airflow!")

with DAG(
    dag_id="hello_world",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
) as dag:

    env = BashOperator(
        task_id="env",
        bash_command="env",
    )

    project = BashOperator(
        task_id="project",
        bash_command="ls -la /opt/airflow",
    )

    docker_version = BashOperator(
        task_id="docker_version",
        bash_command="docker --version",
    )

    docker_ps = BashOperator(
        task_id="docker_ps",
        bash_command="docker ps",
    )

    env >> project >> docker_ps