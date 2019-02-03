// Oneoff job to cleanup the ci system.
//
local params = std.extVar("__ksonnet/params").components["cleanup-ci-cron"];
local env = std.extVar("__ksonnet/environments");

local k = import "k.libsonnet";
local cleanup = import "cleanup-ci.libsonnet";

apiVersion: batch/v1beta1
kind: CronJob
metadata:
  name: label-sync-cron
spec:
  schedule: "0 */6 * * *"    # Every day 23:17 / 11:17PM
  concurrencyPolicy: Forbid
  jobTemplate:
    metadata:
      labels:
        app: label-sync
    spec:
      template:
        spec:
          containers:
            - name: label-sync
              image: gcr.io/k8s-testimages/label_sync:v20180921-f7ff24f34
              args:
              - --config=/etc/config/kubeflow_label.yml
              - --confirm=true
              - --orgs=kubeflow
              - --token=/etc/github/bot-token
              volumeMounts:
              - name: oauth
                mountPath: /etc/github
                readOnly: true
              - name: config
                mountPath: /etc/config
                readOnly: true
          restartPolicy: Never
          volumes:
          - name: oauth
            secret:
              secretName: bot-token-github
          - name: config
            configMap:
              name: label-config-v2

local job = {
    "apiVersion": "batch/v1beta", 
    "kind": "CronJob", 
    "metadata": {           
      name: params.name,
      namespace: env.namespace,
      labels: {
        job: "cleanup-ci"
      },
    }, 
    spec: {
      schedule: "0 */2 * * *"    # Every two hours
      concurrencyPolicy: Forbid
      jobTemplate:
        metadata:
          labels:
            app: label-sync
      
      jobTemplate: {
        spec: cleanup.jobSpec,
      },
    }, 
};

std.prune(k.core.v1.list.new([  
  job,
]))
