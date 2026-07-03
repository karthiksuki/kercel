import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
export interface DataStackProps extends cdk.StackProps {
    readonly stage: string;
}
export declare class DataStack extends cdk.Stack {
    readonly projectsTable: dynamodb.Table;
    readonly deploymentsTable: dynamodb.Table;
    readonly artifactsBucket: s3.Bucket;
    readonly deploymentQueue: sqs.Queue;
    readonly deploymentDlq: sqs.Queue;
    constructor(scope: Construct, id: string, props: DataStackProps);
}
