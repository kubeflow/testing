# Access Control

Prerequisites:
* Apply your AWS account in advance via [starting page](https://portal.aws.amazon.com/billing/signup#/start)

We provide below IAM Roles/Users with respect to test-infra AWS account:

* infra-viewer
    * This is controlled by IAM role: [infra-viewer](./assume-role-access/infra-viewer/trust-policy.json)
    * It will grant read access to Argo Cluster and Tekton Cluster's namespace (kubeflow-test-infra)
    * Folks making regular and continual contributions to Kubeflow and in need of access to debug tests can generally have access

* infra-editor
    * This is controlled by IAM role: [infra-editor](./assume-role-access/infra-editor/trust-policy.json)
    * It will grant write access to Argo Cluster and Tekton Cluster's namespace (kubeflow-test-infra)
    * We want to limit the number of folks with write access to test-infra:
        * WG TechLeads and testing-infra operators can request the access

* infra-admin
    * This is controlled by IAM Group: [infra-admin](./console-access/infra-admin/infra-admin.yaml)
    * It will grant Admin access to the AWS account hosted test-infra
    * Limited to test-infra WG Leaders (2 - 3 total)
    
    
## Guidance for Access

### CLI Access
infra-viewer and infra-editor can be only be access via CLI. 

0. Create AWS IAM ROLE/USER from your console via [official doc](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html#id_users_create_console):  
0.1. In #4 step, select **Programmatic access**  
0.2. In #6 step, choose **Attach existing policies to user directly**, and use administrator policy for simplicity.  
0.3. In #11 step, save user's access keys for below usage.

1. Configure AWS Credentials with keys you stored and region
```shell script
$ aws configure

AWS Access Key ID [****************ABCD]:ABCDEFG123456
AWS Secret Access Key [****************EFGH]:HIJKLMN7890
Default region name [us-west-2]: us-west-2
Default output format [None]:
```

2. Confirm you authenticated to be yourself
```shell script
$ aws sts get-caller-identity

{
    "UserId": "<YOUR AWS ACCOUNT PUBLIC KEY>",
    "Account": "<YOUR AWS ACCOUNT ID>",
    "Arn": "<YOUR AWS IAM USER/ROLE ARN>"
}
```

3. Assume infra-editor / infra-viewer role
```shell script
$ aws sts assume-role --role-arn arn:aws:iam::809251082950:role/infra-editor --role-session-name <YourPreferredName>
OR 
$ aws sts assume-role --role-arn arn:aws:iam::809251082950:role/infra-viewer --role-session-name <YourPreferredName>

Example Output:

{
   “Credentials”: {
       “AccessKeyId”: “AAA”,
       “SecretAccessKey”: “BBBBBB”,
       “SessionToken”: “CCCCC“,
       “Expiration”: “2020-09-30T23:23:09Z”
   },
   “AssumedRoleUser”: {
       “AssumedRoleId”: “XXXXXXXX:YourPreferredName”,
       “Arn”: “arn:aws:sts::809251082950:assumed-role/infra-editor/YourPreferredName”
   }
}
```

4. Use generated credentials to access Argo and Tekton Clusters
```shell script
$ export AWS_ACCESS_KEY_ID=AAA
$ export AWS_SECRET_ACCESS_KEY=BBBBBB
$ export AWS_SESSION_TOKEN=CCCCC
$ export AWS_REGION=us-west-2
```

5. Confirm you authenticated to be infra-editor / infra-viewer
```shell script
aws sts get-caller-identity
```

6. Update Tekton and Argo Cluster’s Kube-Config
```shell script
# Argo Cluster kubeconfig
$ aws eks update-kubeconfig --name optional-test-infra-argo

# Tekton Cluster kubeconfig
$ aws eks update-kubeconfig --name optional-test-infra-tekton
```

7. Access into Tekton and Argo Cluster’s `kubeflow-test-infra` namespace
```shell script
# Argo Cluster Dataplane
kubectl get all -n kubeflow-test-infra --context=arn:aws:eks:us-west-2:809251082950:cluster/optional-test-infra-argo

# Tekton Cluster Dataplane
kubectl get all -n kubeflow-test-infra --context=arn:aws:eks:us-west-2:809251082950:cluster/optional-test-infra-tekton
```

