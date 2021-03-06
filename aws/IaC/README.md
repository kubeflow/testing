# Infrastructure as Code

Test infrastructure is set up as two layers of resources:

1. AWS resources set up via [CDK](CDK/test-infra/README.md)
2. Kubernetes resources set up via [Helm](helm/test-infra/README.md)

## Set up Prow Cluster as Test Infrastructure

### Set up AWS resources

1. Set up ACM certificates for domain names

Add ACM certificates in [ACM_Resources.py](./CDK/test-infra/config/static_config/ACM_Resources.py), take a note of 
 <Prow Dashboard Domain Name> and <Prow Dashboard Domain Name ACM Certificates>

2. Set up S3 buckets

Add S3 buckets in [S3_Resources.py](./CDK/test-infra/config/static_config/S3_Resources.py), take a note of
<Status Reconciler S3 Bucket>, <Prow Logs S3 Bucket>, and <Tide S3 Bucket>.

3. Set up EKS clusters

Add EKS clusters in [EKS_Resources.py](./CDK/test-infra/config/static_config/EKS_Resources.py), take a note of
<EKS Cluster Name>

Deploy AWS resources via `cdk deploy`, more details [here](./CDK/test-infra/README.md)

### Set up Tokens

1. Create Github Token

Create a [personal access token](https://github.com/settings/tokens) for the GitHub bot account, adding the following scopes
* Must have the `public_repo` and `repo:status` scopes
* Add the `repo` scope if you plan on handing private repos
* Add the `admin:org_hook` scope if you plan on handling a github org

Take a note of <Github Token>

2. Create Github Secret (Hmac Token)

You will need two secrets to talk to GitHub. The `hmac-token` is the token that you give
 to GitHub for validating webhooks. Generate it using any reasonable randomness-generator, 
```shell script
openssl rand -hex 20
```

Take a note of <Hmac Token>

### Set up Kubernetes resources

In general, follow the [doc](./helm/test-infra/README.md) and fill in parameters with above notes

Note: go to [AWS Route53 console](https://console.aws.amazon.com/route53/v2/hostedzones#) to
 configure DNS record when you use any of domain names.
