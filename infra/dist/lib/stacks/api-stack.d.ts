import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
export interface ApiStackProps extends cdk.StackProps {
    readonly stage: string;
    readonly projectsTable: dynamodb.ITable;
    readonly deploymentsTable: dynamodb.ITable;
    readonly deploymentQueue: sqs.IQueue;
}
export declare class ApiStack extends cdk.Stack {
    readonly api: apigateway.RestApi;
    constructor(scope: Construct, id: string, props: ApiStackProps);
}
