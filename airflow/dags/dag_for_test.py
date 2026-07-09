from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def fail():
    raise RuntimeError("SMTP test")


with DAG(
    dag_id="test_notifications",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "email": ["fujimotohugo@gmail.com"],
        "email_on_failure": True,
    },
    tags=["test"],
) as dag:
    PythonOperator(task_id="fail_task", python_callable=fail)
