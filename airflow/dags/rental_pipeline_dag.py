from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

SOURCE_NAMES = ["pap", "leboncoin", "bienici", "seloger"]


COMMON_DOCKER_ARGS = {
    "image": "logement_project-pipeline",
    "docker_url": "unix://var/run/docker.sock",
    "network_mode": "logement_project_default",
    "auto_remove": "success",
    "mount_tmp_dir": False,
    "execution_timeout": timedelta(hours=2),
}


default_args = {
    "owner": "ouffo",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def pipeline_task(task_id: str, command: str) -> DockerOperator:
    return DockerOperator(
        task_id=task_id,
        command=command,
        **COMMON_DOCKER_ARGS,
    )


with DAG(
    dag_id="rental_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args=default_args,
    tags=["rental", "scraping"],
) as dag:

    source_enrich_tasks = []

    for source_name in SOURCE_NAMES:
        fetch = pipeline_task(
            task_id=f"fetch_{source_name}",
            command=f"python -u pipelines/daily_pipelines.py --task fetch-source --source {source_name}",
        )

        extract_save = pipeline_task(
            task_id=f"extract_save_{source_name}",
            command=f"python -u pipelines/daily_pipelines.py --task extract-save-source --source {source_name}",
        )

        enrich = pipeline_task(
            task_id=f"enrich_{source_name}",
            command=f"python -u pipelines/daily_pipelines.py --task enrich-source --source {source_name}",
        )

        fetch >> extract_save >> enrich
        source_enrich_tasks.append(enrich)

    image_scoring = pipeline_task(
        task_id="image_scoring",
        command="python -u pipelines/daily_pipelines.py --task image-scoring",
    )

    final_scoring = pipeline_task(
        task_id="final_scoring",
        command="python -u pipelines/daily_pipelines.py --task final-scoring",
    )

    source_enrich_tasks >> image_scoring >> final_scoring