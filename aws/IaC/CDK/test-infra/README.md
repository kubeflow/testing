# [AWS Resources] Infrastructure as Code

We utilize [CDK](https://github.com/aws/aws-cdk) which
serves as the AWS resources tool of Infrastructure as Code (IAC).

## Project Architecture
We define AWS resources in [static_config](https://github.com/kubeflow/testing/tree/master/aws/IaC/CDK/test-infra/config/static_config),
establish CDK stacks in [test_infra_stack.py](https://github.com/kubeflow/testing/tree/master/aws/IaC/CDK/test-infra/test_infra/test_infra_stack.py),
and reference in root [app.py](https://github.com/kubeflow/testing/tree/master/aws/IaC/CDK/test-infra/app.py).

## Useful Information

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
executable in your path with access to the `venv` package.
If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation
