# [Kubernetes Resources] Infrastructure as Code

We utilize [helm](https://github.com/helm/helm) which
serves as the tool of Kubernetes resources Infrastructure as Code (IAC).

## Deploy Helm Charts
This section describes how to deploy helm charts on existing Kubernetes cluster

### Deploy ALB Ingress Controller

```shell script
helm install alb-ingress-controller ./alb-ingress-controller \
		--set clusterName=<EKS Cluster Name> \
		--set secret.keyValue=<AWS Public Key> \
		--set secret.secretValue=<AWS Secret key>
```

### Deploy Grafana and Prometheus

```shell script
kubectl create namespace prometheus
kubectl create namespace grafana

helm install prometheus ./prometheus \
    --namespace prometheus \
    --set alertmanager.persistentVolume.storageClass="gp2" \
    --set server.persistentVolume.storageClass="gp2"

helm install grafana ./grafana \
    --namespace grafana \
    --set persistence.storageClassName="gp2" \
    --set persistence.enabled=true \
    --set adminPassword='KFCI!Awesome' \
    --values ./grafana/environment/grafana.yaml \
    --set service.type=LoadBalancer
```

### Deploy Prow

```shell script
kubectl create namespace prow 
kubectl create namespace test-pods

helm install prow ./prow \
		--set s3Buckets.statusReconciler=<Status Reconciler S3 Bucket> \
		--set s3Buckets.prowLogs=<Prow Logs S3 Bucket> \
		--set s3Buckets.tide=<Tide S3 Bucket> \
		--set secret.keyValue=<AWS Public Key> \
		--set secret.secretValue=<AWS Secret key> \
		--set managedGithubOrg=<Prow Managed Github Organization> \
		--set prowDashboardDomainName=<Prow Dashboard Domain Name> \
		--set prowDashboardDomainNameACMCerts=<Prow Dashboard Domain Name ACM Certificates> \
		--set tokens.githubToken=<Github Token> \
		--set tokens.hmacToken=<Hmac Token>
```