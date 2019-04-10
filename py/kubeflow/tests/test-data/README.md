### How to generate API JSON file for tests.
Run the following command:
```bash
GET https://www.googleapis.com/discovery/v1/apis/{API_NAME}/{VERSION}/rest

# example
GET https://www.googleapis.com/discovery/v1/apis/deploymentmanager/v2/rest > \
deploymentmanager-v2.json
```
