# Registers the v1 flows' deployments (prefect-local.yaml / prefect-remote.yaml) from
# the v1 image, apart from the legacy flows' deployer.
apiVersion: batch/v1
kind: Job
metadata:
  name: deploy-prefect-v1-workflows
spec:
  ttlSecondsAfterFinished: 60
  template:
    spec:
      containers:
      - name: deploy-prefect-v1-workflows
        image: ${actions.build.teehr-prefect-v1-image.outputs.deploymentImageId}
        command:
        - prefect
        - --no-prompt
        - deploy
        - --all
        - --prefect-file
        - ${environment.name == "local" ? "/teehr-v1/prefect-local.yaml" : "/teehr-v1/prefect-remote.yaml"}
        env:
        - name: PREFECT_API_URL
          value: http://prefect-server:4200/api
        # Passed on to the flows' jobs (the deployments' job variables).
        - name: PREFECT_TEEHR_V1_IMAGE
          value: ${actions.build.teehr-prefect-v1-image.outputs.deploymentImageId}
        - name: TEEHR_NAMESPACE
          value: ${environment.namespace}
        ${if environment.name == "local"}
        - name: REMOTE_CATALOG_S3_ENDPOINT
          value: ${var.polaris.catalogS3Endpoint}
        - name: REMOTE_CATALOG_S3_PATH_STYLE_ACCESS
          value: "${var.polaris.catalogS3PathStyleAccess}"
        ${endif}
        - name: AWS_REGION
          value: ${var.aws.region}
        - name: REMOTE_CATALOG_REST_URI
          value: ${var.polaris.catalogUri}
        - name: REMOTE_WAREHOUSE_IDENTIFIER
          value: ${var.polaris.defaultRealm}
        - name: POLARIS_OAUTH2_SERVER_URI
          value: ${var.polaris.oauthServerUri}
        - name: POLARIS_CLIENT_ID
          value: prefect-polaris
        - name: POLARIS_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: prefect-polaris-secrets
              key: client-secret
        - name: POLARIS_DEFAULT_REALM
          value: ${var.polaris.defaultRealm}
        # The automation user's personal token, for flows that call the control plane
        # (run-platform-evaluations). Optional: without it those flows refuse to start.
        - name: CONTROL_PLANE_TOKEN
          valueFrom:
            secretKeyRef:
              name: prefect-control-plane-token
              key: token
              optional: true
        resources:
          requests:
            cpu: 250m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 1Gi
      restartPolicy: Never
