"""
This file defines S3 resource static configuration parameters for CDK Constructs
"""

S3_Bucket_List = {
    # Pattern
    # "cdk-id": "bucket-name"
    # Example:

    # "prow_logs_bucket": "cdk-poc-prow-logs",
    # "status_reconciler_backup_bucket": "cdk-poc-status-reconciler-backup",
    # "daily_worker_prow_logs_bucket": "cdk-poc-daily-worker-prow-logs",
    # "daily_worker_status_reconciler_backup_bucket": "cdk-poc-daily-worker-status-reconciler-backup",
    "status_reconciler_backup_bucket": "cdk-poc-status-reconciler-backup",
    "prow_logs_bucket": "cdk-poc-prow-logs",
    "tide_bucket": "cdk-poc-tide",
}
