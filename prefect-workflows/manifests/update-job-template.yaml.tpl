apiVersion: batch/v1
kind: Job
metadata:
  name: update-job-template
spec:
  ttlSecondsAfterFinished: 60
  template:
    spec:
      containers:
      - name: update-job-template
        image: ${actions.build.teehr-prefect-image.outputs.deploymentImageId}
        command:
        - python
        - /opt/teehr/update_job_template.py

        env:
        - name: PREFECT_API_URL
          value: http://prefect-server:4200/api
      restartPolicy: Never